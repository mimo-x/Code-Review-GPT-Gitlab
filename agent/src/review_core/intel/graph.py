from __future__ import annotations

import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import islice

from review_core.common import Analyzed, Gap, GapError, ReviewCoreError, Shortfalls

from .models import ChangeGraph, Relation
from .precise import precise_calls
from .references import BOUND_LANGUAGES, module_paths
from .resolvers import resolver_for

# Per-call-site resolution cap; the whole graph is also bounded by intel.graph_timeout.
RESOLVE_TIMEOUT = 10
MAX_RENAME_PAIRS = 1000
# Rename/move candidates: similar normalized syntax, and enough of it to mean something.
RENAME_SIMILARITY = 0.8
MIN_RENAME_TOKENS = 24


def change_graph(intel) -> ChangeGraph:
    deadline = time.monotonic() + intel.graph_timeout
    skipped = 0
    units = intel.changed_symbols()
    hunks = {hunk.id: hunk for change in intel.workspace.snapshot.changes for hunk in change.hunks}
    relations = []
    found = Shortfalls()
    for unit in units:
        found.gaps.extend(unit.gaps)
        found.issues.extend(unit.issues)
    for side in ("base", "head"):
        symbol_units = {}
        file_units = defaultdict(list)
        for unit in units:
            symbol = unit.base_symbol if side == "base" else unit.head_symbol
            path = unit.old_path if side == "base" else unit.new_path
            if path:
                file_units[path].append(unit)
            if symbol:
                symbol_units[symbol.id] = unit.id
        changed_paths = tuple(sorted(file_units))
        changed_names = set()
        pending = []  # (path, call, source unit) awaiting resolution
        for path in sorted(file_units):
            for symbol in intel.outline(path, side).items:
                if symbol.id not in symbol_units and symbol.parent_id in symbol_units:
                    symbol_units[symbol.id] = symbol_units[symbol.parent_id]
                if symbol.id in symbol_units:
                    changed_names.add(symbol.name)
        for path, owners in sorted(file_units.items()):
            try:
                parsed = intel.parsed(path, side)
            except ReviewCoreError as exc:
                if intel.expects_symbols(path, side) or not isinstance(exc, GapError):
                    found.error(exc, path)
                continue
            aliases = {
                binding["local_name"]
                for binding in parsed["imports"]
                if binding["imported_name"] in changed_names
                or binding["imported_name"] == "default"
            }
            for call in parsed["calls"]:
                if call["name"] not in changed_names | aliases:
                    continue
                owner = intel.enclosing_symbol(path, call["line"], side, call["column"])
                source = (
                    symbol_units.get(owner.id)
                    if owner
                    else next(
                        (
                            unit.id
                            for unit in owners
                            if unit.base_symbol is None
                            and unit.head_symbol is None
                            and any(
                                (
                                    hunks[key].old_start
                                    <= call["line"]
                                    < hunks[key].old_start + hunks[key].old_length
                                    if side == "base"
                                    else hunks[key].new_start
                                    <= call["line"]
                                    < hunks[key].new_start + hunks[key].new_length
                                )
                                for key in unit.hunk_ids
                            )
                        ),
                        None,
                    )
                )
                if source is not None:
                    pending.append((path, call, source))
            if (
                parsed["language"] not in BOUND_LANGUAGES
                and parsed["imports"]
                and resolver_for(parsed["language"]) is None
            ):
                found.gaps.append(
                    Gap(
                        kind="name_only",
                        detail=f"{parsed['language']}: imports and calls are matched by name",
                    )
                )
            for binding in parsed["imports"]:
                paths = module_paths(intel, path, binding["module"], side)
                for imported_path in paths:
                    for source in owners:
                        for target in file_units.get(imported_path, []):
                            if source.id != target.id:
                                relations.append(
                                    Relation(
                                        source=source.id,
                                        target=target.id,
                                        kind="import",
                                        confidence="bound" if len(paths) == 1 else "candidate",
                                        basis=f"module import {binding['module']}",
                                        location=intel.location(path, binding["line"], side),
                                    )
                                )
            # A star records shared-file membership without a quadratic weak-edge clique.
            for other in owners[1:]:
                relations.append(
                    Relation(
                        source=owners[0].id,
                        target=other.id,
                        kind="same_file",
                        confidence="candidate",
                        basis=f"same file on {side}: {path}",
                    )
                )
        _resolve_pending(
            intel, side, pending, symbol_units, changed_paths, deadline, relations, found
        )
        skipped += sum(1 for item in pending if item[0] is None)
    removed = [unit for unit in units if unit.base_symbol and unit.head_symbol is None]
    added = [unit for unit in units if unit.head_symbol and unit.base_symbol is None]
    pairs = list(
        islice(
            (
                (old, new)
                for old in removed
                for new in added
                if old.base_symbol.kind == new.head_symbol.kind
            ),
            MAX_RENAME_PAIRS + 1,
        )
    )
    if len(pairs) > MAX_RENAME_PAIRS:
        found.limits.append(f"rename comparison limit ({MAX_RENAME_PAIRS} symbol pairs)")
    for old, new in pairs[:MAX_RENAME_PAIRS]:
        before = intel.read_symbol(old.base_symbol.id, "base").text
        after = intel.read_symbol(new.head_symbol.id, "head").text
        language = intel.classify_file(old.old_path, "base").language
        a = intel.normalize(before, language)
        b = intel.normalize(after, language)
        if min(len(a.tokens), len(b.tokens)) < MIN_RENAME_TOKENS:
            continue  # tiny bodies look alike whatever they do
        similarity = SequenceMatcher(None, a.tokens, b.tokens, autojunk=False).ratio()
        if similarity >= RENAME_SIMILARITY:
            relations.append(
                Relation(
                    source=old.id,
                    target=new.id,
                    kind="rename_candidate",
                    confidence="candidate",
                    basis="similar syntax; rename/move is not established",
                    similarity=similarity,
                )
            )
    if skipped:
        found.limits.append(
            f"graph time budget of {intel.graph_timeout:g}s; {skipped} call sites not resolved"
        )
    distinct = {relation.model_dump_json(): relation for relation in relations}
    fields = found.fields()
    return ChangeGraph(
        units=units,
        relations=tuple(distinct[key] for key in sorted(distinct)),
        limits=tuple(sorted(fields["limits"])),
        gaps=tuple(sorted(fields["gaps"], key=lambda gap: (gap.kind, gap.path or "", gap.detail))),
        issues=tuple(sorted(fields["issues"])),
    )


