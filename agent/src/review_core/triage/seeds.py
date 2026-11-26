"""Deterministic starting hypotheses backed by text facts on the head tree.

A seed says where to look, never what is wrong: hits are literal word matches and can be
comments, strings or unrelated same-named symbols. Investigation confirms or rejects them.
"""

from __future__ import annotations

from review_core.common import Analyzed, Shortfalls, stable_id
from review_core.intel.models import ChangeUnit

from .links import IDENTIFIER
from .models import Hit, Seed, TriageConfig

CALLABLE_KINDS = frozenset({"function", "method"})
# Prose mentions are not code references; they would crowd out real call sites.
PROSE_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")


def find_seeds(workspace, units: tuple[ChangeUnit, ...], config: TriageConfig):
    """Return (seeds, shortfalls) from a single batched search."""
    candidates = _candidates(units, config)
    if not candidates:
        return (), Analyzed()
    names = sorted({name for _, _, name in candidates})
    result = workspace.search(names, "head", timeout=config.seed_search_timeout, words=True)
    hits_by_name = {name: [] for name in names}
    added = {
        (unit.new_path, line.new_line)
        for unit in units
        for line in unit.lines
        if line.kind == "add"
    }
    for match in result.items:
        for name in hits_by_name.keys() & set(IDENTIFIER.findall(match.text)):
            hits_by_name[name].append(match)
    seeds, too_common = [], 0
    for kind, unit, name in candidates:
        hits = []
        for match in hits_by_name[name]:
            if match.path.lower().endswith(PROSE_SUFFIXES):
                continue
            in_diff = (match.path, match.line) in added
            if kind == "unchanged_callers" and (in_diff or _inside(unit.head_symbol, match)):
                continue
            hits.append(
                Hit(
                    path=match.path, line=match.line, text=match.text.strip()[:200], in_diff=in_diff
                )
            )
        if not hits:
            continue
        if len(hits) > config.max_seed_hits_per_symbol:
            too_common += 1
            continue
        owner = unit.base_symbol if kind == "dangling_reference" else unit.head_symbol
        # New code first, then other files (cross-file callers), then the defining file.
        hits.sort(
            key=lambda hit: (
                not hit.in_diff,
                hit.path == owner.location.path,
                hit.path,
                hit.line,
            )
        )
        symbol = owner.label
        seeds.append(
            Seed(
                id=stable_id(["seed-v1", kind, unit.id, name]),
                kind=kind,
                unit_id=unit.id,
                symbol=symbol,
                claim=_claim(kind, symbol, name, len(hits)),
                hits=tuple(hits[: config.max_seed_locations]),
                total_hits=len(hits),
                complete=result.complete,
            )
        )
    found = Shortfalls()
    found.absorb(result)
    if too_common:
        noun = "candidate" if too_common == 1 else "candidates"
        found.limits.append(
            f"{too_common} seed {noun} matched more than "
            f"{config.max_seed_hits_per_symbol} lines and were not seeded"
        )
    return tuple(sorted(seeds, key=lambda seed: seed.id)), Analyzed(**found.fields())


def _candidates(units, config):
    """Deleted symbols and non-private callable signature changes, deleted first, bounded."""
    added_names = {
        (unit.head_symbol.name, unit.head_symbol.kind)
        for unit in units
        if unit.head_symbol and "added" in unit.kinds
    }
    deleted, changed = [], []
    for unit in sorted(units, key=lambda item: (item.label, item.id)):
        if "deleted" in unit.kinds and unit.base_symbol:
            symbol = unit.base_symbol
            # Re-added under the same name and kind elsewhere in this diff: a move.
            if (symbol.name, symbol.kind) not in added_names:
                deleted.append(("dangling_reference", unit, symbol.name))
        elif (
            "signature_changed" in unit.kinds
            and unit.head_symbol
            and unit.head_symbol.kind in CALLABLE_KINDS
            and unit.head_symbol.visibility != "private"
        ):
            changed.append(("unchanged_callers", unit, unit.head_symbol.name))
    chosen = [
        item
        for item in (*deleted, *changed)
        if len(item[2]) >= config.min_seed_name_length and IDENTIFIER.fullmatch(item[2])
    ]
    return chosen[: config.max_seed_symbols]


def _inside(symbol, match) -> bool:
    location = symbol.location
    return match.path == location.path and location.start_line <= match.line <= location.end_line


def _claim(kind: str, symbol: str, name: str, count: int) -> str:
    if kind == "dangling_reference":
        return f"{symbol} is deleted, yet {count} head lines still mention `{name}`"
    return (
        f"The signature of {symbol} changed, yet {count} head lines mentioning `{name}` "
        "were not modified by this change"
    )
