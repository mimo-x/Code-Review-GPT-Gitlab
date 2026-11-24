"""一次 MR 审查的完整流水线。"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import replace

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.common.logging_utils import TimerContext, get_logger
from apps.llm.models import LLMConfig
from apps.response.notification_dispatcher import NotificationDispatcher
from apps.webhook.models import MergeRequestReview, ProjectWebhookEventPrompt
from apps.webhook.services import ProjectService

from .diff_index import DiffIndex
from .engines import EngineError, engine_for
from .engines.base import MergeRequestInfo, ReviewEngine, ReviewRequest, ReviewResult, Revisions
from .postprocess import finalize_findings
from .rendering import render_digest, render_summary, verdict_summary
from .report import ReviewReport
from .scope import ReviewScope
from .services import GitlabService
from .workspace import RepositoryWorkspace, WorkspaceError

logger = logging.getLogger(__name__)


class ReviewAborted(Exception):
    """可预期的失败，消息直接写入审查记录。"""


def run(review_id: int, payload: dict, matched_rule=None) -> None:
    """后台线程入口。"""
    try:
        review = MergeRequestReview.objects.get(pk=review_id)
    except MergeRequestReview.DoesNotExist:
        logger.error("MergeRequestReview %s not found when starting review processing", review_id)
        return

    request_id = review.request_id or str(uuid.uuid4())
    log = get_logger("mr_review", request_id)
    log.log_thread_start(review.project_id, review.merge_request_iid)
    try:
        _execute(review, payload, matched_rule, request_id, log)
    except ReviewAborted as exc:
        log.error(f"审查失败: {exc}")
        _mark_failed(review, str(exc), log)
    except Exception as exc:
        log.log_error_with_context(exc, context={
            "operation": "mr_review_processing",
            "project_id": review.project_id,
            "mr_iid": review.merge_request_iid,
        })
        _mark_failed(review, str(exc), log)


def _execute(review, payload, matched_rule, request_id, log) -> None:
    review.status = "processing"
    review.save(update_fields=["status", "updated_at"])

    gitlab = _connect_gitlab(request_id)
    with TimerContext(log, "get_mr_changes"):
        response = gitlab.get_merge_request_changes(review.project_id, review.merge_request_iid)
    if not response:
        raise ReviewAborted("未找到MR变更信息")

    all_changes = response.get("changes", [])
    scope = ReviewScope.for_project(review.project_id)
    changes, skipped_paths = scope.split(all_changes)
    if skipped_paths:
        log.info(f"按项目配置排除 {len(skipped_paths)} 个文件")
    if all_changes and not changes:
        _complete_without_review(review, len(all_changes), log)
        return
    mr = _merge_request_info(review, payload, changes)
    log.info(f"获取到 {mr.file_count} 个文件变更，{mr.changes_count} 行代码变更")

    llm_config = LLMConfig.objects.filter(is_active=True).first()
    if llm_config is None:
        raise ReviewAborted("未找到有效的 LLM 配置")
    engine = engine_for(llm_config, request_id)
    log.info(f"审查引擎: {engine.kind} (provider={llm_config.provider})")

    revisions = _revisions(gitlab, review, response)
    request = ReviewRequest(
        request_id=request_id,
        mr=mr,
        changes=changes,
        language=settings.REVIEW_OUTPUT_LANGUAGE,
        revisions=revisions,
        custom_prompt=_custom_prompt(review.project_id, matched_rule, mr, log),
        skipped_paths=skipped_paths,
    )

    started = time.monotonic()
    result = _run_engine(engine, request, payload, gitlab, log)
    duration = time.monotonic() - started
    log.log_llm_call(provider=result.provider, model=result.model, success=True, duration=duration)

    diff = DiffIndex(changes)
    report = ReviewReport(
        review_id=review.pk,
        mr=mr,
        result=result,
        findings=finalize_findings(result.findings, diff, scope),
        diff=diff,
        revisions=revisions,
        language=request.language,
        skipped_paths=skipped_paths,
    )
    _save_result(review, report, changes)
    log.log_report_generation(
        is_mock=review.is_mock, file_count=mr.file_count, success=True,
        findings=len(report.findings),
    )
    publish_error = _publish_error(_notify(review, report, request_id, log))
    if publish_error:
        raise ReviewAborted(f"审查已完成，但发布到 GitLab 失败: {publish_error}")
    _mark_completed(review)


def _connect_gitlab(request_id: str) -> GitlabService:
    try:
        return GitlabService(request_id=request_id)
    except ImproperlyConfigured as exc:
        raise ReviewAborted(str(exc)) from exc


def _merge_request_info(review, payload, changes) -> MergeRequestInfo:
    project = payload.get("project", {})
    attributes = payload.get("object_attributes", {})
    return MergeRequestInfo(
        project_id=review.project_id,
        mr_iid=review.merge_request_iid,
        project_name=project.get("name", "未知项目"),
        title=attributes.get("title", "未知MR"),
        author=attributes.get("author", {}).get("name", "未知作者"),
        description=attributes.get("description") or "",
        url=attributes.get("url", ""),
        source_branch=attributes.get("source_branch", ""),
        target_branch=attributes.get("target_branch", "main"),
        file_count=len(changes),
        changes_count=sum(change.get("diff", "").count("\n") for change in changes),
    )


def _revisions(gitlab, review, response) -> Revisions | None:
    """优先用和 diff 同一次响应返回的 diff_refs，保证 SHA 和审查内容一致。"""
    refs = response.get("diff_refs") or gitlab.get_latest_diff_refs(
        review.project_id, review.merge_request_iid
    )
    if not refs or not all(refs.get(key) for key in ("base_sha", "start_sha", "head_sha")):
        return None
    return Revisions(refs["base_sha"], refs["start_sha"], refs["head_sha"])


def _custom_prompt(project_id, matched_rule, mr: MergeRequestInfo, log) -> str | None:
    if not matched_rule:
        return None
    try:
        config = ProjectWebhookEventPrompt.objects.filter(
            project__project_id=project_id,
            event_rule=matched_rule,
            use_custom=True,
        ).first()
        if config and config.custom_prompt:
            log.info(f"使用项目自定义 Prompt (Event: {matched_rule.name})")
            return config.render_prompt(mr.as_context())
    except Exception as exc:
        log.warning(f"获取自定义 Prompt 失败: {exc}，使用系统默认")
    return None


def _run_engine(engine: ReviewEngine, request: ReviewRequest, payload, gitlab, log) -> ReviewResult:
    try:
        if not engine.needs_worktree:
            return engine.review(request)
        if request.revisions is None:
            raise ReviewAborted("仓库准备失败: 未能获取 MR 的提交信息")
        clone_url = ProjectService.build_clone_url(
            payload.get("project", {}), base_url=getattr(gitlab, "server_url", None)
        )
        workspace = RepositoryWorkspace(request_id=request.request_id)
        with workspace.checkout(
            request.mr.project_id, clone_url, gitlab.private_token, request.revisions,
            request.mr.mr_iid, request.mr.target_branch,
        ) as worktree:
            return engine.review(replace(request, worktree=worktree))
    except WorkspaceError as exc:
        raise ReviewAborted(f"仓库准备失败: {exc}") from exc
    except EngineError as exc:
        raise ReviewAborted(str(exc)) from exc


def _save_result(review, report: ReviewReport, changes) -> None:
    review.review_content = render_summary(report)
    review.review_score = None
    review.files_reviewed_list = [change.get("new_path") for change in changes]
    review.total_files = report.mr.file_count
    review.llm_provider = report.result.provider
    review.llm_model = report.result.model
    review.is_mock = bool(report.result.metadata.get("is_mock"))
    review.save()


def _complete_without_review(review, file_count: int, log) -> None:
    """所有变更都被排除时不调用引擎，也不产生费用。"""
    log.info("所有变更文件都在排除范围内，跳过审查")
    review.review_content = f"本次 {file_count} 个变更文件都在排除范围内，未进行审查。"
    review.files_reviewed_list = []
    review.total_files = 0
    _mark_completed(review)


def _mark_completed(review) -> None:
    review.status = "completed"
    review.completed_at = timezone.now()
    review.save()


def _notify(review, report: ReviewReport, request_id: str, log) -> dict:
    report_data = {
        "content": render_digest(report),
        "report": report,
        "verdict": verdict_summary(report),
    }
    with TimerContext(log, "notification_dispatch"):
        outcome = NotificationDispatcher(request_id=request_id).dispatch(
            report_data, report.mr.as_context(), project_id=review.project_id
        )
    review.notification_sent = outcome.get("success", False)
    review.notification_result = json.dumps(outcome, ensure_ascii=False)
    review.save(update_fields=["notification_sent", "notification_result", "updated_at"])
    log.log_notification_dispatch(
        total_channels=outcome.get("total_channels", 0),
        success_channels=outcome.get("success_channels", 0),
        failed_channels=outcome.get("failed_channels", 0),
    )
    return outcome


def _publish_error(outcome: dict) -> str | None:
    """MR 评论是审查的交付物，发布失败不能算完成；IM 通知失败只记录。"""
    if "results" not in outcome:
        return None if outcome.get("success") else outcome.get("message", "通知分发失败")
    for result in outcome["results"]:
        if result["channel"] == "gitlab" and not result["success"]:
            return result.get("message") or "未知错误"
    return None


def _mark_failed(review, message: str, log) -> None:
    try:
        review.status = "failed"
        review.error_message = message
        review.save(update_fields=["status", "error_message", "updated_at"])
    except Exception as exc:
        log.log_error_with_context(exc, context={
            "operation": "save_failed_review",
            "review_id": review.pk,
            "original_error": message,
        })
