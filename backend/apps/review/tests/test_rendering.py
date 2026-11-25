"""用户看到的内容：结论、总结、行内评论、IM 摘要和安全转义。"""
import re

import pytest

from apps.review.diff_index import DiffIndex
from apps.review.engines.base import Finding, MergeRequestInfo, ReviewResult, Revisions
from apps.review.postprocess import finalize_findings
from apps.review.rendering import (
    PublishHistory,
    render_digest,
    render_inline_comment,
    render_summary,
)
from apps.review.rendering.markers import parse_findings_marker, parse_summary_marker, summary_marker
from apps.review.rendering.sanitize import sanitize
from apps.review.report import ReviewReport, Verdict

DIFF = "@@ -1,1 +1,6 @@\n a = 1\n+b = 2\n+c = 3\n+d = 4\n+e = 5\n+f = 6\n"
URL = "https://gitlab.example.com/org/app/-/merge_requests/7"
HEAD = "b" * 40


def report(findings=(), structured=True, summary="需要优先处理退款问题。", language="zh-CN", skipped=()):
    diff = DiffIndex([{"old_path": "src/app.py", "new_path": "src/app.py", "diff": DIFF}])
    result = ReviewResult(
        provider="deepseek", model="deepseek-chat", summary=summary,
        findings=list(findings), structured=structured,
    )
    return ReviewReport(
        review_id=5,
        mr=MergeRequestInfo(1, 7, "app", "标题", "dev", "", URL, "f", "main", 1, 3),
        result=result,
        findings=finalize_findings(list(findings), diff),
        diff=diff,
        revisions=Revisions("a" * 40, "a" * 40, HEAD),
        language=language,
        skipped_paths=tuple(skipped),
    )


def issue(severity="major", **overrides):
    values = {
        "path": "src/app.py", "title": "并发请求可能重复退款", "body": "原因和修复方式。",
        "severity": severity, "category": "defect", "start_line": 2, "end_line": 2,
        "existing_code": "b = 2",
    }
    values.update(overrides)
    return Finding(**values)


class TestVerdict:
    @pytest.mark.parametrize("severities,expected,heading", [
        (["critical", "nit"], Verdict.CHANGES_CRITICAL, "### 🔴 建议修复后再合并"),
        (["major"], Verdict.CHANGES_MAJOR, "### 🟠 建议修复后再合并"),
        (["minor", "nit"], Verdict.ATTENTION, "### 🟡 可以合并，有几处建议"),
        (["nit"], Verdict.CLEAN, "### 未发现需要处理的问题"),
        ([], Verdict.CLEAN, "### 未发现需要处理的问题"),
    ])
    def test_is_derived_from_findings(self, severities, expected, heading):
        findings = [issue(s, title=f"问题 {i}", end_line=2 + i % 2) for i, s in enumerate(severities)]
        built = report(findings)
        assert built.verdict is expected
        assert render_summary(built).startswith(heading)


