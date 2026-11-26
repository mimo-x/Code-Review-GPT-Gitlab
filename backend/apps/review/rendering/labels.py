"""用户可见文案。严重程度的圆点是输出里唯一保留的 emoji，除结论标题外都放在小号标签里。"""
from __future__ import annotations

from ..report import Verdict

SEVERITY_ICONS = {"critical": "🔴", "major": "🟠", "minor": "🟡", "nit": "⚪"}

_LABELS = {
    "zh-CN": {
        "severity": {"critical": "严重", "major": "重要", "minor": "一般", "nit": "轻微"},
        "verdict": {
            Verdict.CHANGES_CRITICAL: "建议修复后再合并",
            Verdict.CHANGES_MAJOR: "建议修复后再合并",
            Verdict.ATTENTION: "可以合并，有几处建议",
            Verdict.CLEAN: "未发现需要处理的问题",
            Verdict.PARTIAL: "已审查的部分未发现问题",
            Verdict.INCOMPLETE: "审查未完成",
            Verdict.UNSTRUCTURED: "审查完成",
        },
        "separator": "：",
        "col_severity": "级别", "col_issue": "问题", "col_location": "位置",
        "new": "新增", "persisted": "仍存在", "not_located": "未定位到改动行",
        "more": "其余 {count} 条次要建议", "undelivered": "未能挂到代码行的问题",
        "not_reported": "本次未再报告",
        "not_reported_hint": "模型这次没有再提到这些问题，不代表它们已经修复。",
        "unstructured_hint": "模型没有返回结构化结果，以下是它的原始审查内容。",
        "reviewed_files": "已审查 {count} 个文件", "at_commit": "提交 {commit}",
        "planned_files": "计划审查 {count} 个文件",
        "failed_investigations": "{count} 项调查失败。下方只展示已取得的结果。",
        "skipped_files": "跳过 {count} 个文件",
        "truncated": "GitLab 只返回了部分改动，没返回的部分这次没有审查。",
        "truncated_positions": "GitLab 只返回了部分改动，缺少差异位置的问题会列在总结中。",
        "digest_verdict": "结论", "digest_issues": "问题", "digest_top": "最需要关注",
        "digest_link": "查看 MR", "digest_none": "无",
        "condition": "触发条件", "also_at": "同样的问题还出现在", "list_separator": "、",
    },
    "en": {
        "severity": {"critical": "Critical", "major": "Major", "minor": "Minor", "nit": "Nit"},
        "verdict": {
            Verdict.CHANGES_CRITICAL: "Fix before merging",
            Verdict.CHANGES_MAJOR: "Fix before merging",
            Verdict.ATTENTION: "OK to merge, a few suggestions",
            Verdict.CLEAN: "No issues need attention",
            Verdict.PARTIAL: "No issues in the reviewed part",
            Verdict.INCOMPLETE: "Review incomplete",
            Verdict.UNSTRUCTURED: "Review complete",
        },
        "separator": ": ",
        "col_severity": "Severity", "col_issue": "Issue", "col_location": "Location",
        "new": "new", "persisted": "still present", "not_located": "not on a changed line",
        "more": "{count} more minor suggestions", "undelivered": "Issues without an inline comment",
        "not_reported": "Not reported this time",
        "not_reported_hint": "The model did not mention these again. They may not be fixed.",
        "unstructured_hint": "The model returned no structured result. Its raw review follows.",
        "reviewed_files": "Reviewed {count} files", "at_commit": "at {commit}",
        "planned_files": "{count} files in scope",
        "failed_investigations": "{count} investigations failed. Only the available results are shown.",
        "skipped_files": "skipped {count} files",
        "truncated": "GitLab returned only part of the diff. The rest was not reviewed.",
        "truncated_positions": "GitLab returned only part of the diff. Findings without a diff position appear in the summary.",
        "digest_verdict": "Verdict", "digest_issues": "Issues", "digest_top": "Top issue",
        "digest_link": "Open MR", "digest_none": "None",
        "condition": "When", "also_at": "The same problem also appears at", "list_separator": ", ",
    },
}

VERDICT_ICONS = {
    Verdict.CHANGES_CRITICAL: "🔴 ",
    Verdict.CHANGES_MAJOR: "🟠 ",
    Verdict.ATTENTION: "🟡 ",
    Verdict.CLEAN: "",
    Verdict.PARTIAL: "",
    Verdict.INCOMPLETE: "",
    Verdict.UNSTRUCTURED: "",
}

VERDICT_TONES = {
    Verdict.CHANGES_CRITICAL: "red",
    Verdict.CHANGES_MAJOR: "orange",
    Verdict.ATTENTION: "yellow",
    Verdict.CLEAN: "green",
    Verdict.PARTIAL: "blue",
    Verdict.INCOMPLETE: "orange",
    Verdict.UNSTRUCTURED: "blue",
}


def labels_for(language: str) -> dict:
    return _LABELS.get(language, _LABELS["zh-CN"])
