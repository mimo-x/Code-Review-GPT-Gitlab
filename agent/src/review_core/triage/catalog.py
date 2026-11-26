"""A compact, model-facing index of the whole change, shared by every cluster."""

from __future__ import annotations

from collections import defaultdict

from review_core.intel.models import ChangeUnit
from review_core.tokens import TokenCounter

HEADER = (
    "Change catalog: every changed unit, grouped by cluster (C#) and file. "
    "U# names a unit; (bulk) clusters hold large data-like changes, read folded; "
    "excluded changes were filtered on hard evidence.\n"
)


def render(
    clusters: list[tuple[str, list[ChangeUnit]]],
    handles: dict[str, str],
    excluded: list[tuple[ChangeUnit, str]],
    counter: TokenCounter,
    limit: int,
) -> tuple[str, str]:
    """Per-unit detail when it fits, otherwise per-file lines, otherwise truncated files."""
    detailed = _render(clusters, handles, excluded, per_unit=True)
    if counter.count(detailed) <= limit:
        return detailed, "unit"
    compact = _render(clusters, handles, excluded, per_unit=False)
    if counter.count(compact) <= limit:
        return compact, "file"
    lines = compact.splitlines(keepends=True)
    kept = [lines[0]]
    for index, line in enumerate(lines[1:], 1):
        remaining = len(lines) - index
        footer = f"... {remaining} more catalog lines omitted\n"
        if counter.count("".join([*kept, line, footer])) > limit:
            kept.append(footer)
            break
        kept.append(line)
    return "".join(kept), "file"


def _render(clusters, handles, excluded, *, per_unit: bool) -> str:
    out = [HEADER]
    for handle, units in clusters:
        by_file = defaultdict(list)
        for unit in units:
            by_file[_path(unit)].append(unit)
        for path, members in by_file.items():
            if per_unit:
                out.append(f"{handle} {path}\n")
                for unit in members:
                    name = _name(unit)
                    out.append(
                        f"  {handles[unit.id]} {name} [{','.join(unit.kinds)}] {_delta(unit)}\n"
                    )
            else:
                kinds = sorted({kind for unit in members for kind in unit.kinds})
                added = sum(1 for unit in members for line in unit.lines if line.kind == "add")
                deleted = sum(1 for unit in members for line in unit.lines if line.kind == "delete")
                first, last = handles[members[0].id], handles[members[-1].id]
                span = first if first == last else f"{first}-{last}"
                out.append(f"{handle} {path} {span} [{','.join(kinds)}] +{added} -{deleted}\n")
    if excluded:
        out.append("Excluded\n")
        for unit, reason in excluded:
            out.append(f"  {handles[unit.id]} {_path(unit)} ({reason}) {_delta(unit)}\n")
    return "".join(out)


def _path(unit: ChangeUnit) -> str:
    if unit.old_path and unit.new_path and unit.old_path != unit.new_path:
        return f"{unit.old_path} -> {unit.new_path}"
    return unit.new_path or unit.old_path or ""


def _name(unit: ChangeUnit) -> str:
    symbol = unit.head_symbol or unit.base_symbol
    return symbol.qualified_name if symbol else "<module>"


def _delta(unit: ChangeUnit) -> str:
    added = sum(1 for line in unit.lines if line.kind == "add")
    deleted = sum(1 for line in unit.lines if line.kind == "delete")
    return f"+{added} -{deleted}"
