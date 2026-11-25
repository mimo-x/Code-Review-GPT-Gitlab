"""Bulk changes: still reviewed, but alone, last, and on the floor budget.

A unit is bulk when its file is too large to index, or when its changed lines are large and
data-like (mostly very long lines, or almost no letters). Bulk is a review-shape decision,
never an exclusion: the unit keeps its place in the coverage manifest.
"""

from __future__ import annotations

from review_core.intel.models import ChangeUnit
from review_core.textshape import shape

from .models import TriageConfig


def bulk_reason(unit: ChangeUnit, config: TriageConfig) -> str | None:
    classification = unit.classification
    if classification and classification.unindexed:
        return f"unindexed file: {classification.unindexed}"
    found = shape((line.text for line in unit.lines), config.max_line_chars)
    if found.chars < config.bulk_min_chars:
        return None
    if found.long_line_chars >= config.bulk_long_line_share * found.chars:
        return f"data-like lines: {found.chars} changed chars, longest line {found.longest_line}"
    if found.letter_share <= config.bulk_max_letter_share:
        return f"data-like lines: {found.chars} changed chars, {found.letter_share:.0%} letters"
    return None
