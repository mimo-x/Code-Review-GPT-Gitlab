"""Focus a review on given locations, e.g. the reference comments of a bench case: only
the clusters whose change units a location points at are investigated, so a run spends its
budget where labels exist. Episode ids do not depend on the focus, so a later review of the
same case under the same run id loads the focused episodes and runs only the rest."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Side = Literal["base", "head"]


class Location(BaseModel):
    path: str
    side: Side | None = None  # None: either side
    start_line: int | None = None  # no lines: anywhere in the file
    end_line: int | None = None


class Focus(BaseModel):
    locations: list[Location]
    clusters: list[str]  # handles investigated
    skipped: list[str]  # handles not investigated
    unmatched: list[Location]  # locations no cluster covers


def _runs(numbers) -> list[tuple[int, int]]:
    """Consecutive line numbers as closed ranges."""
    runs: list[tuple[int, int]] = []
    for number in sorted(set(numbers)):
        if runs and number == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], number)
        else:
            runs.append((number, number))
    return runs


def _spans(unit, side: Side, hunks: dict) -> list[list[tuple[int, int]]]:
    """A unit's line ranges on one side, from the most to the least precise: its changed
    lines; its symbol, for a comment on unchanged lines inside it; its hunks with their
    context, for a comment next to a change."""
    changed = _runs(
        line.new_line if side == "head" else line.old_line
        for line in unit.lines
        if line.kind == ("add" if side == "head" else "delete")
    )
    symbol = unit.head_symbol if side == "head" else unit.base_symbol
    enclosing = [(symbol.location.start_line, symbol.location.end_line)] if symbol else []
    context = []
    for key in unit.hunk_ids:
        hunk = hunks[key]
        start, length = (
            (hunk.new_start, hunk.new_length)
            if side == "head"
            else (hunk.old_start, hunk.old_length)
        )
        if length:
            context.append((start, start + length - 1))
    return [changed, enclosing, context]


def _overlap(ranges, start: int, end: int) -> list[tuple[int, int]]:
    return [(lo, hi) for lo, hi in ranges if lo <= end and start <= hi]


def select(plan, units, changes, locations: list[Location]) -> Focus:
    """The clusters to investigate for these locations. A location matches the units on its
    path and side by the first of these that any of them overlaps: their changed lines, the
    innermost changed symbol around it, their hunks with context. A location without lines,
    or one none of these overlaps, matches every unit of its path."""
    hunks = {hunk.id: hunk for change in changes for hunk in change.hunks}
    owner = {key: cluster.handle for cluster in plan.clusters for key in cluster.unit_ids}
    chosen: set[str] = set()
    unmatched = []
    for location in locations:
        sides = (location.side,) if location.side else ("head", "base")
        candidates = [
            (unit, side)
            for unit in units
            for side in sides
            if (unit.new_path if side == "head" else unit.old_path) == location.path
            and unit.id in owner
        ]
        matched: set[str] = set()
        if location.start_line is None:
            matched = {owner[unit.id] for unit, _ in candidates}
        else:
            start = location.start_line
            end = location.end_line or start
            spans = [(owner[unit.id], _spans(unit, side, hunks)) for unit, side in candidates]
            for tier in range(3):
                hits = [
                    (handle, hit)
                    for handle, ranges in spans
                    for hit in _overlap(ranges[tier], start, end)
                ]
                if tier == 1 and hits:  # an enclosing class also encloses its methods
                    size = min(hi - lo for _, (lo, hi) in hits)
                    hits = [(handle, (lo, hi)) for handle, (lo, hi) in hits if hi - lo == size]
                matched = {handle for handle, _ in hits}
                if matched:
                    break
            else:
                # e.g. a file-level comment GitHub pins to line 1: the file's units, as for
                # a location without lines
                matched = {owner[unit.id] for unit, _ in candidates}
        if not matched:
            unmatched.append(location)
        chosen |= matched
    return Focus(
        locations=locations,
        clusters=[c.handle for c in plan.clusters if c.handle in chosen],
        skipped=[c.handle for c in plan.clusters if c.handle not in chosen],
        unmatched=unmatched,
    )
