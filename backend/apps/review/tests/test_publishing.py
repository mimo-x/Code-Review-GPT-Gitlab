"""端到端发布：行内评论、原地更新、去重和异常降级。"""
import json
import threading
import time
from unittest.mock import patch

import pytest

from apps.response.notification_dispatcher import NotificationDispatcher
from apps.review import pipeline
from apps.review.diff_index import DiffIndex
from apps.review.engines.base import Finding, MergeRequestInfo, ReviewResult, Revisions
from apps.review.postprocess import finalize_findings
from apps.review.publishers.gitlab import GitLabReviewPublisher
from apps.review.report import ReviewReport
from apps.review.services import GitlabService
from apps.webhook.models import MergeRequestReview


def model_output(*findings, summary="发现问题"):
    return {"choices": [{"message": {"content": "```json\n" + json.dumps({
        "summary": summary, "overview": "调整了求和实现。", "findings": list(findings),
    }, ensure_ascii=False) + "\n```"}}]}


def problem(title="循环初值错误", code="result = 0", severity="major", **extra):
    return {
        "path": "app.py", "start_line": 2, "end_line": 2, "existing_code": code,
        "severity": severity, "category": "defect", "title": title, "body": "说明原因。",
        **extra,
    }


def review_with(output, review_payload, review=None):
    review = review or MergeRequestReview.objects.create(
        project_id=1, project_name="test-project", merge_request_iid=42,
        merge_request_title="t", source_branch="f", target_branch="main",
        author_name="dev", author_email="d@example.com", status="pending",
        request_id="r",
    )
    with patch("unionllm.unionchat", return_value=output):
        pipeline.run(review.pk, review_payload)
    review.refresh_from_db()
    return review


