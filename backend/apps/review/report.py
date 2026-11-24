"""一次审查的最终报告：引擎结果经过平台后处理后的统一形态。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diff_index import DiffIndex
from .engines.base import Finding, MergeRequestInfo, ReviewResult, Revisions


class Verdict(Enum):
    CHANGES_CRITICAL = "changes_critical"
    CHANGES_MAJOR = "changes_major"
    ATTENTION = "attention"
    CLEAN = "clean"
    UNSTRUCTURED = "unstructured"


@dataclass
class ReviewReport:
    review_id: int
    mr: MergeRequestInfo
    result: ReviewResult
    findings: list[Finding]
    diff: DiffIndex
    revisions: Revisions | None
    language: str
    skipped_paths: tuple[str, ...] = ()

    @property
    def verdict(self) -> Verdict:
        """结论由规则决定，只用于展示，不会触发 approve 或阻止合并。"""
        if not self.result.structured:
            return Verdict.UNSTRUCTURED
        severities = {finding.severity for finding in self.findings}
        if "critical" in severities:
            return Verdict.CHANGES_CRITICAL
        if "major" in severities:
            return Verdict.CHANGES_MAJOR
        if "minor" in severities:
            return Verdict.ATTENTION
        return Verdict.CLEAN

    def count(self, severity: str) -> int:
        return sum(finding.severity == severity for finding in self.findings)
