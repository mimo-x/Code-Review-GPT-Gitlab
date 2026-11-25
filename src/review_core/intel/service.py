from __future__ import annotations

import fnmatch
import re
import time
from pathlib import PurePosixPath

from review_core.common import (
    Gap,
    GapError,
    QueryResult,
    ReviewCoreError,
    Side,
    SourceLocation,
    source_lines,
    stable_id,
    unique,
)
from review_core.workspace import Workspace

from .models import FileClassification, StructuralMatch, Symbol
from .syntax import (
    CODE_SUFFIXES,
    DATA_LANGUAGES,
    OUTLINE_LANGUAGES,
    Syntax,
    has_syntax_errors,
    language_for,
    normalize,
)

# Larger files are not parsed or indexed: they are usually data, and parsing them dominates
# graph and reference time. They stay reviewable as text.
MAX_INDEX_BYTES = 1_000_000
# Wall-clock budget for precise call resolution while building the change graph.
GRAPH_TIMEOUT = 60


class CodeIntel:
    def __init__(
        self,
        workspace: Workspace,
        max_index_bytes: int = MAX_INDEX_BYTES,
        graph_timeout: float = GRAPH_TIMEOUT,
    ):
        self.workspace = workspace
        self.max_index_bytes = max_index_bytes
        self.graph_timeout = graph_timeout
        self.syntax = Syntax(workspace.store)
        self._outlines = {}
        self._classifications = {}
        self._resolutions = {}
        self._shadow_index = {}  # (blob, language) -> names that can rebind an import
        self._graph = None

    def classify_file(self, path: str, side: Side = "head") -> FileClassification:
        key = (path, side)
        if key in self._classifications:
            return self._classifications[key]
        entry = self.workspace.entry(path, side)
        language = language_for(path)
        text = ""
        reasons = []
        size = None
        unindexed = None
        try:
            size = self.workspace.blob_size(path, side) if entry.kind == "blob" else None
            if size is not None and size > self.max_index_bytes:
                unindexed = f"{size} bytes exceeds the {self.max_index_bytes} byte index limit"
                reasons.append(unindexed)
            text = self.workspace.read_bytes(path, side).decode("utf-8", "replace")
            language = language_for(path, text)
        except ReviewCoreError as exc:
            reasons.append(str(exc))
        pure = PurePosixPath(path)
        kind = "source" if language else "other"
        if pure.suffix.lower() in {".md", ".rst", ".txt", ".adoc"}:
            kind = "documentation"
        if pure.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}:
            kind = "config"
        if any(
            part in {"test", "tests", "__tests__", "spec", "specs"} for part in pure.parts
        ) or re.search(r"(^test_|_test\.|\.test\.|\.spec\.|Test\.)", pure.name):
            kind = "test"
            reasons.append("test path convention")
        attributes = self.workspace.attributes(path, side)
        if any(
            part in {"vendor", "node_modules", "third_party"} for part in pure.parts
        ) or attributes.get("linguist-vendored") in {"set", "true"}:
            kind = "vendor"
            reasons.append("vendored path or Git attribute")
        header = "\n".join(text.splitlines()[:12]).lower()
        if attributes.get("linguist-generated") in {"set", "true"} or (
            "do not edit" in header and ("generated" in header or "auto-generated" in header)
        ):
            kind = "generated"
            reasons.append("generated header or Git attribute")
        indexable = entry.mode in {"100644", "100755"} and unindexed is None
        result = FileClassification(
            language=language,
            kind=kind,
            parser_available=bool(language and indexable),
            outline_available=language in OUTLINE_LANGUAGES and indexable,
            reasons=tuple(reasons),
            size=size,
            unindexed=unindexed,
        )
        self._classifications[key] = result
        return result

    def expects_symbols(self, path: str, side: Side = "head") -> bool:
        """Whether symbols are expected in this file, so failing to extract them is a gap."""
        info = self.classify_file(path, side)
        if info.outline_available or info.unindexed or info.language in OUTLINE_LANGUAGES:
            return True
        if info.language is None:
            return PurePosixPath(path).suffix.lower() in CODE_SUFFIXES
        return info.language not in DATA_LANGUAGES

    def parsed(self, path: str, side: Side = "head") -> dict:
        info = self.classify_file(path, side)
        if info.unindexed:
            raise GapError(
                Gap(kind="unindexed", path=path, detail=f"Not indexed: {info.unindexed}")
            )
        if not info.outline_available:
            detail = f"no symbol extractor for {info.language or 'unknown language'}"
            raise GapError(Gap(kind="unsupported", path=path, detail=detail))
        content = self.workspace.read_file(path, side)
        try:
            return self.syntax.parse(content.blob_hash, info.language, content.text)
        except GapError as exc:
            raise exc.at(path) from None

    def outline(self, path: str, side: Side = "head") -> QueryResult[Symbol]:
        key = (path, side)
        if key in self._outlines:
            return self._outlines[key]
        try:
            parsed = self.parsed(path, side)
        except GapError as exc:
            # Cached: the same blob always fails the same way. Data and prose files have no
            # symbols to miss, so text precision is all there is, not a gap.
            gaps = (exc.gap,) if self.expects_symbols(path, side) else ()
            self._outlines[key] = QueryResult[Symbol](
                precision="text", gaps=gaps, scope=f"{side}:{path}"
            )
            return self._outlines[key]
        except ReviewCoreError as exc:
            return QueryResult[Symbol](precision="text", issues=(str(exc),), scope=f"{side}:{path}")
        entry = self.workspace.entry(path, side)
        sha = self.workspace.snapshot.sha(side)
        items = []
        latest = {}  # qualified name -> id of the most recent symbol, for parent links
        for item in parsed["symbols"]:
            identity = stable_id(
                [
                    sha,
                    path,
                    entry.oid,
                    item["kind"],
                    item["start_line"],
                    item["start_column"],
                    item["end_line"],
                    item["end_column"],
                ]
            )
            parent = latest.get(item["parent"])
            latest[item["qualified_name"]] = identity
            items.append(
                Symbol(
                    id=identity,
                    name=item["name"],
                    qualified_name=item["qualified_name"],
                    kind=item["kind"],
                    signature=item["signature"],
                    body_hash=item["body_hash"],
                    visibility=item["visibility"],
                    parent_id=parent,
                    export_names=tuple(item["export_names"]),
                    end_column=item["end_column"],
                    location=SourceLocation(
                        path=path,
                        side=side,
                        sha=sha,
                        blob_hash=entry.oid,
                        symbol_id=identity,
                        start_line=item["start_line"],
                        end_line=max(item["end_line"], item["start_line"]),
                        start_column=item["start_column"],
                    ),
                )
            )
        gaps = ()
        if parsed["errors"]:
            spans = ", ".join(f"L{start}-{end}" for start, end in parsed["errors"][:5])
            more = len(parsed["errors"]) - 5
            gaps = (
                Gap(
                    kind="syntax_error",
                    path=path,
                    detail=f"symbols in error regions are missing: {spans}"
                    + (f" and {more} more" if more > 0 else ""),
                ),
            )
        result = QueryResult[Symbol](
            items=tuple(items), scope=f"{side}:{path}", searched_files=1, gaps=gaps
        )
        self.workspace.store.put_many(
            "symbol-handles-v1", {symbol.id: {"path": path, "sha": sha} for symbol in items}
        )
        self._outlines[key] = result
        return result

    def syntax_errors(self, path: str, side: Side = "head") -> tuple[tuple[int, int], ...]:
        """Line ranges Tree-sitter could not parse; symbols there are unknown."""
        try:
            return tuple(tuple(span) for span in self.parsed(path, side)["errors"])
        except ReviewCoreError:
            return ()

    def enclosing_symbol(
        self,
        path: str,
        line: int,
        side: Side = "head",
        column: int | None = None,
    ) -> Symbol | None:
        candidates = []
        for symbol in self.outline(path, side).items:
            location = symbol.location
            if not location.start_line <= line <= location.end_line:
                continue
            if column is not None:
                if line == location.start_line and column < location.start_column:
                    continue
                if line == location.end_line and column >= symbol.end_column:
                    continue
            candidates.append(symbol)
        if not candidates:
            return None
        if column is None:
            # A physical diff line can include a class header and several inline methods.
            # Keep their common container rather than guessing which column changed.
            by_id = {symbol.id: symbol for symbol in candidates}
            candidates = [
                symbol
                for symbol in candidates
                if symbol.parent_id not in by_id
                or by_id[symbol.parent_id].location.start_line != line
            ]
            parents = {symbol.parent_id for symbol in candidates}
            leaves = [symbol for symbol in candidates if symbol.id not in parents]
            if len(leaves) > 1:
                ancestors = []
                for leaf in leaves:
                    chain = set()
                    parent = by_id.get(leaf.parent_id)
                    while parent:
                        chain.add(parent.id)
                        parent = by_id.get(parent.parent_id)
                    ancestors.append(chain)
                common = set.intersection(*ancestors)
                candidates = [symbol for symbol in candidates if symbol.id in common]
                if not candidates:
                    return None
        return min(
            candidates,
            key=lambda s: (
                s.location.end_line - s.location.start_line,
                s.end_column - s.location.start_column,
                -s.location.start_line,
            ),
        )

    def symbol(self, identifier: str, side: Side = "head") -> Symbol:
        if "::" in identifier:
            path, qualified = identifier.split("::", 1)
            matches = [s for s in self.outline(path, side).items if s.qualified_name == qualified]
        else:
            matches = [
                s
                for (path, cached_side), result in self._outlines.items()
                if cached_side == side
                for s in result.items
                if s.id == identifier
            ]
            if not matches:
                handle = self.workspace.store.get("symbol-handles-v1", identifier)
                if handle and handle["sha"] == self.workspace.snapshot.sha(side):
                    matches = [
                        symbol
                        for symbol in self.outline(handle["path"], side).items
                        if symbol.id == identifier
                    ]
        if len(matches) != 1:
            candidates = ", ".join(f"{s.id} ({s.label}, L{s.location.start_line})" for s in matches)
            raise ReviewCoreError(
                f"Symbol is missing or ambiguous: {identifier}. Candidates: {candidates}"
            )
        return matches[0]

    def read_symbol(self, identifier: str, side: Side = "head"):
        symbol = self.symbol(identifier, side)
        return self.workspace.read_file(
            symbol.location.path, side, symbol.location.start_line, symbol.location.end_line
        )

    def location(self, path: str, line: int, side: Side, column: int = 0) -> SourceLocation:
        symbol = self.enclosing_symbol(path, line, side, column)
        return SourceLocation(
            path=path,
            side=side,
            sha=self.workspace.snapshot.sha(side),
            blob_hash=self.workspace.entry(path, side).oid,
            start_line=line,
            end_line=line,
            start_column=column,
            symbol_id=symbol.id if symbol else None,
        )

    def resolve(self, name: str, side: Side = "head", **kwargs):
        from .references import resolve

        # Only complete results are cached, and those do not depend on the time budget.
        key = stable_id([name, side, {k: v for k, v in kwargs.items() if k != "timeout"}])
        if key not in self._resolutions:
            result = resolve(self, name, side, **kwargs)
            if result.complete:
                self._resolutions[key] = result
            return result
        return self._resolutions[key]

    def references(self, identifier: str, side: Side = "head", **kwargs):
        from .references import references

        return references(self, identifier, side, **kwargs)

    def changed_symbols(self):
        from .changes import changed_symbols

        return changed_symbols(self)

    def change_graph(self):
        from .graph import change_graph

        # Cached even when incomplete: a rebuild would hit the same limits again.
        if self._graph is None:
            self._graph = change_graph(self)
        return self._graph

    def compare_symbol(self, identifier: str, side: Side = "head") -> dict:
        symbol = self.symbol(identifier, side)
        matches = [
            u
            for u in self.changed_symbols()
            if symbol.id
            in {
                u.base_symbol.id if u.base_symbol else None,
                u.head_symbol.id if u.head_symbol else None,
            }
        ]
        if not matches:
            return {"changed": False, "symbol": symbol.model_dump(mode="json")}
        unit = matches[0]
        candidates = []
        if unit.base_symbol is None or unit.head_symbol is None:
            graph = self.change_graph()
            by_id = {item.id: item for item in graph.units}
            for relation in graph.relations:
                if relation.kind != "rename_candidate" or unit.id not in {
                    relation.source,
                    relation.target,
                }:
                    continue
                before = by_id[relation.source].base_symbol
                after = by_id[relation.target].head_symbol
                candidates.append(
                    {
                        "base_symbol": before.model_dump(mode="json"),
                        "head_symbol": after.model_dump(mode="json"),
                        "confidence": "candidate",
                        "similarity": relation.similarity,
                        "diff": self._full_symbol_diff(before, after),
                    }
                )
        return dict(
            changed=True,
            unit=unit.model_dump(mode="json"),
            diff=self._full_symbol_diff(unit.base_symbol, unit.head_symbol),
            pairing_candidates=candidates,
        )

    def _full_symbol_diff(self, before: Symbol | None, after: Symbol | None) -> str:
        from difflib import unified_diff

        old_lines = (
            source_lines(self.read_symbol(before.id, before.location.side).text) if before else []
        )
        new_lines = (
            source_lines(self.read_symbol(after.id, after.location.side).text) if after else []
        )
        result = []
        for line in unified_diff(
            old_lines,
            new_lines,
            fromfile=before.location.path if before else "/dev/null",
            tofile=after.location.path if after else "/dev/null",
            n=max(len(old_lines), len(new_lines)),
        ):
            result.append(line)
            if not line.endswith("\n"):
                result.append("\n\\ No newline at end of file\n")
        return "".join(result)

    def structural_match(
        self,
        pattern: str | dict,
        language: str,
        side: Side = "head",
        path_glob: str = "*",
        max_files: int = 1000,
        timeout: float = 10,
    ) -> QueryResult[StructuralMatch]:
        from ast_grep_py import SgRoot

        rule = {"pattern": pattern} if isinstance(pattern, str) else pattern
        try:
            SgRoot("", language).root().find_all({"rule": rule})
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # ast-grep panics (e.g. unknown language) are BaseException
            raise ReviewCoreError(f"Invalid structural query: {exc}") from exc
        matches = []
        issues, gaps, limits = [], [], []
        searched = 0
        started = time.monotonic()
        variables = set(re.findall(r"\${1,3}([A-Z_][A-Z_0-9]*)", str(pattern)))
        for path in sorted(self.workspace.tree(side)):
            if not fnmatch.fnmatchcase(path, path_glob):
                continue
            info = self.classify_file(path, side)
            if info.language == language and info.unindexed:
                gaps.append(
                    Gap(kind="unindexed", path=path, detail=f"not searched: {info.unindexed}")
                )
                continue
            if info.language != language or not info.parser_available:
                continue
            if searched >= max_files or time.monotonic() - started >= timeout:
                limits.append(f"structural search budget ({max_files} files, {timeout:g}s)")
                break
            try:
                content = self.workspace.read_file(path, side)
                root = self.syntax.root(content.blob_hash, language, content.text)
                if has_syntax_errors(root):
                    gaps.append(
                        Gap(kind="syntax_error", path=path, detail="matches may be incomplete")
                    )
                nodes = root.find_all({"rule": rule})
                searched += 1
            except GapError as exc:
                gaps.append(exc.at(path).gap)
                continue
            except (ReviewCoreError, ValueError) as exc:
                issues.append(str(exc))
                continue
            for node in nodes:
                position = node.range()
                bindings = {}
                for variable in sorted(variables):
                    single = node.get_match(variable)
                    multiple = node.get_multiple_matches(variable)
                    if single is not None:
                        bindings[variable] = single.text()
                    elif multiple:
                        bindings[variable] = tuple(value.text() for value in multiple)
                location = self.location(path, position.start.line + 1, side, position.start.column)
                location = location.model_copy(update={"end_line": position.end.line + 1})
                matches.append(
                    StructuralMatch(location=location, text=node.text(), bindings=bindings)
                )
        return QueryResult[StructuralMatch](
            items=tuple(matches),
            limits=unique(limits),
            gaps=unique(gaps),
            issues=unique(issues),
            searched_files=searched,
            scope=f"{language} structural query, {side}:{path_glob}",
        )

    normalize = staticmethod(normalize)

    def relocate(self, old_location: SourceLocation, snippet: str, new_side: Side = "head"):
        from .tracking import relocate

        return relocate(self, old_location, snippet, new_side)
