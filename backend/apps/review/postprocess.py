"""所有引擎共用的后处理：定位、去重、排序、计算指纹。每一步都是幂等的。"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from difflib import SequenceMatcher

from .diff_index import DiffIndex
from .engines.base import SEVERITIES, Finding
from .scope import ReviewScope

_TITLE_SIMILARITY = 0.8
_LINE_GAP = 3


def finalize_findings(
    findings: list[Finding], diff: DiffIndex, scope: ReviewScope = ReviewScope()
) -> list[Finding]:
    # 引擎能读到被排除的文件，这里保证不会针对它们报告问题；已纳入审查的重命名文件不受影响
    findings = [f for f in findings if diff.get(f.path) is not None or scope.allows(f.path)]
    for finding in findings:
        _anchor(finding, diff)
    ordered = sorted(findings, key=_order)
    kept = _dedupe(ordered)
    _assign_fingerprints(kept, diff)
    return kept


def _anchor(finding: Finding, diff: DiffIndex) -> None:
    finding.in_diff = False
    file_diff = diff.get(finding.path)
    if file_diff is None:
        return

    if finding.existing_code:
        other = "old" if finding.side == "new" else "new"
        for side in (finding.side, other):
            hit = file_diff.find(finding.existing_code, side, finding.end_line)
            if hit:
                finding.side = side
                finding.start_line, finding.end_line = hit
                finding.in_diff = True
                break

    if not finding.in_diff and finding.end_line:
        start, end = sorted((finding.start_line or finding.end_line, finding.end_line))
        if file_diff.line(finding.side, end):
            finding.start_line = start if file_diff.covers(finding.side, start, end) else end
            finding.end_line = end
            finding.in_diff = True

    finding.path = file_diff.old_path if finding.side == "old" else file_diff.new_path


def _order(finding: Finding):
    return (
        SEVERITIES.index(finding.severity),
        not finding.in_diff,
        finding.path,
        finding.end_line or 0,
    )


def _dedupe(ordered: list[Finding]) -> list[Finding]:
    """只合并同一位置且标题相近的问题；语义去重属于引擎自己的判断。"""
    kept: list[Finding] = []
    for finding in ordered:
        if not any(_same_problem(finding, other) for other in kept):
            kept.append(finding)
    return kept


def _same_problem(a: Finding, b: Finding) -> bool:
    if a.path != b.path or a.side != b.side:
        return False
    if a.end_line and b.end_line and abs(a.end_line - b.end_line) > _LINE_GAP:
        return False
    if bool(a.end_line) != bool(b.end_line):
        return False
    return SequenceMatcher(None, _normalized(a.title), _normalized(b.title)).ratio() >= _TITLE_SIMILARITY


def _assign_fingerprints(findings: list[Finding], diff: DiffIndex) -> None:
    """指纹基于代码内容而不是行号，这样 push 后行号移动也能认出同一个问题。"""
    seen: Counter = Counter()
    for finding in findings:
        identity = "\0".join((
            finding.path, finding.side, finding.category, _anchor_text(finding, diff),
        ))
        ordinal = seen[identity]
        seen[identity] += 1
        finding.fingerprint = hashlib.sha256(f"{identity}\0{ordinal}".encode()).hexdigest()[:16]


def _anchor_text(finding: Finding, diff: DiffIndex) -> str:
    file_diff = diff.get(finding.path)
    if not finding.in_diff or file_diff is None:
        return _normalized(finding.title)
    lines = (
        file_diff.line(finding.side, number)
        for number in range(finding.start_line, finding.end_line + 1)
    )
    return "\n".join(line.text.strip() for line in lines if line)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