def _resolve_pending(intel, side, pending, symbol_units, changed_paths, deadline, relations, found):
    """Bind collected call sites: type-aware where a resolver exists, else by name."""
    by_path = defaultdict(list)
    for path, call, _ in pending:
        by_path[path].append(call)
    remaining = deadline - time.monotonic()
    precise, shortfalls = (
        # Every changed file is context: callees' definitions must be visible to bind.
        precise_calls(intel, side, by_path, extra_files=changed_paths, timeout=remaining)
        if remaining > 0
        else ({}, None)
    )
    if shortfalls:
        found.absorb(Analyzed(**shortfalls.fields()))
    # Sites a resolver could not bind fall back to names: say so, per language.
    asked, unbound = Counter(), Counter()
    for path, call, _ in pending:
        language = intel.classify_file(path, side).language
        if resolver_for(language) is None:
            continue
        asked[language] += 1
        if precise.get((path, call["line"], call["column"])) is None:
            unbound[language] += 1
    for language, count in sorted(unbound.items()):
        found.gaps.append(
            Gap(
                kind="name_only",
                detail=f"{language} on {side}: {count} of {asked[language]} call sites not "
                "bound by type, matched by name",
            )
        )
    for index, (path, call, source) in enumerate(pending):
        kind = "test_reference" if intel.classify_file(path, side).kind == "test" else "call"
        location = intel.location(path, call["line"], side, call["column"])
        bound = precise.get((path, call["line"], call["column"]))
        if bound is not None:
            for symbol in bound:
                target = symbol_units.get(symbol.id)
                if target is not None and target != source:
                    relations.append(
                        Relation(
                            source=source,
                            target=target,
                            kind=kind,
                            confidence="bound",
                            basis="type-aware resolution",
                            location=location,
                        )
                    )
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # Out of time: keep the cheap edges, record what was not resolved.
            pending[index] = (None, call, source)
            continue
        definitions = intel.resolve(
            call["expression"],
            side,
            from_path=path,
            line=call["line"],
            column=call["column"],
            timeout=min(RESOLVE_TIMEOUT, remaining),
            # Only definitions in changed files can become edges.
            within=changed_paths,
            precise=False,
        )
        found.absorb(definitions)
        for candidate in definitions.items:
            target = symbol_units.get(candidate.symbol.id)
            if target is None or target == source:
                continue
            relations.append(
                Relation(
                    source=source,
                    target=target,
                    kind=kind,
                    confidence=candidate.confidence,
                    basis=candidate.basis,
                    location=location,
                )
            )