class TestSummary:
    def test_table_lists_the_most_important_tier_and_folds_the_rest(self):
        text = render_summary(report([
            issue("critical", title="退款金额可被篡改"),
            issue(title="缺少归属校验", end_line=3, existing_code="c = 3"),
            issue("minor", title="循环内查询", end_line=4, existing_code="d = 4"),
            issue("nit", title="命名可以更清楚", end_line=5, existing_code="e = 5"),
        ]))
        assert "| 级别 | 问题 | 位置 |" in text
        assert f"| <sub>🔴 严重</sub> | 退款金额可被篡改 | [`src/app.py:2`](https://gitlab.example.com/org/app/-/blob/{HEAD}/src/app.py#L2) |" in text
        assert "| <sub>🟠 重要</sub> | 缺少归属校验 |" in text
        assert "🟡" not in text.split("<details>")[0]
        assert "<summary>其余 2 条次要建议</summary>" in text
        assert "- **循环内查询** <sub>🟡 一般</sub>" in text and "- **命名可以更清楚** <sub>⚪ 轻微</sub>" in text

    def test_minor_issues_lead_when_nothing_is_more_severe(self):
        text = render_summary(report([issue("minor", title="循环内查询"), issue("nit", title="命名", end_line=3)]))
        assert "| <sub>🟡 一般</sub> | 循环内查询 |" in text
        assert "<summary>其余 1 条次要建议</summary>" in text

    def test_has_no_overview_or_review_metadata(self):
        text = render_summary(report([issue()]))
        for removed in ("概览", "审查信息", "引擎", "模型", "用时", "deepseek"):
            assert removed not in text

    def test_footer_shows_scope_commit_and_skipped_files(self):
        text = render_summary(report([issue()], skipped=["a.sql", "b.lock"]))
        assert text.endswith(
            f"<sub>已审查 1 个文件 · 提交 [`bbbbbbbb`](https://gitlab.example.com/org/app/-/commit/{HEAD})"
            " · 跳过 2 个文件</sub>"
        )

    def test_clean_result_is_one_line_and_a_footer(self):
        text = render_summary(report(summary="整体实现清晰。"))
        assert text.split("\n\n") == [
            "### 未发现需要处理的问题",
            f"<sub>已审查 1 个文件 · 提交 [`bbbbbbbb`](https://gitlab.example.com/org/app/-/commit/{HEAD})</sub>",
        ]

    def test_unlocated_problem_keeps_its_explanation(self):
        text = render_summary(report([issue(end_line=99, start_line=99, existing_code=None)]))
        assert "未定位到改动行" in text
        assert "<summary>未能挂到代码行的问题（1）</summary>" in text
        assert "原因和修复方式。" in text

    def test_folded_items_without_a_thread_keep_their_explanation(self):
        nit = issue("nit", title="命名", body="改成 refund_total 更清楚。", end_line=3, existing_code="c = 3")
        minor = issue("minor", title="循环内查询", body="会很慢。", end_line=4, existing_code="d = 4")
        built = report([issue(), minor, nit])
        posted = {built.findings[0].fingerprint, built.findings[1].fingerprint}
        text = render_summary(built, PublishHistory(inline=posted))
        assert "改成 refund_total 更清楚。" in text
        assert "会很慢。" not in text

    def test_follow_up_marks_new_and_unreported_without_claiming_fixed(self):
        built = report([issue()])
        fingerprint = built.findings[0].fingerprint
        text = render_summary(built, PublishHistory(
            previous={"old"},
            inline={fingerprint},
            not_reported=[{"fp": "old", "title": "旧问题", "severity": "major", "location": "a.py:1"}],
        ))
        assert "并发请求可能重复退款（新增）" in text
        assert "本次未再报告（1）" in text
        assert "不代表它们已经修复" in text
        assert "已修复" not in text

    def test_markdown_without_structure_is_preserved(self):
        text = render_summary(report(structured=False, summary="### 原始报告\n- 问题"))
        assert text.startswith("### 审查完成")
        assert "### 原始报告" in text

    def test_english_labels(self):
        text = render_summary(report([issue()], language="en"))
        assert "Fix before merging" in text
        assert "Reviewed 1 files" in text
        assert not re.search(r"[\u4e00-\u9fff]", text.replace("需要优先处理退款问题。", "").replace("并发请求可能重复退款", ""))


