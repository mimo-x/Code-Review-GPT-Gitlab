"""把审查报告发布到 MR：总结评论原地更新，问题作为一轮 review 发到对应代码行。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from redis.exceptions import LockError

from utils.redis_client import redis_client

from ..engines.base import Finding
from ..report import ReviewReport
from ..rendering import PublishHistory, render_inline_comment, render_summary
from ..rendering.markers import parse_findings_marker, parse_summary_marker, summary_marker
from ..services import DraftNotesUnsupported
from .threads import plan_threads

logger = logging.getLogger(__name__)

# 持锁进程崩溃后锁会自动过期，等待时间要长于过期时间
_LOCK_TTL_S = 300
_LOCK_WAIT_S = 330


@dataclass
class _Comment:
    findings: list[Finding]
    body: str
    position: dict

    @property
    def fingerprints(self) -> set[str]:
        return {finding.fingerprint for finding in self.findings}


class _ReviewUnavailable(Exception):
    """这次不能用草稿一次性发布，改为逐条发布。"""


@dataclass
class _PublishedState:
    summary_note_id: int | None = None
    summary_review_id: int | None = None
    # 有行内讨论的问题（含所在讨论 id 和是否已解决）
    findings: dict[str, dict] = field(default_factory=dict)
    # 上一轮总结里的全部问题
    summarized: dict[str, dict] = field(default_factory=dict)

    @property
    def previous(self) -> dict[str, dict]:
        return {**self.summarized, **self.findings}


class GitLabReviewPublisher:
    def __init__(self, gitlab_service, request_id: str | None = None):
        self.gitlab = gitlab_service
        self.request_id = request_id

    def publish(self, report: ReviewReport) -> dict:
        """读取已有评论到写完总结必须互斥，否则并发审查会发出重复评论。"""
        mr = report.mr
        lock = redis_client.get_client().lock(
            f"review:publish:{mr.project_id}:{mr.mr_iid}",
            timeout=_LOCK_TTL_S,
            blocking_timeout=_LOCK_WAIT_S,
        )
        if not lock.acquire():
            raise RuntimeError("等待同一 MR 的发布任务超时")
        try:
            return self._publish(report)
        finally:
            try:
                lock.release()
            except LockError as exc:
                logger.warning("[%s] 发布锁已过期: %s", self.request_id, exc)

    def _publish(self, report: ReviewReport) -> dict:
        mr = report.mr
        state, history_available = self._load_state(mr.project_id, mr.mr_iid)
        if state.summary_review_id and state.summary_review_id > report.review_id:
            # 较早的审查比新一轮更晚结束时，不能覆盖新结果
            return {
                "success": True,
                "message": "已有更新的审查结果，跳过发布",
                "details": {"skipped": True},
            }

        carried = _carry_over(report.findings, state)
        reported = {finding.fingerprint for finding in report.findings}
        threads = {
            fp: record["fp"] for fp, record in state.findings.items()
            if fp in reported and record.get("fp") != fp
        }
        # 首次审查先占住总结的位置，MR 动态里总结才会排在行内评论之前
        updated = state.summary_note_id is not None
        note_id = state.summary_note_id or self._write_summary(
            mr.project_id, mr.mr_iid, None, self._summary_body(report, None, threads)
        )
        inline, failed = self._post_inline(report, state) if history_available else (set(), 0)
        current = reported | carried
        # 讨论仍被这次报告的问题沿用时，它的旧指纹不算"未再报告"
        live = {state.findings[fp]["discussion"] for fp in reported if fp in state.findings}
        previous = state.previous
        history = PublishHistory(
            previous=set(previous),
            inline=inline | (set(state.findings) & current),
            not_reported=[
                item for fingerprint, item in previous.items()
                if fingerprint not in current and not item.get("resolved")
                and item.get("discussion") not in live
            ],
        )
        note_id = self._write_summary(
            mr.project_id, mr.mr_iid, note_id, self._summary_body(report, history, threads)
        )
        return {
            "success": True,
            "message": "GitLab 评论发布成功",
            "details": {
                "note_id": note_id,
                "inline_posted": len(inline),
                "inline_failed": failed,
                "updated": updated,
            },
        }

    @staticmethod
    def _summary_body(report: ReviewReport, history: PublishHistory | None, threads) -> str:
        marker = summary_marker(report.review_id, report.findings, threads)
        return f"{marker}\n\n{render_summary(report, history)}"

    def _load_state(self, project_id, mr_iid) -> tuple[_PublishedState, bool]:
        """只认机器人账号自己发的标记，防止他人伪造评论来屏蔽问题。"""
        state = _PublishedState()
        try:
            bot_id = self.gitlab.current_user_id
            discussions = self.gitlab.list_merge_request_discussions(project_id, mr_iid)
        except Exception as exc:
            logger.warning("[%s] 读取 MR 评论失败，本次只发布总结: %s", self.request_id, exc)
            return state, False
        for discussion in discussions:
            for note in discussion.get("notes", []):
                if note.get("system") or note.get("author", {}).get("id") != bot_id:
                    continue
                body = note.get("body", "")
                summary = parse_summary_marker(body)
                if summary is not None:
                    review_id, items = summary
                    if state.summary_review_id is None or review_id > state.summary_review_id:
                        state.summary_note_id = note["id"]
                        state.summary_review_id = review_id
                        state.summarized = {item["fp"]: item for item in items}
                    continue
                for finding in parse_findings_marker(body):
                    state.findings[finding["fp"]] = {
                        **finding,
                        "resolved": bool(note.get("resolved")),
                        "discussion": discussion.get("id"),
                    }
        # 恢复上一轮的沿用关系：总结里的新指纹指向讨论标记里的旧指纹
        for fp, item in state.summarized.items():
            thread = state.findings.get(item.get("thread"))
            if thread is not None and fp not in state.findings:
                state.findings[fp] = thread
        return state, True

    def _post_inline(self, report: ReviewReport, state: _PublishedState) -> tuple[set[str], int]:
        if report.revisions is None:
            return set(), 0
        threads = plan_threads(
            report.findings, state.findings, settings.REVIEW_MAX_INLINE_COMMENTS
        )
        comments = [
            _Comment(thread, render_inline_comment(thread, report.language),
                     self._position(report, thread[0]))
            for thread in threads
        ]
        if not comments:
            return set(), 0
        try:
            return self._submit_as_review(report, comments)
        except _ReviewUnavailable as exc:
            logger.info("[%s] 改为逐条发布行内评论: %s", self.request_id, exc)
            return self._submit_one_by_one(report, comments)

    @staticmethod
    def _position(report: ReviewReport, finding: Finding) -> dict:
        return {
            "position_type": "text",
            "base_sha": report.revisions.base_sha,
            "start_sha": report.revisions.start_sha,
            "head_sha": report.revisions.head_sha,
            **report.diff.get(finding.path).position(finding.side, finding.end_line),
        }

    def _submit_as_review(self, report, comments: list[_Comment]) -> tuple[set[str], int]:
        """先存成草稿再一次性发布，MR 上是一轮完整的 review，每个讨论仍可单独解决。"""
        mr = report.mr
        own, foreign = self._list_drafts(mr)
        if foreign:
            raise _ReviewUnavailable("账号在这个 MR 上还有其他未发布的草稿")
        # 上次中断留下的草稿，不删会随这次一起发出
        self._delete_drafts(mr, [draft["id"] for draft in own])

        drafted, draft_ids, failed = [], [], 0
        for comment in comments:
            try:
                created = self.gitlab.create_draft_note(
                    mr.project_id, mr.mr_iid, comment.body, comment.position
                )
            except Exception as exc:
                failed += 1
                logger.warning("[%s] 行内草稿创建失败: %s", self.request_id, exc)
                continue
            drafted.append(comment)
            draft_ids.append(created["id"])
        if not drafted:
            return set(), failed

        # 发布前再确认一次，账号本人在这期间新建的草稿不能被一起发出
        try:
            _, foreign = self._list_drafts(mr)
        except _ReviewUnavailable:
            foreign = 1
        if foreign:
            logger.info("[%s] 发布前出现了其他草稿，改为逐条发布", self.request_id)
            self._delete_drafts(mr, draft_ids)
            posted, retry_failed = self._submit_one_by_one(report, drafted)
            return posted, failed + retry_failed

        try:
            self.gitlab.publish_draft_notes(mr.project_id, mr.mr_iid)
        except Exception as exc:
            logger.warning("[%s] 批量发布草稿失败，改为逐条补发: %s", self.request_id, exc)
            return self._recover(report, drafted, draft_ids, failed)
        return set().union(*(comment.fingerprints for comment in drafted)), failed

    def _list_drafts(self, mr) -> tuple[list[dict], int]:
        """返回我们留下的草稿和其他草稿的数量。

        批量发布会发出账号的全部草稿，配置的若是个人令牌，里面可能有本人没写完的评审，
        所以只在草稿都是我们生成的时候才批量发布。
        """
        try:
            drafts = self.gitlab.list_draft_notes(mr.project_id, mr.mr_iid)
        except DraftNotesUnsupported as exc:
            raise _ReviewUnavailable("GitLab 不支持草稿评论") from exc
        except Exception as exc:
            raise _ReviewUnavailable(f"读取草稿失败: {exc}") from exc
        own = [draft for draft in drafts if parse_findings_marker(draft.get("note", ""))]
        return own, len(drafts) - len(own)

    def _delete_drafts(self, mr, draft_ids) -> None:
        for draft_id in draft_ids:
            try:
                self.gitlab.delete_draft_note(mr.project_id, mr.mr_iid, draft_id)
            except Exception as exc:
                logger.warning("[%s] 删除草稿 %s 失败: %s", self.request_id, draft_id, exc)

    def _recover(self, report, drafted, draft_ids, failed: int) -> tuple[set[str], int]:
        """批量发布失败时可能已发出一部分：删掉剩余草稿，只补发确实没发出去的。"""
        mr = report.mr
        self._delete_drafts(mr, draft_ids)
        state, readable = self._load_state(mr.project_id, mr.mr_iid)
        if not readable:
            # 不知道哪些已发出，宁可让问题留在总结里，也不重复发
            return set(), failed + len(drafted)
        published = set(state.findings)
        missing = [comment for comment in drafted if not comment.fingerprints <= published]
        posted, retry_failed = self._submit_one_by_one(report, missing)
        sent = set().union(*(c.fingerprints for c in drafted if c.fingerprints <= published))
        return sent | posted, failed + retry_failed

    def _submit_one_by_one(self, report, comments: list[_Comment]) -> tuple[set[str], int]:
        mr = report.mr
        posted: set[str] = set()
        failed = 0
        for comment in comments:
            try:
                self.gitlab.create_merge_request_discussion(
                    mr.project_id, mr.mr_iid, comment.body, comment.position
                )
            except Exception as exc:
                # 发不出去的问题会进入总结评论，不会丢
                failed += 1
                logger.warning("[%s] 行内评论发布失败: %s", self.request_id, exc)
                continue
            posted |= comment.fingerprints
        return posted, failed

    def _write_summary(self, project_id, mr_iid, note_id, body) -> int | None:
        if note_id is not None:
            try:
                self.gitlab.update_merge_request_note(project_id, mr_iid, note_id, body)
                return note_id
            except Exception as exc:
                logger.warning("[%s] 更新总结评论失败，改为新建: %s", self.request_id, exc)
        note = self.gitlab.post_merge_request_comment(project_id, mr_iid, body)
        if not note:
            raise RuntimeError("GitLab API 调用失败")
        return note.get("id")


def _carry_over(findings: list[Finding], state: _PublishedState) -> set[str]:
    """改动了问题所在的代码行时指纹会变；同一文件里标题相同的，仍算同一个问题。

    把旧记录挂到新指纹上，避免重复发讨论，也避免把它列进"本次未再报告"。
    返回被接续的旧指纹。
    """
    current = {finding.fingerprint for finding in findings}
    unmatched = {
        fp: item for fp, item in state.previous.items()
        if fp not in current and not item.get("resolved")
    }
    carried: set[str] = set()
    for finding in findings:
        if finding.fingerprint in state.findings:
            continue
        # 同一个问题沿用过的几个旧指纹共用一条讨论，按讨论合并成一个候选
        candidates: dict[str, list[str]] = {}
        for fp, item in unmatched.items():
            if (
                fp not in carried
                and _normalized(item.get("title", "")) == _normalized(finding.title)
                and str(item.get("location", "")).rsplit(":", 1)[0] == finding.path
            ):
                candidates.setdefault(item.get("discussion") or fp, []).append(fp)
        if len(candidates) != 1:
            # 同一文件里有多个同名问题时分不清是哪一个，宁可当成新问题
            continue
        old_fps = next(iter(candidates.values()))
        carried.update(old_fps)
        for records in (state.findings, state.summarized):
            record = next((records[fp] for fp in old_fps if fp in records), None)
            if record is not None:
                records[finding.fingerprint] = record
    return carried


def _normalized(text: str) -> str:
    return " ".join(text.split()).lower()

