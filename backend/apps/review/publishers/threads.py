"""决定哪些问题发成行内讨论。"""
from __future__ import annotations

from ..engines.base import Finding

# 只有严重和重要问题挂到代码行上，每个问题一条讨论，可以单独解决；其余都放在总结里
_INLINE = ("critical", "major")


def plan_threads(
    findings: list[Finding], published: dict[str, dict], max_threads: int
) -> list[list[Finding]]:
    """published 是已有讨论里的问题（指纹 → 标记内容，含所在讨论 id）。

    已经发过的问题不再发；限额要扣掉仍在报告的旧讨论，否则每次 push 都会再发一批。
    """
    current = {finding.fingerprint for finding in findings}
    open_threads = {item["discussion"] for fp, item in published.items() if fp in current}
    fresh = [
        finding for finding in findings
        if finding.in_diff and finding.severity in _INLINE and finding.fingerprint not in published
    ]
    return [[finding] for finding in fresh][:max(0, max_threads - len(open_threads))]
