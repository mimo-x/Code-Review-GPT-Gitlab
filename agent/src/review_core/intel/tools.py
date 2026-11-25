"""Bounded, evidence-recording tools for review agents.

Every call returns model-facing text (numbered, folded, capped) plus the structured items
it shows; the full result is stored as evidence under evidence_id. Text always ends with
the coverage status, so "found nothing" is never confused with "could not look".
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from review_core.common import (
    Analyzed,
    Precision,
    QueryResult,
    Record,
    ReviewCoreError,
    Side,
    stable_id,
)
from review_core.tokens import TokenCounter

from . import render

HANDLE = re.compile(r"[UC]\d+")
# Bump when a tool's name, arguments, description or output format changes: trajectories
# record it, so training data from different tool versions is never silently mixed.
TOOLS_VERSION = "tools-v3"
MAX_LISTED_DIFF_PATHS = 30


class PageArgs(Record):
    offset: int = Field(default=0, ge=0)


class OutlineArgs(PageArgs):
    path: str
    side: Side = "head"
    under: str | None = None


class SymbolArgs(PageArgs):
    identifier: str = Field(description="path::qualified.name, a symbol id, or a unit handle U#")
    side: Side = "head"


class DefinitionArgs(PageArgs):
    name: str
    side: Side = "head"
    from_path: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int = Field(default=0, ge=0)
    path_glob: str = "*"


class ReferenceArgs(SymbolArgs):
    symbol_side: Side | None = None
    direction: Literal["callers", "callees", "importers"] = "callers"
    scope: Literal["all", "tests"] = "all"
    path_glob: str = "*"


class StructuralArgs(PageArgs):
    pattern: str | dict
    language: str
    side: Side = "head"
    path_glob: str = "*"


class SearchArgs(PageArgs):
    pattern: str
    side: Side = "head"
    path_glob: str = "*"
    exclude_glob: str | None = None
    regex: bool = Field(default=False, description="treat pattern as a POSIX extended regex")
    case_sensitive: bool = True


class FindFileArgs(PageArgs):
    query: str = Field(description="substring of the repository-relative path")
    side: Side = "head"
    case_sensitive: bool = False


class FileArgs(PageArgs):
    path: str
    side: Side = "head"
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    # Page through very long lines; each line is shown from this character on.
    char_offset: int = Field(default=0, ge=0)


class DiffArgs(PageArgs):
    """offset counts hunks; line_offset pages inside the first hunk shown."""

    path: str | None = None
    paths: list[str] | None = Field(default=None, description="several file paths at once")
    unit: str | None = Field(default=None, description="a unit handle U#")
    cluster: str | None = Field(default=None, description="a cluster handle C#")
    line_offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _one_scope(self) -> DiffArgs:
        scopes = (self.path, self.paths, self.unit, self.cluster)
        if sum(value is not None for value in scopes) > 1:
            raise ValueError("Give at most one of path, paths, unit or cluster")
        if self.paths is not None and not self.paths:
            raise ValueError("paths must not be empty")
        return self


class ChangesArgs(PageArgs):
    cluster: str | None = Field(default=None, description="only this cluster handle C#")


class ToolResult(Analyzed):
    text: str
    # The items shown in text, unfolded, for programs; evidence holds all of them.
    items: tuple[dict, ...]
    total: int | None
    next_offset: int | None = None
    precision: Precision
    evidence_id: str
    error: str | None = None


# name: (arguments, items per page, renderer, description)
SPECS = {
    "outline": (
        OutlineArgs,
        200,
        render.outline_item,
        "List the symbols of a file with line ranges; under restricts to one class.",
    ),
    "read_symbol": (
        SymbolArgs,
        1,
        None,
        "Read one function or class with snapshot line numbers.",
    ),
    "compare_symbol": (
        SymbolArgs,
        1,
        render.compare_item,
        "Show a changed symbol's full before/after diff.",
    ),
    "find_definition": (
        DefinitionArgs,
        20,
        render.definition_item,
        "Find definitions of a name used at from_path:line (bound = proven binding).",
    ),
    "find_references": (
        ReferenceArgs,
        50,
        render.reference_item,
        "Find callers, callees or module importers of a symbol.",
    ),
    "structural_search": (
        StructuralArgs,
        50,
        render.match_item,
        "Find an ast-grep syntax pattern; matches are not defects by themselves.",
    ),
    "code_search": (
        SearchArgs,
        100,
        render.search_item,
        "Search file contents on one revision (literal text, or a regex with regex=true).",
    ),
    "find_file": (
        FindFileArgs,
        100,
        render.path_item,
        "Find files whose path contains a substring (e.g. a class or module name).",
    ),
    "read_file": (
        FileArgs,
        1,
        None,
        "Read a source line range (300 lines by default); long lines are folded, page "
        "them with char_offset.",
    ),
    "list_changes": (
        ChangesArgs,
        200,
        render.change_item,
        "List every changed unit of the review with its cluster (C#) and unit (U#) handles.",
    ),
    "read_diff": (
        DiffArgs,
        20,
        None,
        "Read diff hunks of the review, for files (path or paths), a unit (U#), a "
        "cluster (C#) or all.",
    ),
}


def drop_empty(model, arguments: dict) -> dict:
    """Optional arguments given as "", [] or null count as not given.

    Function-calling models often fill every schema field; an empty value for an optional
    field means "not set", not a conflicting choice.
    """
    fields = model.model_fields
    return {
        key: value
        for key, value in arguments.items()
        if not (
            key in fields
            and not fields[key].is_required()
            and (value is None or value == "" or value == [] or value == {})
        )
    }


def symbol_reference(identifier: str) -> str:
    """Accept "path:Name" and "path#Name" for "path::Name" when the left part is a path."""
    if "::" in identifier:
        return identifier
    for separator in (":", "#"):
        path, found, name = identifier.rpartition(separator)
        if found and name and ("/" in path or "." in path):
            return f"{path}::{name}"
    return identifier


class Tools:
    def __init__(self, intel, plan=None, max_output_tokens: int = 6000, max_line_chars: int = 2000):
        if max_output_tokens < 256:
            raise ValueError("Tool output cap must be at least 256 tokens")
        if max_line_chars < 80:
            raise ValueError("Line fold limit must be at least 80 characters")
        self.intel = intel
        self.plan = plan
        self.counter = TokenCounter("cl100k_base")
        self.max_output_tokens = max_output_tokens
        self.max_line_chars = max_line_chars

    @staticmethod
    def schemas() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": model.model_json_schema(),
                },
            }
            for name, (model, _, _, description) in SPECS.items()
        ]

    def call(self, name: str, /, **arguments) -> ToolResult:
        """Run a tool; name is positional-only so tool arguments may also be called name."""
        if name not in SPECS:
            raise ReviewCoreError(f"Unknown tool: {name}")
        model, item_limit, _, _ = SPECS[name]
        error = None
        options = {}
        try:
            options = model.model_validate(drop_empty(model, arguments)).model_dump()
            result, header = self._execute(name, dict(options))
        except ValidationError as exc:
            error = "Invalid tool arguments: " + "; ".join(
                f"{'.'.join(str(p) for p in item['loc']) or 'arguments'}: {item['msg']}"
                for item in exc.errors()[:3]
            )
            result, header = QueryResult[dict](precision="text", issues=(error,)), name
        except ReviewCoreError as exc:
            error = str(exc)
            result, header = QueryResult[dict](precision="text", issues=(error,)), name
        except Exception as exc:  # a tool bug must not end the investigation
            error = f"internal tool error ({type(exc).__name__}); try another tool"
            result = QueryResult[dict](precision="text", issues=(f"{type(exc).__name__}: {exc}",))
            header = name
        items = tuple(
            item.model_dump(mode="json") if isinstance(item, Record) else item
            for item in result.items
        )
        evidence = {
            "snapshot_id": self.intel.workspace.snapshot.id,
            "revisions": {
                "base": self.intel.workspace.snapshot.base_sha,
                "head": self.intel.workspace.snapshot.head_sha,
                "previous": self.intel.workspace.snapshot.previous_sha,
            },
            "query": {"tool": name, "arguments": arguments},
            "result": {**result.model_dump(mode="json"), "items": list(items)},
            "content_hash": stable_id(result.model_dump(mode="json")),
        }
        evidence_id = stable_id(evidence)
        self.intel.workspace.store.put("evidence-v1", evidence_id, evidence)
        offset = options.get("offset", 0)
        text, shown, next_offset = self._text(name, header, items, offset, item_limit, options)
        footer = render.status(result, next_offset=next_offset, error=error)
        text = "\n".join([text, *footer, f"evidence {render.short(evidence_id)}"])
        return ToolResult(
            text=text,
            items=shown,
            total=len(items) if result.complete else None,
            next_offset=next_offset,
            precision=result.precision,
            evidence_id=evidence_id,
            limits=result.limits,
            gaps=result.gaps,
            issues=result.issues,
            error=error,
        )

    def evidence(self, identifier: str) -> dict:
        """Look up evidence by full or short id (as shown in tool text)."""
        record = self.intel.workspace.store.get("evidence-v1", identifier)
        if record is None and len(identifier) >= render.SHORT_ID:
            record = self.intel.workspace.store.find_prefix("evidence-v1", identifier)
        if record is None or record["snapshot_id"] != self.intel.workspace.snapshot.id:
            raise ReviewCoreError("Evidence not found in this snapshot")
        return record

    # -- text ---------------------------------------------------------------------------

    def _text(self, name, header, items, offset, item_limit, options):
        budget = self.max_output_tokens - 120  # room for the status footer
        page = items[offset : offset + item_limit]
        if not page:
            return f"{header}: no results", (), None
        if name in {"read_file", "read_symbol"}:
            return self._source_text(page[0], options, budget)
        if name == "read_diff":
            return self._diff_text(header, items, offset, item_limit, options, budget)
        renderer = SPECS[name][2]
        lines = [f"{header}: {len(items)} result{'s' if len(items) != 1 else ''}"]
        shown = []
        for item in page:
            block = renderer(item, self.max_line_chars)
            candidate = "\n".join([*lines, block])
            if shown and self.counter.count(candidate) > budget:
                break
            if not shown and self.counter.count(candidate) > budget:
                block = self._cut(block, budget - self.counter.count("\n".join(lines)))
            lines.append(block)
            shown.append(item)
        end = offset + len(shown)
        return "\n".join(lines), tuple(shown), end if end < len(items) else None

    def _source_text(self, item, options, budget):
        if item.get("body_omitted"):
            symbol = item["symbol"]
            location = symbol["location"]
            text = (
                f"{symbol['qualified_name']} spans L{location['start_line']}-"
                f"{location['end_line']} of {location['path']}; too long to show whole. "
                "Use outline to find parts, then read_file with a line range."
            )
            return text, (item,), None
        body = render.numbered(item, self.max_line_chars, options.get("char_offset", 0))
        text = "\n".join([render.source_header(item), body])
        if self.counter.count(text) > budget:
            kept = self._fit_lines(body.splitlines(), budget - 40)
            last = item["start_line"] + len(kept) - 1
            text = "\n".join(
                [
                    render.source_header(item),
                    *kept,
                    f"[output cap: continue with read_file start_line={last + 1}]",
                ]
            )
        return text, (item,), None

    def _diff_text(self, header, items, offset, item_limit, options, budget):
        lines = [f"{header}: {len(items)} hunks (-L base line, +L / L head line)"]
        shown = []
        line_offset = options.get("line_offset", 0)
        for index, item in enumerate(items[offset : offset + item_limit]):
            skip = line_offset if index == 0 else 0
            title = render.hunk_header(item)
            if skip:
                title += f" (from hunk line {skip + 1})"
            body = (
                [] if item.get("kind") == "file" else render.hunk_lines(item, self.max_line_chars)
            )
            body = body[skip:]
            if self.counter.count("\n".join([*lines, title, *body])) <= budget:
                lines += [title, *body]
                shown.append(item)
                continue
            if shown:
                break
            # One hunk alone exceeds the cap: show what fits and say how to continue.
            room = budget - self.counter.count("\n".join([*lines, title])) - 40
            kept = self._fit_lines(body, room)
            lines += [
                title,
                *kept,
                f"[output cap: continue with offset={offset} line_offset={skip + len(kept)}]",
            ]
            return "\n".join(lines), (item,), None
        end = offset + len(shown)
        return "\n".join(lines), tuple(shown), end if end < len(items) else None

    def _fit_lines(self, lines: list[str], budget: int) -> list[str]:
        kept, used = [], 0
        for line in lines:
            cost = self.counter.count(line) + 1
            if used + cost > budget:
                break
            kept.append(line)
            used += cost
        return kept

    def _cut(self, block: str, budget: int) -> str:
        kept = self._fit_lines(block.splitlines(), max(budget - 20, 20))
        return "\n".join([*kept, "[item cut at the output cap; narrow the query]"])

    # -- execution ----------------------------------------------------------------------

    def _execute(self, name: str, options: dict):
        options.pop("offset", None)
        workspace = self.intel.workspace
        if name == "outline":
            under = options.pop("under")
            result = self.intel.outline(**options)
            symbols = result.items
            if under:
                symbols = tuple(
                    s
                    for s in symbols
                    if s.qualified_name == under or s.qualified_name.startswith(under + ".")
                )
            changed = {
                symbol.id
                for unit in self.intel.changed_symbols()
                for symbol in (unit.base_symbol, unit.head_symbol)
                if symbol
            }
            items = tuple(
                {**s.model_dump(mode="json"), "changed": s.id in changed} for s in symbols
            )
            header = f"outline {options['path']} @{options['side']}"
            fields = result.model_dump(exclude={"items", "complete"})
            return QueryResult[dict](**{**fields, "items": items}), header
        if name in {"read_symbol", "compare_symbol"}:
            options["identifier"], options["side"] = self._symbol_ref(
                options["identifier"], options["side"]
            )
            if name == "compare_symbol":
                item = self.intel.compare_symbol(**options)
                return QueryResult[dict](items=(item,)), f"compare_symbol {options['identifier']}"
            symbol = self.intel.symbol(**options)
            location = symbol.location
            if location.end_line - location.start_line + 1 > 300:
                item = {"symbol": symbol.model_dump(mode="json"), "body_omitted": True}
                return QueryResult[dict](items=(item,)), "read_symbol"
            return self._source(self.intel.read_symbol(**options)), "read_symbol"
        if name == "find_definition":
            header = f"find_definition {options['name']}"
            return self.intel.resolve(**options), header
        if name == "find_references":
            options["identifier"], side = self._symbol_ref(
                options["identifier"], options["symbol_side"] or options["side"]
            )
            options["symbol_side"] = side
            header = f"find_references {options['direction']} of {options['identifier']}"
            return self.intel.references(**options), header
        if name == "structural_search":
            return self.intel.structural_match(**options), "structural_search"
        if name == "code_search":
            header = f"code_search {options['pattern']!r} @{options['side']}"
            return workspace.search(**options), header
        if name == "find_file":
            header = f"find_file {options['query']!r} @{options['side']}"
            return workspace.find_files(
                options["query"], options["side"], case_sensitive=options["case_sensitive"]
            ), header
        if name == "read_file":
            options.pop("char_offset")
            if options["end_line"] is None:
                options["end_line"] = options["start_line"] + 299
            return self._source(workspace.read_file(**options)), "read_file"
        if name == "read_diff":
            return self._hunks(options)
        if name == "list_changes":
            return self._changes(options["cluster"])
        raise ReviewCoreError(f"Unknown tool {name}")

    def _source(self, content):
        changed = [
            number
            for number in range(content.start_line, content.end_line + 1)
            if self.intel.workspace.is_diff_line(
                content.path, number, content.side, changed_only=True
            )
        ]
        return QueryResult[dict](
            items=({**content.model_dump(mode="json"), "changed_lines": changed},),
            precision="text",
            scope=f"{content.sha}:{content.path}:{content.start_line}-{content.end_line}",
        )

    def _hunks(self, options):
        units = {unit.id: unit for unit in self.intel.changed_symbols()}
        handles = self.plan.unit_handles if self.plan else {}
        by_hunk = {}
        for unit in units.values():
            for hunk_id in unit.hunk_ids:
                by_hunk.setdefault(hunk_id, []).append(handles.get(unit.id))
        wanted_hunks, wanted_files, header = None, None, "read_diff"
        if options["unit"]:
            unit = units[self._unit_id(options["unit"])]
            wanted_hunks, wanted_files = set(unit.hunk_ids), {unit.file_change_id}
            header = f"read_diff {options['unit']} ({unit.label})"
        elif options["cluster"]:
            cluster = self._plan().cluster(options["cluster"])
            members = [units[key] for key in cluster.unit_ids if key in units]
            wanted_hunks = {hunk for unit in members for hunk in unit.hunk_ids}
            wanted_files = {unit.file_change_id for unit in members}
            header = f"read_diff {cluster.handle}"
        wanted_paths = None
        if options["path"] or options["paths"]:
            wanted_paths = list(dict.fromkeys(options["paths"] or [options["path"]]))
            header = f"read_diff {', '.join(wanted_paths)}"
        changes = self.intel.workspace.read_diff()
        issues = ()
        if wanted_paths is not None:
            present = {p for change in changes for p in (change.old_path, change.new_path) if p}
            missing = [path for path in wanted_paths if path not in present]
            if missing:
                listed = sorted(present)
                more = len(listed) - MAX_LISTED_DIFF_PATHS
                known = ", ".join(listed[:MAX_LISTED_DIFF_PATHS]) + (
                    f" (+{more} more; see list_changes)" if more > 0 else ""
                )
                message = f"no diff for {', '.join(missing)}; files with diffs: {known}"
                if len(missing) == len(wanted_paths):
                    raise ReviewCoreError(message + ". For unchanged files use read_file.")
                issues = (message,)
        items = []
        for change in changes:
            if wanted_files is not None and change.id not in wanted_files:
                continue
            if wanted_paths is not None and not (
                {change.old_path, change.new_path} & set(wanted_paths)
            ):
                continue
            base = {
                "old_path": change.old_path,
                "new_path": change.new_path,
                "status": change.status,
            }
            if not change.hunks:
                summary = (
                    "binary change" if change.binary else f"{change.status} without text changes"
                )
                if change.old_mode != change.new_mode:
                    summary += f", mode {change.old_mode} -> {change.new_mode}"
                items.append({**base, "kind": "file", "summary": summary, "units": []})
            for hunk in change.hunks:
                if wanted_hunks is not None and hunk.id not in wanted_hunks:
                    continue
                labels = sorted({h for h in by_hunk.get(hunk.id, []) if h}, key=_handle_order)
                items.append({**base, **hunk.model_dump(mode="json"), "units": labels})
        return QueryResult[dict](items=tuple(items), precision="text", issues=issues), header

    def _changes(self, cluster_key):
        plan = self._plan()
        clusters = [plan.cluster(cluster_key)] if cluster_key else list(plan.clusters)
        units = {unit.id: unit for unit in self.intel.changed_symbols()}
        items = []
        for cluster in clusters:
            for key in cluster.unit_ids:
                unit = units[key]
                symbol = unit.head_symbol or unit.base_symbol
                items.append(
                    {
                        "cluster": cluster.handle,
                        "unit": plan.unit_handles[key],
                        "path": unit.new_path or unit.old_path,
                        "symbol": symbol.qualified_name if symbol else None,
                        "kinds": list(unit.kinds),
                        "added": sum(line.kind == "add" for line in unit.lines),
                        "deleted": sum(line.kind == "delete" for line in unit.lines),
                    }
                )
        excluded = [{"path": item.path, "reason": item.reason} for item in plan.coverage.exclusions]
        header = f"list_changes {cluster_key or 'all'}"
        if excluded and not cluster_key:
            paths = sorted({f"{item['path']} ({item['reason']})" for item in excluded})
            header += f"; not reviewed (excluded by rule): {', '.join(paths[:20])}"
            if len(paths) > 20:
                header += f" +{len(paths) - 20} more"
        return QueryResult[dict](items=tuple(items), precision="text"), header

    # -- handles ------------------------------------------------------------------------

    def _plan(self):
        if self.plan is None:
            raise ReviewCoreError("Unit and cluster handles need a triage plan")
        return self.plan

    def _unit_id(self, handle: str) -> str:
        plan = self._plan()
        for unit_id, value in plan.unit_handles.items():
            if value == handle:
                return unit_id
        raise ReviewCoreError(f"Unknown unit handle: {handle}")

    def _symbol_ref(self, identifier: str, side: str) -> tuple[str, str]:
        """Resolve a U# handle to its symbol on the requested side (or the side it has)."""
        identifier = identifier.strip()
        if not HANDLE.fullmatch(identifier) or not identifier.startswith("U"):
            return symbol_reference(identifier), side
        unit = {u.id: u for u in self.intel.changed_symbols()}[self._unit_id(identifier)]
        symbol = unit.head_symbol if side == "head" else unit.base_symbol
        symbol = symbol or unit.head_symbol or unit.base_symbol
        if symbol is None:
            raise ReviewCoreError(
                f"{identifier} is a change outside any symbol; use read_diff(unit={identifier!r})"
            )
        return symbol.id, symbol.location.side


def _handle_order(handle: str) -> int:
    return int(handle[1:])
