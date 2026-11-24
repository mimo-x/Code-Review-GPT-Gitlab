"""IM 通知的摘要：只回答"要不要现在去看"。"""
from __future__ import annotations

from ..engines.base import SEVERITIES
from ..report import ReviewReport
from .labels import SEVERITY_ICONS, VERDICT_TONES, labels_for
from .sanitize import plain_message


def render_digest(report: ReviewReport) -> str:
    """各渠道的 Markdown 能力不同，这里只用纯文本和空行分段。"""
    labels = labels_for(report.language)
    separator = labels["separator"]
    counts = [
        f"{SEVERITY_ICONS[severity]} {labels['severity'][severity]} {report.count(severity)}"
        for severity in SEVERITIES
        if report.count(severity)
    ]
    lines = [
        f"{labels['digest_verdict']}{separator}{labels['verdict'][report.verdict]}",
        f"{labels['digest_issues']}{separator}{' · '.join(counts) or labels['digest_none']}",
    ]
    if report.findings:
        top = report.findings[0]
        lines.append(
            f"{labels['digest_top']}{separator}{plain_message(top.title)}"
            f"（{plain_message(top.location)}）"
        )
    if report.mr.url:
        lines.append(f"{labels['digest_link']}{separator}{report.mr.url}")
    return "\n\n".join(lines)


def verdict_summary(report: ReviewReport) -> dict[str, str]:
    labels = labels_for(report.language)
    return {"label": labels["verdict"][report.verdict], "tone": VERDICT_TONES[report.verdict]}
