from __future__ import annotations

from typing import Literal

from review_core.common import Analyzed, Gap, Precision, Record, SourceLocation
from review_core.workspace.models import DiffLine


class FileClassification(Record):
    language: str | None
    kind: Literal["source", "test", "config", "generated", "vendor", "documentation", "other"]
    parser_available: bool
    outline_available: bool
    reasons: tuple[str, ...] = ()
    size: int | None = None
    # Set when the file is too large to parse or index; it is still read as text.
    unindexed: str | None = None


class Symbol(Record):
    id: str
    name: str
    qualified_name: str
    kind: str
    signature: str
    body_hash: str
    visibility: Literal["public", "private", "unknown"]
    location: SourceLocation
    end_column: int
    parent_id: str | None = None
    export_names: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.location.path}::{self.qualified_name}"


class Reference(Record):
    location: SourceLocation
    context: str
    target_id: str | None
    relation: Literal["call", "import", "text"]
    confidence: Literal["bound", "candidate"]
    basis: str


class DefinitionCandidate(Record):
    symbol: Symbol
    confidence: Literal["bound", "candidate"]
    basis: str


class ChangeBoundary(Record):
    after_line_id: str
    kind: Literal["hunk", "syntax"]
    depth: int = 0


class ChangeUnit(Record):
    id: str
    file_change_id: str
    old_path: str | None
    new_path: str | None
    base_symbol: Symbol | None
    head_symbol: Symbol | None
    kinds: tuple[str, ...]
    lines: tuple[DiffLine, ...]
    hunk_ids: tuple[str, ...]
    boundaries: tuple[ChangeBoundary, ...] = ()
    metadata: str = ""
    precision: Precision = "syntactic"
    # Why symbol attribution fell back to hunks for this file, if it did.
    gaps: tuple[Gap, ...] = ()
    issues: tuple[str, ...] = ()
    classification: FileClassification | None = None

    @property
    def label(self) -> str:
        symbol = self.head_symbol or self.base_symbol
        if symbol:
            return symbol.label
        return f"{self.new_path or self.old_path}::<module>"


class Relation(Record):
    source: str
    target: str
    kind: Literal["call", "test_reference", "import", "same_file", "rename_candidate", "split"]
    confidence: Literal["bound", "candidate"]
    basis: str
    location: SourceLocation | None = None
    similarity: float | None = None


class ChangeGraph(Analyzed):
    units: tuple[ChangeUnit, ...]
    relations: tuple[Relation, ...]


class StructuralMatch(Record):
    location: SourceLocation
    text: str
    bindings: dict[str, str | tuple[str, ...]]


class NormalizedCode(Record):
    digest: str
    tokens: tuple[str, ...]
    precision: Precision
    complete: bool


class Relocation(Record):
    status: Literal["exact", "candidate", "ambiguous", "unlocated"]
    locations: tuple[SourceLocation, ...] = ()
    confidence: float = 0
    basis: str