class TestInlineComment:
    def test_single_issue_has_title_and_explanation_only(self):
        built = report([issue()])
        text = render_inline_comment(built.findings, "zh-CN")
        assert text.split("\n\n")[1:] == ["**并发请求可能重复退款** <sub>🟠 重要</sub>", "原因和修复方式。"]
        assert "suggestion" not in text

    def test_adjacent_issues_are_numbered_with_their_lines(self):
        built = report([
            issue("minor", title="循环内查询", body="订单多时会很慢。\n建议先批量取出。"),
            issue("minor", title="日志缺少订单号", body="难以定位。", start_line=3, end_line=4, existing_code="c = 3\nd = 4"),
        ])
        text = render_inline_comment(built.findings, "zh-CN")
        assert "**这段代码有 2 个小问题** <sub>🟡 一般</sub>" in text
        assert "1. **循环内查询**（第 2 行）：订单多时会很慢。\n   建议先批量取出。" in text
        assert "2. **日志缺少订单号**（第 3-4 行）：难以定位。" in text

    def test_marker_records_every_issue_in_the_thread(self):
        built = report([issue("minor"), issue("minor", title="另一个", end_line=3, existing_code="c = 3")])
        items = parse_findings_marker(render_inline_comment(built.findings, "zh-CN"))
        assert [item["fp"] for item in items] == [f.fingerprint for f in built.findings]


class TestMarkers:
    def test_summary_marker_keeps_every_issue(self):
        built = report([issue(), issue("nit", title="命名", end_line=3, existing_code="c = 3")])
        review_id, items = parse_summary_marker(summary_marker(5, built.findings))
        assert review_id == 5 and len(items) == 2

    def test_reads_markers_written_by_the_previous_version(self):
        assert parse_summary_marker("<!-- code-review-gpt:summary:v1 review=3 -->\n正文") == (3, [])
        old = "<!-- code-review-gpt:finding:v1 eyJmcCI6ICJhYmMifQ== -->"
        assert parse_findings_marker(old) == [{"fp": "abc"}]


class TestPartialDiff:
    def test_truncated_diff_is_never_called_clean(self):
        built = report(summary="没有问题。")
        built.truncated = True
        text = render_summary(built)
        assert text.startswith("### 已审查的部分未发现问题\n\nGitLab 只返回了部分改动")
        assert "未发现需要处理的问题" not in text

    def test_saved_copy_keeps_explanations_of_folded_items(self):
        text = render_summary(report([issue(), issue("minor", title="循环内查询", body="会很慢。",
                                                     end_line=3, existing_code="c = 3")]))
        assert "会很慢。" in text


class TestSafety:
    def test_mentions_after_punctuation_do_not_notify(self):
        for text in ("-@all", ".@all", "(@all)", "，@all", "请注意@all"):
            assert "@all" not in sanitize(text)

    def test_quick_actions_are_escaped(self):
        for line in ("/merge", "  /approve", "> /assign @x", "说明\n/close"):
            assert not re.search(r"^[ \t>]*/[a-z]", sanitize(line), re.MULTILINE)

    def test_code_comments_are_untouched(self):
        assert sanitize("// keep") == "// keep"

    def test_mentions_do_not_notify_but_emails_stay(self):
        assert "@all" not in sanitize("ping @all")
        assert sanitize("me@example.com") == "me@example.com"

    def test_text_cannot_break_folded_sections(self):
        assert "</details>" not in sanitize("</details>")

    def test_model_written_path_cannot_inject_a_command(self):
        text = render_summary(report([issue(path="x\n/merge", existing_code=None)]))
        assert not re.search(r"^/merge", text, re.MULTILINE)

    def test_table_cell_cannot_add_columns(self):
        text = render_summary(report([issue(title="a | b")]))
        assert "a \\| b" in text


class TestDigest:
    def test_is_short_and_links_to_the_mr(self):
        text = render_digest(report([issue("critical"), issue("nit", title="命名", end_line=3)]))
        assert text.split("\n\n") == [
            "结论：建议修复后再合并",
            "问题：🔴 严重 1 · ⚪ 轻微 1",
            "最需要关注：并发请求可能重复退款（src/app.py:2）",
            f"查看 MR：{URL}",
        ]

    def test_cannot_inject_channel_markup(self):
        text = render_digest(report([issue(title='<at user_id="all"></at>```')]))
        assert "<at" not in text
        assert "```" not in text
