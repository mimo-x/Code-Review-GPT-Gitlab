"""GitLab 上的两种评论：MR 顶部的总结和代码行上的讨论。"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote

from ..engines.base import Finding
from ..report import ReviewReport, Verdict
from .labels import SEVERITY_ICONS, VERDICT_ICONS, labels_for
from .markers import findings_marker
from .sanitize import code_span, sanitize, single_line, table_cell

_HEADLINE_SEVERITIES = ("critical", "major")


@dataclass
class PublishHistory:
    """这次发布和历史评论的对照；首次审查时 previous 为空。"""
    previous: set[str] = field(default_factory=set)
    inline: set[str] = field(default_factory=set)
    not_reported: list[dict] = field(default_factory=list)


def render_inline_comment(findings: list[Finding], language: str) -> str:
    """一条行内讨论：一个问题，或同一段代码上相邻的几个次要问题。"""
    labels = labels_for(language)
    marker = findings_marker(findings)
    icon = SEVERITY_ICONS[findings[0].severity]
    if len(findings) == 1:
        finding = findings[0]
        parts = [marker, f"{icon} **{single_line(finding.title)}**"]
        if finding.body:
            parts.append(sanitize(finding.body))
        return "\n\n".join(parts)

    items = []
    for number, finding in enumerate(findings, 1):
        item = f"{number}. **{single_line(finding.title)}**（{_lines(finding, labels)}）"
        if finding.body:
            item += labels["separator"] + sanitize(finding.body).replace("\n", "\n   ")
        items.append(item)
    title = labels["group_title"].format(count=len(findings))
    return "\n\n".join([marker, f"{icon} **{title}**", "\n".join(items)])


def _lines(finding: Finding, labels: dict) -> str:
    if finding.start_line and finding.start_line != finding.end_line:
        text = labels["lines"].format(start=finding.start_line, end=finding.end_line)
    else:
        text = labels["line"].format(line=finding.end_line)
    return labels["old_prefix"] + text if finding.side == "old" else text


def render_summary(report: ReviewReport, history: PublishHistory | None = None) -> str:
    """第一屏只回答"能不能合、先看哪里"，其余内容折叠。"""
    labels = labels_for(report.language)
    verdict = report.verdict
    parts = [f"### {VERDICT_ICONS[verdict]}{labels['verdict'][verdict]}"]

    if verdict is Verdict.UNSTRUCTURED:
        parts += [labels["unstructured_hint"], sanitize(report.result.summary)]
    else:
        if verdict is not Verdict.CLEAN and report.result.summary:
            parts.append(sanitize(report.result.summary))
        parts += _render_findings(report, history, labels)

    if history and history.not_reported:
        parts.append(_render_not_reported(history.not_reported, labels))
    parts.append(_footer(report, labels))
    return "\n\n".join(parts)


def _render_findings(report, history, labels) -> list[str]:
    """表格列出最该先看的一档问题：有 🔴🟠 时只列它们，否则列 🟡。"""
    findings = report.findings
    tier = _HEADLINE_SEVERITIES if any(
        f.severity in _HEADLINE_SEVERITIES for f in findings
    ) else ("minor",)
    headline = [f for f in findings if f.severity in tier]
    rest = [f for f in findings if f.severity not in tier]
    delivered = _delivered(findings, history)

    parts = []
    if headline:
        parts.append(_render_table(headline, report, history, labels))
    unanchored = [f for f in headline if f.fingerprint not in delivered]
    if unanchored:
        title = f"{labels['undelivered']}（{len(unanchored)}）"
        parts.append(_details(title, _render_issue_list(unanchored, report, labels, set())))
    if rest:
        title = labels["more"].format(count=len(rest))
        parts.append(_details(title, _render_issue_list(rest, report, labels, delivered)))
    return parts


def _delivered(findings, history) -> set[str]:
    """已经有行内讨论的问题；没有发布记录时，按能否挂到改动行估计。"""
    if history is not None:
        return history.inline
    return {f.fingerprint for f in findings if f.in_diff and f.severity != "nit"}


def _render_table(findings, report, history, labels) -> str:
    rows = [f"|  | {labels['col_issue']} | {labels['col_location']} |", "| --- | --- | --- |"]
    for finding in findings:
        issue = table_cell(finding.title)
        if history and history.previous:
            status = "persisted" if finding.fingerprint in history.previous else "new"
            issue = f"{issue}（{labels[status]}）"
        location = _location(finding, report, labels)
        rows.append(f"| {SEVERITY_ICONS[finding.severity]} | {issue} | {location} |")
    return "\n".join(rows)


def _location(finding: Finding, report: ReviewReport, labels: dict) -> str:
    code = code_span(finding.location)
    if not finding.in_diff:
        return f"{code}（{labels['not_located']}）"
    url = _blob_url(finding, report)
    return f"[{code}]({url})" if url else code


def _blob_url(finding: Finding, report: ReviewReport) -> str | None:
    project_url = report.mr.project_web_url
    if not project_url or report.revisions is None:
        return None
    sha = report.revisions.base_sha if finding.side == "old" else report.revisions.head_sha
    return f"{project_url}/-/blob/{sha}/{quote(finding.path)}#L{finding.end_line}"


def _render_issue_list(findings, report, labels, delivered: set[str]) -> str:
    """有行内讨论的只给位置；没有的要带上说明，内容不能丢。"""
    items = []
    for finding in findings:
        icon = SEVERITY_ICONS[finding.severity]
        item = f"- {icon} **{single_line(finding.title)}** — {_location(finding, report, labels)}"
        if finding.body and finding.fingerprint not in delivered:
            item += "\n\n  " + sanitize(finding.body).replace("\n", "\n  ")
        items.append(item)
    return "\n".join(items)


def _render_not_reported(items: list[dict], labels: dict) -> str:
    lines = [labels["not_reported_hint"], ""]
    for item in items:
        icon = SEVERITY_ICONS.get(item.get("severity"), SEVERITY_ICONS["minor"])
        location = code_span(str(item.get("location", "")))
        lines.append(f"- {icon} {single_line(str(item.get('title', '')))} — {location}")
    return _details(f"{labels['not_reported']}（{len(items)}）", "\n".join(lines))


def _footer(report: ReviewReport, labels: dict) -> str:
    items = [labels["reviewed_files"].format(count=report.mr.file_count)]
    if report.revisions:
        items.append(labels["at_commit"].format(commit=_commit_link(report)))
    if report.skipped_paths:
        items.append(labels["skipped_files"].format(count=len(report.skipped_paths)))
    return f"<sub>{' · '.join(items)}</sub>"


def _commit_link(report: ReviewReport) -> str:
    sha = report.revisions.head_sha
    project_url = report.mr.project_web_url
    return f"[`{sha[:8]}`]({project_url}/-/commit/{sha})" if project_url else f"`{sha[:8]}`"


def _details(title: str, body: str) -> str:
    return f"<details>\n<summary>{title}</summary>\n\n{body}\n\n</details>"
