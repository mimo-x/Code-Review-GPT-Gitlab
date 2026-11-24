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
        text = json.dumps({"findings": [{"title": "无路径"}, {"path": "pay.py", "title": "问题"}]})
        assert [f.title for f in parse_output(text).findings] == ["问题"]

    def test_findings_that_cannot_be_read_are_not_a_clean_result(self):
        text = json.dumps({"summary": "有问题", "findings": [{"title": "无路径"}, "x"]})
        parsed = parse_output(text)
        assert not parsed.structured and parsed.summary == text

    def test_empty_findings_are_a_clean_result(self):
        assert parse_output('{"summary": "", "findings": []}').structured

    def test_invalid_line_number_does_not_drop_later_findings(self):
        text = '{"findings": [{"path": "pay.py", "title": "a", "start_line": 11, "end_line": 1e400},' \
               ' {"path": "pay.py", "title": "b", "end_line": 12}]}'
        first, second = parse_output(text).findings
        assert (first.start_line, first.end_line, second.end_line) == (11, 11, 12)


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

    def test_same_title_on_separate_snippets_is_kept(self):
        kept = finalize_findings([
            finding(title="返回值没有检查", existing_code="if order.paid:"),
            finding(title="返回值没有检查", existing_code="refund(order)"),
        ], diff_index())
        assert len(kept) == 2

    def test_identical_lines_get_distinct_and_stable_fingerprints(self):
        body = ["+a = 1", "+save()", "+b = 2", "+c = 3", "+save()", "+d = 4"]
        def run(lines, start):
            diff = DiffIndex([{"old_path": "m.py", "new_path": "m.py",
                               "diff": f"@@ -0,0 +{start},{len(lines)} @@\n" + "\n".join(lines) + "\n"}])
            items = [finding(path="m.py", title=f"问题{n}", existing_code="save()", end_line=start + n)
                     for n in (1, 4)]
            return [f.fingerprint for f in finalize_findings(items, diff)]
        first = run(body, 1)
        assert len(set(first)) == 2
        assert run(body, 21) == first

    def test_is_idempotent(self):
        items = [finding(existing_code="if order.paid:")]
        once = finalize_findings(items, diff_index())
        print_once = [(f.fingerprint, f.end_line) for f in once]
        twice = finalize_findings(once, diff_index())
        assert print_once == [(f.fingerprint, f.end_line) for f in twice]
