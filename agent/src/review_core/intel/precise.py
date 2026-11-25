"""Type-aware call binding through external resolvers, mapped back onto Code Intel symbols."""

from __future__ import annotations

from collections import defaultdict

from review_core.common import Gap, ReviewCoreError, Shortfalls, stable_id

from .models import Symbol
from .resolvers import Resolution, Site, resolver_for

STORE = "resolutions-v1"

# A call site key: (path, line, column) with Code Intel coordinates.
SiteKey = tuple[str, int, int]


def precise_calls(
    intel, side: str, sites: dict[str, list[dict]], extra_files=(), timeout: float = 120
) -> tuple[dict[SiteKey, tuple[Symbol, ...] | None], Shortfalls]:
    """Bind call sites with the resolver for their language.

    The result maps each site to the symbols it calls; an empty tuple means it binds to
    something with no symbol here (outside the repository); None means the resolver could
    not bind it, so name matching should decide. Sites without a resolver are absent.
    """
    found = Shortfalls()
    groups = defaultdict(list)
    for path in sites:
        resolver = resolver_for(intel.classify_file(path, side).language)
        if resolver:
            groups[resolver].append(path)
    extra_by_resolver = defaultdict(list)
    for path in extra_files:
        if path in intel.workspace.tree(side):
            resolver = resolver_for(intel.classify_file(path, side).language)
            if resolver in groups:
                extra_by_resolver[resolver].append(path)
    result: dict[SiteKey, tuple[Symbol, ...] | None] = {}
    for resolver, paths in sorted(groups.items(), key=lambda item: item[0].name):
        files = sorted({*paths, *extra_by_resolver[resolver]})
        requested = [
            Site(path=path, line=call["line"], column=call["column"], name=call["name"])
            for path in paths
            for call in sites[path]
        ]
        try:
            resolution = _run(intel, side, resolver, files, requested, timeout)
        except ReviewCoreError as exc:
            found.gaps.append(Gap(kind="resolver_failed", detail=str(exc)))
            continue
        definitions = defaultdict(list)
        for definition in resolution.definitions:
            definitions[definition.key].append(definition)
        for resolved in resolution.sites:
            key = (resolved.path, resolved.line, resolved.column)
            if not resolved.targets:
                result[key] = () if resolved.external else None
                continue
            symbols = []
            for target in resolved.targets:
                symbol = symbol_at(intel, target.path, target.line, target.name, side)
                for definition in definitions.get(target.key, ()) if symbol is None else ():
                    symbol = symbol_at(intel, definition.path, definition.line, target.name, side)
                    if symbol:
                        break
                if symbol:
                    symbols.append(symbol)
            result[key] = tuple(dict.fromkeys(symbols))
    return result, found


CONSTRUCTOR_NAMES = {"__init__", "__new__", "constructor"}


def symbol_at(intel, path: str, line: int, name: str, side: str) -> Symbol | None:
    """The innermost symbol named name whose span covers path:line.

    Resolvers report the declared name, so a parameter or local that shadows a function
    maps to nothing rather than to the enclosing function. A constructor maps to its class.
    """
    if path not in intel.workspace.tree(side):
        return None
    covering = [
        symbol
        for symbol in intel.outline(path, side).items
        if symbol.location.start_line <= line <= symbol.location.end_line
    ]
    matches = [symbol for symbol in covering if symbol.name == name]
    if not matches and name in CONSTRUCTOR_NAMES:
        matches = [symbol for symbol in covering if symbol.kind == "class"]
    return min(
        matches,
        key=lambda s: (s.location.end_line - s.location.start_line, -s.location.start_line),
        default=None,
    )


def _run(intel, side, resolver, files, sites, timeout) -> Resolution:
    workspace = intel.workspace
    tree = sorted(workspace.tree(side))
    read = lambda path: workspace.read_file(path, side).text  # noqa: E731
    files = sorted({*files, *resolver.context(tree, files, read)})
    key = stable_id(
        [resolver.version, workspace.snapshot.sha(side), files, [s.model_dump() for s in sites]]
    )
    cached = workspace.store.get(STORE, key)
    if cached is not None:
        return Resolution.model_validate(cached)
    root = workspace.export(side, resolver.export_paths(tree, files))
    resolution = resolver.run(root, files, sites, timeout)
    workspace.store.put(STORE, key, resolution.model_dump(mode="json"))
    return resolution
