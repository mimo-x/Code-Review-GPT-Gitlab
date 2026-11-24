"""输出契约解析、定位和去重。"""
import json

from apps.review.diff_index import DiffIndex
from apps.review.engines.base import Finding
from apps.review.engines.output import parse_output
from apps.review.postprocess import finalize_findings

DIFF = (
    "@@ -10,3 +10,4 @@ def pay(order):\n"
    "     check(order)\n"
    "-    refund(order)\n"
    "+    if order.paid:\n"
    "+        refund(order)\n"
    "     return order\n"
)


def diff_index(path="pay.py"):
    return DiffIndex([{"old_path": path, "new_path": path, "diff": DIFF}])


def finding(**overrides):
    values = {"path": "pay.py", "title": "重复退款", "severity": "major", "end_line": 12}
    values.update(overrides)
    values.setdefault("start_line", values["end_line"])
    return Finding(**values)


class TestParseOutput:
    def test_reads_json_with_surrounding_text_and_code_fences(self):
        payload = {"summary": "结论", "overview": "概览", "findings": [{
            "path": "./pay.py", "line": 12, "severity": "HIGH", "category": "unknown",
            "title": "问题", "body": "说明",
        }]}
        parsed = parse_output(f"分析如下：\n```json\n{json.dumps(payload)}\n```\n完成")
        item = parsed.findings[0]
        assert parsed.structured and parsed.summary == "结论"
        assert (item.path, item.start_line, item.severity, item.category) == (
            "pay.py", 12, "major", "defect"
        )

    def test_keeps_plain_markdown_as_summary(self):
        parsed = parse_output("### 代码有问题\n- 第一条 {not json}")
        assert not parsed.structured
        assert "第一条" in parsed.summary

    def test_drops_entries_without_path_or_title(self):
        parsed = parse_output(json.dumps({"findings": [{"title": "无路径"}, "x", {"path": "a"}]}))
        assert parsed.structured and parsed.findings == []


class TestAnchoring:
    def test_snippet_wins_over_a_wrong_line_number(self):
        item = finding(end_line=99, existing_code="+    if order.paid:\n+        refund(order)")
        finalize_findings([item], diff_index())
        assert (item.start_line, item.end_line, item.in_diff) == (11, 12, True)

    def test_removed_code_is_anchored_on_the_old_side(self):
        item = finding(existing_code="refund(order)", side="old", end_line=11)
        finalize_findings([item], diff_index())
        assert (item.side, item.end_line, item.in_diff) == ("old", 11, True)

    def test_context_line_position_has_both_sides(self):
        position = diff_index().get("pay.py").position("new", 10)
        assert (position["old_line"], position["new_line"]) == (10, 10)

    def test_line_outside_the_diff_is_not_located(self):
        item = finding(end_line=200)
        finalize_findings([item], diff_index())
        assert item.in_diff is False

    def test_unknown_file_is_not_located(self):
        item = finding(path="other.py")
        finalize_findings([item], diff_index())
        assert item.in_diff is False


class TestPostprocess:
    def test_orders_by_severity_and_merges_only_the_same_problem(self):
        items = [
            finding(title="命名不清晰", severity="nit", end_line=10),
            finding(title="重复退款问题", end_line=12),
            finding(title="重复退款问题。", end_line=11, severity="critical"),
            finding(title="金额没有校验", end_line=12),
        ]
        kept = finalize_findings(items, diff_index())
        assert [f.title for f in kept] == ["重复退款问题。", "金额没有校验", "命名不清晰"]

    def test_fingerprint_survives_a_line_shift(self):
        moved = DIFF.replace("@@ -10,3 +10,4 @@", "@@ -30,3 +30,4 @@")
        first = finding(existing_code="if order.paid:", end_line=11)
        second = finding(existing_code="if order.paid:", end_line=31)
        finalize_findings([first], diff_index())
        finalize_findings([second], DiffIndex([{"old_path": "pay.py", "new_path": "pay.py", "diff": moved}]))
        assert first.end_line != second.end_line
        assert first.fingerprint == second.fingerprint

    def test_is_idempotent(self):
        items = [finding(existing_code="if order.paid:")]
        once = finalize_findings(items, diff_index())
        print_once = [(f.fingerprint, f.end_line) for f in once]
        twice = finalize_findings(once, diff_index())
        assert print_once == [(f.fingerprint, f.end_line) for f in twice]
