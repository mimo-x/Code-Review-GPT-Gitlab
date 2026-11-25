"""Review order from facts. Order never removes work: every cluster keeps its floor."""

from __future__ import annotations

from review_core.intel.models import ChangeUnit

from .models import Seed

BEHAVIOR_KINDS = {"added", "body_changed", "module", "file", "metadata_changed"}


def priority(units: list[ChangeUnit], seeds: list[Seed]) -> tuple[int, tuple[str, ...]]:
    score, reasons = 0, []
    if seeds:
        score += 3 * min(len(seeds), 3)
        reasons.append(_count(len(seeds), "seed hypothesis", "seed hypotheses"))
    public_changes = [
        unit
        for unit in units
        if "signature_changed" in unit.kinds
        and unit.head_symbol
        and unit.head_symbol.visibility != "private"
    ]
    if public_changes:
        score += 2
        reasons.append(_count(len(public_changes), "non-private signature change"))
    deleted = [unit for unit in units if "deleted" in unit.kinds]
    if deleted:
        score += 2
        reasons.append(_count(len(deleted), "deleted symbol"))
    source = [
        unit
        for unit in units
        if unit.classification
        and unit.classification.kind == "source"
        and BEHAVIOR_KINDS & set(unit.kinds)
    ]
    if source:
        score += 1
        reasons.append("source behavior changed")
    return score, tuple(reasons)


def _count(number: int, singular: str, plural: str | None = None) -> str:
    return f"{number} {singular if number == 1 else plural or singular + 's'}"
