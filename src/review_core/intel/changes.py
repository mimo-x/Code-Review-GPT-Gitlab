from __future__ import annotations

import json
from collections import Counter, defaultdict

from review_core.common import stable_id, unique

from .models import ChangeUnit
from .regions import change_boundaries


def changed_symbols(intel) -> tuple[ChangeUnit, ...]:
    if hasattr(intel, "_changes"):
        return intel._changes
    units = []
    for change in intel.workspace.snapshot.changes:
        before = intel.outline(change.old_path, "base") if change.old_path else None
        after = intel.outline(change.new_path, "head") if change.new_path else None
        base_symbols = before.items if before else ()
        head_symbols = after.items if after else ()
        counts_base = Counter(symbol.qualified_name for symbol in base_symbols)
        counts_head = Counter(symbol.qualified_name for symbol in head_symbols)
        pairs = {}
        symbol_keys = {}
        for symbol in base_symbols:
            name = symbol.qualified_name
            pair = None
            if counts_base[name] == counts_head[name] == 1:
                pair = next(item for item in head_symbols if item.qualified_name == name)
            key = symbol.id
            pairs[key] = (symbol, pair)
            symbol_keys[symbol.id] = key
            if pair:
                symbol_keys[pair.id] = key
        for symbol in head_symbols:
            if symbol.id not in symbol_keys:
                pairs[symbol.id] = (None, symbol)
                symbol_keys[symbol.id] = symbol.id
        groups = defaultdict(list)
        hunk_ids = defaultdict(set)
        gaps = unique(gap for result in (before, after) if result for gap in result.gaps)
        issues = unique(issue for result in (before, after) if result for issue in result.issues)
        # A partial parse still attributes lines outside its error regions to symbols.
        structured = any(result.precision != "text" for result in (before, after) if result)
        reliable = structured and not issues and all(gap.kind == "syntax_error" for gap in gaps)
        broken = {
            "base": intel.syntax_errors(change.old_path, "base") if change.old_path else (),
            "head": intel.syntax_errors(change.new_path, "head") if change.new_path else (),
        }
        classification = intel.classify_file(
            change.new_path or change.old_path, "head" if change.new_path else "base"
        )
        for hunk in change.hunks:
            for line in hunk.lines:
                if line.kind == "context":
                    continue
                side = "base" if line.kind == "delete" else "head"
                path = change.old_path if side == "base" else change.new_path
                number = line.old_line if side == "base" else line.new_line
                usable = reliable and not any(a <= number <= b for a, b in broken[side])
                symbol = intel.enclosing_symbol(path, number, side) if usable else None
                key = ("symbol", symbol_keys[symbol.id]) if symbol else ("hunk", hunk.id)
                groups[key].append(line)
                hunk_ids[key].add(hunk.id)
        metadata_changed = (
            change.old_mode != change.new_mode
            or change.status.startswith(("R", "C"))
            or change.binary
            or not change.hunks
        )
        metadata_key = next(iter(groups), ("metadata", change.id))
        if metadata_changed and not groups:
            groups[metadata_key] = []
        for key, lines in groups.items():
            base_symbol, head_symbol = pairs[key[1]] if key[0] == "symbol" else (None, None)
            kinds = []
            if key[0] != "symbol":
                kinds.append("module" if reliable else "file")
            elif base_symbol is None:
                kinds.append("added")
            elif head_symbol is None:
                kinds.append("deleted")
            else:
                if base_symbol.signature != head_symbol.signature:
                    kinds.append("signature_changed")
                if base_symbol.body_hash != head_symbol.body_hash:
                    kinds.append("body_changed")
                if not kinds:
                    kinds.append("format_or_comment_changed")
            owns_metadata = metadata_changed and key == metadata_key
            if owns_metadata:
                kinds.append("metadata_changed")
            if change.status.startswith("R"):
                kinds.append("file_renamed")
            unit_id = stable_id([change.id, key, "unit-v2"])
            units.append(
                ChangeUnit(
                    id=unit_id,
                    file_change_id=change.id,
                    old_path=change.old_path,
                    new_path=change.new_path,
                    base_symbol=base_symbol,
                    head_symbol=head_symbol,
                    kinds=tuple(kinds),
                    lines=tuple(lines),
                    hunk_ids=tuple(sorted(hunk_ids[key])),
                    boundaries=change_boundaries(intel, change, lines, reliable),
                    precision=("mixed" if gaps else "syntactic") if reliable else "text",
                    gaps=gaps,
                    issues=issues,
                    classification=classification,
                    metadata=json.dumps(
                        {
                            "status": change.status,
                            "old_mode": change.old_mode,
                            "new_mode": change.new_mode,
                            "old_blob": change.old_blob,
                            "new_blob": change.new_blob,
                            "binary": change.binary,
                        },
                        sort_keys=True,
                    )
                    if owns_metadata
                    else "",
                )
            )
    # This is a core invariant, independent of any clustering or LLM output.
    expected = Counter(
        line.id
        for change in intel.workspace.snapshot.changes
        for hunk in change.hunks
        for line in hunk.lines
        if line.kind != "context"
    )
    assigned = Counter(line.id for unit in units for line in unit.lines)
    if assigned != expected:
        raise RuntimeError("Change ownership is incomplete or duplicated")
    intel._changes = tuple(sorted(units, key=lambda unit: unit.id))
    return intel._changes
