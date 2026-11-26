"""Group change units along their strongest links, Kruskal-style, under a capacity cap."""

from __future__ import annotations

from pathlib import PurePosixPath

from review_core.intel.models import ChangeUnit
from review_core.tokens import TokenCounter

from .models import Link, TriageConfig


def diff_tokens(unit: ChangeUnit, counter: TokenCounter) -> int:
    """Size of the change material a unit contributes; line markers cost about two tokens."""
    return counter.count("".join(line.text for line in unit.lines) + unit.metadata) + 2 * len(
        unit.lines
    )


def cluster_units(
    units: tuple[ChangeUnit, ...],
    links: tuple[Link, ...],
    sizes: dict[str, int],
    config: TriageConfig,
) -> list[tuple[tuple[str, ...], tuple[Link, ...]]]:
    """Merge strongest-first; a merge happens only if both caps still hold.

    Links must be sorted strongest first with a deterministic tie order. Units that exceed
    the capacity on their own stay single: they are never split, only paged later.
    """
    parent = {unit.id: unit.id for unit in units}
    size = {unit.id: sizes[unit.id] for unit in units}
    count = dict.fromkeys(parent, 1)

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for link in links:
        left, right = find(link.source), find(link.target)
        if left == right:
            continue
        if size[left] + size[right] > config.max_cluster_tokens:
            continue
        if count[left] + count[right] > config.max_cluster_units:
            continue
        root, child = sorted((left, right))
        parent[child] = root
        size[root] += size.pop(child)
        count[root] += count.pop(child)
    groups: dict[str, list[str]] = {}
    for unit in sorted(parent):
        groups.setdefault(find(unit), []).append(unit)
    paths = {unit.id: unit.new_path or unit.old_path or "" for unit in units}
    packed = _pack(groups, size, count, paths, config)
    links = (*links, *packed)
    owner = {unit: root for root, members in groups.items() for unit in members}
    internal: dict[str, list[Link]] = {root: [] for root in groups}
    for link in links:
        if owner[link.source] == owner[link.target]:
            internal[owner[link.source]].append(link)
    return [(tuple(members), tuple(internal[root])) for root, members in sorted(groups.items())]


def _pack(groups, size, count, paths, config) -> list[Link]:
    """Pack small clusters with their neighbours in path order, within one top-level dir.

    Mutates groups/size/count in place and returns the locality links that justify packs.
    """
    limit = min(config.pack_tokens, config.max_cluster_tokens)
    if not limit:
        return []

    def anchor(root: str) -> str:
        return min(paths[unit] for unit in groups[root])

    def top(path: str) -> str:
        parts = PurePosixPath(path).parts
        return parts[0] if len(parts) > 1 else ""

    small = sorted(
        (root for root in groups if size[root] < limit),
        key=lambda root: (anchor(root), root),
    )
    made, current = [], None
    for root in small:
        if (
            current is not None
            and top(anchor(current)) == top(anchor(root))
            and size[current] + size[root] <= limit
            and count[current] + count[root] <= config.max_cluster_units
        ):
            left, right = sorted((min(groups[current]), min(groups[root])))
            made.append(
                Link(
                    source=left,
                    target=right,
                    kind="locality",
                    confidence="candidate",
                    weight=0.0,
                    basis=f"small changes near {anchor(current)} and {anchor(root)}",
                )
            )
            groups[current] = sorted(groups[current] + groups.pop(root))
            size[current] += size.pop(root)
            count[current] += count.pop(root)
        else:
            current = root
    return made
