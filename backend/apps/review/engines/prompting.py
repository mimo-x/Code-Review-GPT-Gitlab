"""组装发给模型的审查提示词。"""
from __future__ import annotations

from django.conf import settings

from .base import ReviewRequest
from .output import output_instructions

_MAX_LISTED_SKIPPED_PATHS = 50


def build_review_prompt(request: ReviewRequest, workspace_note: str = "") -> str:
    """自定义 Prompt 只替换审查要求；MR 信息、diff 和输出契约始终由平台提供。"""
    mr = request.mr
    parts = [(request.custom_prompt or settings.GPT_MESSAGE).strip()]
    if workspace_note:
        parts.append(workspace_note)
        if request.skipped_paths:
            parts.append(_skipped_note(request.skipped_paths))
    info = [
        "## MR 信息",
        f"- 标题: {mr.title}",
        f"- 作者: {mr.author}",
        f"- 分支: {mr.source_branch} → {mr.target_branch}",
    ]
    if mr.description:
        info.append(f"- 描述: {mr.description}")
    parts.append("\n".join(info))
    parts.append(f"## 代码变更\n{format_changes(request.changes)}")
    parts.append(output_instructions(request.language))
    return "\n\n".join(parts)


def _skipped_note(paths: tuple[str, ...]) -> str:
    listed = "\n".join(f"- {path}" for path in paths[:_MAX_LISTED_SKIPPED_PATHS])
    hidden = len(paths) - _MAX_LISTED_SKIPPED_PATHS
    more = f"\n- 以及另外 {hidden} 个文件" if hidden > 0 else ""
    return f"以下变更文件已被项目配置排除，可以读取作为上下文，但不要针对它们报告问题：\n{listed}{more}"


def format_changes(changes: list[dict]) -> str:
    sections = []
    for change in changes:
        diff = change.get("diff", "")
        if diff:
            path = change.get("new_path") or change.get("old_path", "")
            sections.append(f"### 文件: {path}\n```diff\n{diff}\n```")
    return "\n\n".join(sections)
