"""Turn structural facts between change units into weighted grouping links."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePosixPath

from review_core.intel.models import ChangeGraph, ChangeUnit

from .models import Link, TriageConfig

IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
# A name owned by more units than this is too ambiguous to imply a relationship.
MAX_NAME_OWNERS = 3
TEST_STEM = re.compile(r"^(?:test_)?(?P<stem>.+?)(?:_tests?|_spec|Tests?)?$")


def links(graph: ChangeGraph, units: tuple[ChangeUnit, ...], config: TriageConfig):
    """Links among the given (reviewed) units, strongest per unit pair, deterministic."""
    members = {unit.id for unit in units}
    found = []
    for relation in graph.relations:
        if relation.source in members and relation.target in members:
            found.append(
                (
                    relation.source,
                    relation.target,
                    relation.kind,
                    relation.confidence,
                    relation.basis,
                )
            )
    found.extend(_mentions(units))
    found.extend(_test_pairs(units))
    found.extend(_same_directory(units))
    best = {}
    for source, target, kind, confidence, basis in found:
        if source == target:
            continue
        weight = config.link_weights.get(f"{kind}/{confidence}", 0.0)
        if weight < config.min_link_weight or weight <= 0:
            continue
        left, right = sorted((source, target))
        link = Link(
            source=left,
            target=right,
            kind=kind,
            confidence=confidence,
            weight=weight,
            basis=basis,
        )
        current = best.get((left, right))
        if current is None or (link.weight, link.kind, link.basis) > (
            current.weight,
            current.kind,
            current.basis,
        ):
            best[left, right] = link
    return tuple(sorted(best.values(), key=lambda link: (-link.weight, link.source, link.target)))


def _mentions(units):
    owners = defaultdict(set)
    for unit in units:
        for symbol in (unit.base_symbol, unit.head_symbol):
            if symbol and len(symbol.name) >= 3:
                owners[symbol.name].add(unit.id)
    names = {name: ids for name, ids in owners.items() if len(ids) <= MAX_NAME_OWNERS}
    for unit in units:
        used = set(IDENTIFIER.findall("".join(line.text for line in unit.lines)))
        for name in sorted(used & names.keys()):
            for owner in sorted(names[name] - {unit.id}):
                yield unit.id, owner, "mention", "candidate", f"changed lines mention {name}"


def _test_pairs(units):
    by_path = defaultdict(list)
    for unit in units:
        by_path[_path(unit)].append(unit)
    stems = defaultdict(list)
    tests = []
    for path, owners in sorted(by_path.items()):
        kind = owners[0].classification.kind if owners[0].classification else None
        if kind == "test":
            tests.append(path)
        else:
            stems[_stem(path)].append(path)
    for test in tests:
        targets = stems.get(_stem(test), [])
        if not 0 < len(targets) <= MAX_NAME_OWNERS:
            continue
        for target in targets:
            # One edge per file pair suffices: same-file links already join each file.
            yield (
                by_path[test][0].id,
                by_path[target][0].id,
                "test_pair",
                "candidate",
                (f"test file naming pairs {test} with {target}"),
            )


def _same_directory(units):
    directories = defaultdict(list)
    for unit in units:
        directories[str(PurePosixPath(_path(unit)).parent)].append(unit)
    for directory, owners in sorted(directories.items()):
        files = {}
        for unit in sorted(owners, key=lambda item: (_path(item), item.id)):
            files.setdefault(_path(unit), unit)
        anchors = list(files.values())
        for other in anchors[1:]:
            yield (
                anchors[0].id,
                other.id,
                "same_directory",
                "candidate",
                (f"files in the same directory {directory}"),
            )


def _path(unit: ChangeUnit) -> str:
    return unit.new_path or unit.old_path or ""


def _stem(path: str) -> str:
    """foo.py, test_foo.py, foo_test.go, foo.spec.ts and FooTest.java all share stem foo."""
    name = PurePosixPath(path).name
    base = name.split(".")[0] or name
    stem = TEST_STEM.match(base).group("stem")
    if stem.startswith("Test") and len(stem) > 4 and stem[4].isupper():
        stem = stem[4:]
    return stem.lower()