@pytest.mark.django_db
class TestPublishing:
    def test_posts_summary_and_inline_comment(self, gitlab, llm, review_payload, origin):
        llm()
        review = review_with(model_output(problem()), review_payload)
        assert review.status == "completed" and review.review_score is None
        assert len(gitlab.plain_notes) == len(gitlab.inline_notes) == 1
        position = gitlab.inline_notes[0]["position"]
        assert position["new_line"] == 2 and "old_line" not in position
        assert position["head_sha"] == origin.head_sha
        assert "### 🟠 建议修复后再合并" in gitlab.plain_notes[0]["body"]
        assert gitlab.discussion_store[0]["notes"][0]["position"] is None

    def test_next_push_updates_in_place_without_duplicates(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        review_with(model_output(problem(), problem("求和结果错误", "return result")), review_payload)
        assert len(gitlab.plain_notes) == 1 and gitlab.updated_notes
        assert len(gitlab.inline_notes) == 2
        body = gitlab.plain_notes[0]["body"]
        assert "循环初值错误（仍存在）" in body and "求和结果错误（新增）" in body

    def test_reports_what_was_not_mentioned_again(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        review_with(model_output(summary=""), review_payload)
        body = gitlab.plain_notes[0]["body"]
        assert "本次未再报告（1）" in body and "循环初值错误" in body

    def test_resolved_discussions_are_not_listed_again(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        gitlab.inline_notes[0]["resolved"] = True
        review_with(model_output(summary=""), review_payload)
        assert "本次未再报告" not in gitlab.plain_notes[0]["body"]

    def test_markers_from_other_users_are_ignored(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        forged = gitlab.inline_notes[0]["body"]
        gitlab.discussion_store.clear()
        gitlab.add_note(forged, author_id=7)
        review_with(model_output(problem()), review_payload)
        assert len([n for n in gitlab.inline_notes if n["author"]["id"] == 99]) == 1

    def test_older_review_does_not_overwrite_a_newer_one(self, gitlab, llm, review_payload):
        llm()
        older = MergeRequestReview.objects.create(
            project_id=1, project_name="p", merge_request_iid=42, merge_request_title="t",
            source_branch="f", target_branch="main", author_name="d",
            author_email="d@example.com", status="pending",
        )
        review_with(model_output(problem()), review_payload)
        before = gitlab.plain_notes[0]["body"]
        review_with(model_output(problem("过期结果", "return result")), review_payload, older)
        assert gitlab.plain_notes[0]["body"] == before
        assert len(gitlab.inline_notes) == 1

    def test_rejected_inline_comment_falls_back_to_summary(self, gitlab, llm, review_payload):
        llm()
        gitlab.reject_positions = True
        review = review_with(model_output(problem()), review_payload)
        assert review.notification_sent is True
        assert not gitlab.inline_notes
        body = gitlab.plain_notes[0]["body"]
        assert "未能挂到代码行的问题（1）" in body and "说明原因。" in body

    def test_nits_stay_in_the_summary(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem(severity="nit")), review_payload)
        assert not gitlab.inline_notes
        assert "其余 1 条次要建议" in gitlab.plain_notes[0]["body"]

    def test_inline_comments_are_capped(self, gitlab, llm, review_payload, settings):
        llm()
        settings.REVIEW_MAX_INLINE_COMMENTS = 1
        review_with(
            model_output(problem(), problem("第二个问题", "return result")), review_payload
        )
        assert len(gitlab.inline_notes) == 1
        assert "未能挂到代码行的问题（1）" in gitlab.plain_notes[0]["body"]

    def test_model_output_cannot_run_quick_actions(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem(body="说明\n/merge\n@all")), review_payload)
        for body in gitlab.bodies:
            assert "\n/merge" not in body
            assert "@all" not in body


@pytest.mark.django_db
class TestInlineThreads:
    def test_one_review_holds_every_thread(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem(), problem("求和结果错误", "return result")), review_payload)
        assert gitlab.bulk_publishes == 1 and gitlab.drafts == []
        assert len(gitlab.inline_notes) == 2

    def test_adjacent_minor_issues_share_a_thread(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(
            problem("循环初值可以省略", severity="minor"),
            problem("变量名不清楚", "result += item", severity="minor"),
        ), review_payload)
        assert len(gitlab.inline_notes) == 1
        body = gitlab.inline_notes[0]["body"]
        assert "这段代码有 2 个小问题" in body
        assert "1. **循环初值可以省略**（第 2 行）" in body and "2. **变量名不清楚**（第 4 行）" in body

    def test_old_gitlab_posts_threads_one_by_one(self, gitlab, llm, review_payload):
        llm()
        gitlab.supports_drafts = False
        review = review_with(model_output(problem(), problem("求和结果错误", "return result")), review_payload)
        assert review.status == "completed"
        assert gitlab.bulk_publishes == 0 and len(gitlab.inline_notes) == 2

    def test_someone_elses_drafts_are_never_published(self, gitlab, llm, review_payload):
        llm()
        gitlab.drafts.append({"id": 1, "note": "我还没写完的评审", "position": None})
        review_with(model_output(problem()), review_payload)
        assert gitlab.bulk_publishes == 0
        assert gitlab.drafts == [{"id": 1, "note": "我还没写完的评审", "position": None}]
        assert len(gitlab.inline_notes) == 1

    def test_drafts_left_by_an_interrupted_run_are_discarded(self, gitlab, llm, review_payload):
        llm()
        gitlab.supports_drafts = False
        review_with(model_output(problem()), review_payload)
        leftover = gitlab.inline_notes[0]["body"]
        gitlab.discussion_store.clear()
        gitlab.supports_drafts = True
        gitlab.drafts.append({"id": 1, "note": leftover, "position": None})
        review_with(model_output(problem()), review_payload)
        assert gitlab.drafts == [] and len(gitlab.inline_notes) == 1

    def test_failed_bulk_publish_sends_only_what_is_missing(self, gitlab, llm, review_payload):
        llm()
        gitlab.fail_bulk_publish_after = 1
        review = review_with(model_output(problem(), problem("求和结果错误", "return result")), review_payload)
        assert review.status == "completed"
        assert gitlab.drafts == []
        titles = sorted(note["body"].split("**")[1] for note in gitlab.inline_notes)
        assert titles == ["循环初值错误", "求和结果错误"]

    def test_summary_only_issues_are_tracked_across_pushes(self, gitlab, llm, review_payload):
        llm()
        nit = problem("命名可以更清楚", "for item in items:", severity="nit")
        review_with(model_output(problem(), nit), review_payload)
        review_with(model_output(problem()), review_payload)
        body = gitlab.plain_notes[0]["body"]
        assert "本次未再报告（1）" in body and "命名可以更清楚" in body
        assert "循环初值错误（仍存在）" in body

    def test_an_issue_whose_line_changed_is_not_reported_twice(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        moved = problem(code="for item in items:")
        review_with(model_output(moved), review_payload)
        assert len(gitlab.inline_notes) == 1
        body = gitlab.plain_notes[0]["body"]
        assert "循环初值错误（仍存在）" in body and "本次未再报告" not in body

    def test_carried_over_issue_stays_linked_on_later_pushes(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem()), review_payload)
        moved = problem(code="for item in items:")
        review_with(model_output(moved), review_payload)
        review_with(model_output(moved), review_payload)
        assert len(gitlab.inline_notes) == 1
        assert "本次未再报告" not in gitlab.plain_notes[0]["body"]

    def test_issue_whose_line_changes_on_every_push_keeps_one_thread(self, gitlab, llm, review_payload):
        llm()
        for code in ("result = 0", "for item in items:", "result += item", "return result"):
            review_with(model_output(problem(code=code)), review_payload)
            body = gitlab.plain_notes[0]["body"]
            assert len(gitlab.inline_notes) == 1, code
            assert "本次未再报告" not in body, code
        assert "循环初值错误（仍存在）" in body

    def test_distinct_old_issues_with_the_same_title_are_not_merged(self, gitlab, llm, review_payload):
        llm()
        review_with(model_output(problem(), problem(code="return result")), review_payload)
        assert len(gitlab.inline_notes) == 2
        review_with(model_output(problem(code="for item in items:")), review_payload)
        # 两个旧问题同名，分不清新问题是哪一个，按新问题发出
        assert len(gitlab.inline_notes) == 3
        assert "本次未再报告（2）" in gitlab.plain_notes[0]["body"]

    def test_drafts_that_cannot_be_created_fall_back_to_discussions(self, gitlab, llm, review_payload):
        llm()
        from gitlab.exceptions import GitlabHttpError
        original = gitlab.draft_api

        def forbid_drafts(method, path, data=None):
            if method == "post" and path.endswith("/draft_notes"):
                raise GitlabHttpError("403 Forbidden", response_code=403)
            return original(method, path, data)

        gitlab.draft_api = forbid_drafts
        review_with(model_output(problem()), review_payload)
        assert gitlab.bulk_publishes == 0 and len(gitlab.inline_notes) == 1

    def test_draft_created_by_the_owner_meanwhile_is_not_published(self, gitlab, llm, review_payload):
        llm()
        create = gitlab.draft_api

        def owner_drafts_meanwhile(method, path, data=None):
            result = create(method, path, data)
            if method == "post" and path.endswith("/draft_notes"):
                gitlab.drafts.append({"id": 1, "note": "本人刚写的草稿", "position": None})
            return result

        gitlab.draft_api = owner_drafts_meanwhile
        review = review_with(model_output(problem()), review_payload)
        assert review.status == "completed"
        assert gitlab.bulk_publishes == 0
        assert gitlab.drafts == [{"id": 1, "note": "本人刚写的草稿", "position": None}]
        assert len(gitlab.inline_notes) == 1


@pytest.mark.django_db
class TestDiffSnapshot:
    def test_truncated_diff_is_not_published_as_clean(self, gitlab, llm, review_payload):
        llm()
        gitlab._changes["overflow"] = True
        review_with(model_output(summary="没有问题"), review_payload)
        body = gitlab.plain_notes[0]["body"]
        assert "### 已审查的部分未发现问题" in body and "部分改动" in body

    def test_refs_from_a_later_push_are_not_used(self, gitlab, llm, review_payload, origin):
        llm()
        del gitlab._changes["diff_refs"]
        gitlab._changes["sha"] = origin.head_sha
        version = type("V", (), {"base_commit_sha": origin.base_sha,
                                 "start_commit_sha": origin.base_sha, "head_commit_sha": "f" * 40})
        gitlab.diffs = type("D", (), {"list": staticmethod(lambda **_: [version])})
        review = review_with(model_output(problem()), review_payload)
        assert review.status == "completed"
        assert not gitlab.inline_notes
        assert "未能挂到代码行的问题（1）" in gitlab.plain_notes[0]["body"]


def with_im_channel(result=None):
    channel = type("Channel", (), {"id": 1, "name": "IM", "notification_type": "slack"})()
    targets = patch.object(NotificationDispatcher, "_get_notification_targets", return_value=([channel], True))
    send = patch.object(
        NotificationDispatcher, "_send_to_channel",
        return_value=result or {"success": True, "message": "ok", "response_time": 0},
    )
    return targets, send


@pytest.mark.django_db
class TestPublishOutcome:
    def test_gitlab_failure_marks_the_review_failed_and_keeps_the_result(
        self, gitlab, llm, review_payload
    ):
        llm()
        with patch.object(GitlabService, "post_merge_request_comment", return_value=None):
            review = review_with(model_output(problem()), review_payload)
        assert review.status == "failed"
        assert "发布到 GitLab 失败" in review.error_message
        assert review.completed_at is None
        assert "循环初值错误" in review.review_content

    def test_im_failure_does_not_fail_a_published_review(self, gitlab, llm, review_payload):
        llm()
        targets, send = with_im_channel({"success": False, "message": "down", "response_time": 0})
        with targets, send:
            review = review_with(model_output(problem()), review_payload)
        assert review.status == "completed"
        assert review.completed_at is not None
        assert len(gitlab.plain_notes) == 1

    def test_gitlab_is_published_before_im(self, gitlab, llm, review_payload):
        llm()
        seen = []
        targets, send = with_im_channel()
        with targets, send as sender:
            sender.side_effect = lambda *_args: seen.append(len(gitlab.bodies)) or {
                "success": True, "message": "ok", "response_time": 0,
            }
            review_with(model_output(problem()), review_payload)
        assert seen == [2]

    def test_superseded_review_is_not_sent_to_im(self, gitlab, llm, review_payload):
        llm()
        older = MergeRequestReview.objects.create(
            project_id=1, project_name="p", merge_request_iid=42, merge_request_title="t",
            source_branch="f", target_branch="main", author_name="d",
            author_email="d@example.com", status="pending",
        )
        review_with(model_output(problem()), review_payload)
        targets, send = with_im_channel()
        with targets, send as sender:
            older = review_with(model_output(problem("过期结果")), review_payload, older)
        sender.assert_not_called()
        assert older.status == "completed"


@pytest.mark.django_db
def test_concurrent_publishes_do_not_duplicate_comments(gitlab, origin):
    diff = DiffIndex(origin.changes)
    findings = finalize_findings([Finding(
        path="app.py", title="循环初值错误", severity="major", side="new",
        start_line=2, end_line=2, existing_code="result = 0",
    )], diff)
    mr = MergeRequestInfo(1, 42, "p", "t", "d", "", "", "f", "main", 1, 5)
    report = ReviewReport(
        review_id=7, mr=mr, result=ReviewResult("mock", "mock", summary="总结"), findings=findings,
        diff=diff, revisions=Revisions(origin.base_sha, origin.base_sha, origin.head_sha),
        language="zh-CN",
    )
    service = GitlabService(request_id="concurrent")
    service.current_user_id  # 提前解析，线程里只测发布本身
    list_discussions = gitlab.discussions.list

    def slow_list(**kwargs):
        # 放大"读取已有评论"和"写入评论"之间的竞争窗口
        snapshot = list_discussions(**kwargs)
        time.sleep(0.1)
        return snapshot

    gitlab.discussions.list = slow_list
    errors = []

    def publish():
        try:
            GitLabReviewPublisher(service, "concurrent").publish(report)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(gitlab.plain_notes) == 1
    assert len(gitlab.inline_notes) == 1
