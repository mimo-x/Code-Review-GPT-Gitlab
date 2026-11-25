"""The deterministic post-processing stages (see postprocess): findings of all episodes ->
comments, selected, ordered, lexically de-duplicated and capped.

Deterministic on purpose: it is part of the environment, not of any policy, so training
signals attach to the episodes that produced each kept comment (see provenance).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from .findings import SEVERITY_ORDER, Severity, snippet_lines

WORD = re.compile(r"[a-z0-9_]+")


class AggregateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_severity: Severity = "nit"  # keep every level; severity only orders comments
    max_comments: int | None = Field(default=None, ge=1)
    include_suggestion: bool = False
    dedup_line_gap: int = 3
    dedup_similarity: float = 0.5
    dedup_same_code_similarity: float = 0.2


class Comment(BaseModel):
    path: str
    side: str
    start_line: int
    end_line: int
    content: str
    title: str
    category: str
    severity: str
    in_diff: bool
    provenance: dict
    duplicates: list[dict] = Field(default_factory=list)


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def _similar(a: dict, b: dict, config: AggregateConfig) -> bool:
    if a["path"] != b["path"] or a["side"] != b["side"]:
        return False
    gap = max(a["start_line"], b["start_line"]) - min(a["end_line"], b["end_line"])
    if gap > config.dedup_line_gap:
        return False
    left, right = _words(a["title"]), _words(b["title"])
    union = left | right
    overlap = len(left & right) / len(union) if union else 0.0
    if snippet_lines(a["existing_code"]) == snippet_lines(b["existing_code"]):
        # the same line can carry different issues: merge only when the claims overlap
        return overlap >= config.dedup_same_code_similarity
    return overlap >= config.dedup_similarity


def content(finding: dict, config: AggregateConfig) -> str:
    text = finding["title"].strip()
    if finding.get("condition"):
        text += f"\n\nRisk (when {finding['condition'].strip().rstrip('.')})."
    text = f"{text}\n\n{finding['description']}".strip()
    if config.include_suggestion and finding.get("suggestion"):
        text += f"\n\nSuggested change:\n```\n{finding['suggestion'].rstrip()}\n```"
    return text


def select(episodes: list[tuple[int, object]], config: AggregateConfig) -> list[tuple]:
    """episodes: (cluster rank, Episode) pairs -> (rank, episode id, finding) of the findings
    that are not withdrawn and reach min_severity."""
    limit = SEVERITY_ORDER[config.min_severity]
    return [
        (rank, episode.id, finding)
        for rank, episode in episodes
        for finding in episode.findings
        if not finding["withdrawn"] and SEVERITY_ORDER[finding["severity"]] <= limit
    ]


def order(candidates: list[tuple]) -> list[tuple]:
    return sorted(
        candidates,
        key=lambda item: (
            SEVERITY_ORDER[item[2]["severity"]],
            not item[2]["in_diff"],
            item[0],
            item[2]["path"],
            item[2]["start_line"],
        ),
    )


def dedupe(candidates: list[tuple], config: AggregateConfig) -> list[Comment]:
    """Ordered candidates -> comments; a finding similar to an earlier kept one is recorded
    as its duplicate."""
    kept: list[tuple[dict, Comment]] = []
    for rank, episode_id, finding in candidates:
        provenance = {
            "episode_id": episode_id,
            "finding_id": finding["id"],
            "cluster_rank": rank,
            "cluster": finding.get("cluster"),
            "unit": finding.get("unit"),
        }
        duplicate = next((c for f, c in kept if _similar(f, finding, config)), None)
        if duplicate is not None:
            duplicate.duplicates.append(provenance)
            continue
        kept.append(
            (
                finding,
                Comment(
                    path=finding["path"],
                    side=finding["side"],
                    start_line=finding["start_line"],
                    end_line=finding["end_line"],
                    content=content(finding, config),
                    title=finding["title"],
                    category=finding["category"],
                    severity=finding["severity"],
                    in_diff=finding["in_diff"],
                    provenance=provenance,
                ),
            )
        )
    return [comment for _, comment in kept]


def cap(comments: list[Comment], config: AggregateConfig) -> list[Comment]:
    return comments[: config.max_comments] if config.max_comments else comments
