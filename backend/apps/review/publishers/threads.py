"""决定哪些问题发成行内讨论，以及哪些问题合成一条。"""
from __future__ import annotations

from ..engines.base import Finding

# 🔴🟠 每个问题一条讨论，可以单独解决；🟡 相邻的合成一条，并限制条数；⚪ 只放在总结里
_OWN_THREAD = ("critical", "major")
_MERGED = "minor"
MAX_MINOR_THREADS = 5
MERGE_LINE_GAP = 3


def plan_threads(
    findings: list[Finding], published: dict[str, dict], max_threads: int
) -> list[list[Finding]]:
    """published 是已有讨论里的问题（指纹 → 标记内容，含所在讨论 id）。

    已经发过的问题不再发；限额要扣掉仍在报告的旧讨论，否则每次 push 都会再发一批。
    """
    current = {finding.fingerprint for finding in findings}
    still_open = {fp: item for fp, item in published.items() if fp in current}
    open_threads = {item["discussion"] for item in still_open.values()}
    open_minor_threads = {
        item["discussion"] for item in still_open.values() if item.get("severity") == _MERGED
    }

    fresh = [f for f in findings if f.in_diff and f.fingerprint not in published]
    threads = [[finding] for finding in fresh if finding.severity in _OWN_THREAD]
    minor_budget = max(0, MAX_MINOR_THREADS - len(open_minor_threads))
    threads += _adjacent_groups([f for f in fresh if f.severity == _MERGED])[:minor_budget]
    return threads[:max(0, max_threads - len(open_threads))]


def _adjacent_groups(findings: list[Finding]) -> list[list[Finding]]:
    """同一文件同一侧、间隔不超过 MERGE_LINE_GAP 行的问题合成一组。"""
    groups: list[list[Finding]] = []
    for finding in sorted(findings, key=lambda f: (f.path, f.side, f.start_line, f.end_line)):
        last = groups[-1][-1] if groups else None
        if (
            last is not None
            and (last.path, last.side) == (finding.path, finding.side)
            and finding.start_line - max(f.end_line for f in groups[-1]) <= MERGE_LINE_GAP
        ):
            groups[-1].append(finding)
        else:
            groups.append([finding])
    return groups
