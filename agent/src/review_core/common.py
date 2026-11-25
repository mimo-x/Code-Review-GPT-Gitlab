from __future__ import annotations

import hashlib
import json
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

Side = Literal["base", "head", "previous"]
Precision = Literal["text", "syntactic", "mixed"]
T = TypeVar("T")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def stable_id(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def source_lines(text: str) -> list[str]:
    """Git and Tree-sitter line coordinates use LF, including inside Unicode strings."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


class SourceLocation(Record):
    path: str
    side: Side
    sha: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_column: int = Field(default=0, ge=0)
    blob_hash: str
    symbol_id: str | None = None


# Why part of a query's scope was analyzed less precisely than asked, or not at all.
GapKind = Literal[
    "unsupported",  # no parser or symbol extractor for the language
    "syntax_error",  # the file does not parse cleanly; results from it are partial
    "unindexed",  # over a size limit, so not parsed or indexed
    "unreadable",  # binary, not UTF-8, or not file content
    "name_only",  # bindings are matched by name only for this language
    "resolver_failed",  # an external resolver failed or timed out
]


class Gap(Record):
    kind: GapKind
    path: str | None = None
    detail: str = ""

    def __str__(self) -> str:
        where = f"{self.path}: " if self.path else ""
        return f"{self.kind}: {where}{self.detail}" if self.detail else f"{self.kind}: {where}"


class Analyzed(Record):
    """Completeness, split by cause, so callers can tell what to do about it.

    limits: a time or size budget stopped the query; retry narrower to see the rest.
    gaps: parts of the scope analyzed below the stated precision; widening will not help.
    issues: any other failure.
    """

    limits: tuple[str, ...] = ()
    gaps: tuple[Gap, ...] = ()
    issues: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _derived_fields(cls, data):
        # complete is derived; accept dumps of this model, which include it.
        if isinstance(data, dict) and "complete" in data:
            data = {key: value for key, value in data.items() if key != "complete"}
        return data

    @computed_field
    @property
    def complete(self) -> bool:
        return not (self.limits or self.gaps or self.issues)


def unique(values) -> tuple:
    """Order-preserving de-duplication for limits, gaps and issues."""
    return tuple(dict.fromkeys(values))


class Shortfalls:
    """Mutable collector for the limits, gaps and issues of one query or build."""

    def __init__(self):
        self.limits: list[str] = []
        self.gaps: list[Gap] = []
        self.issues: list[str] = []

    def absorb(self, result: Analyzed) -> None:
        self.limits.extend(result.limits)
        self.gaps.extend(result.gaps)
        self.issues.extend(result.issues)

    def error(self, exc: Exception, path: str | None = None) -> None:
        if isinstance(exc, GapError):
            self.gaps.append((exc.at(path) if path else exc).gap)
        else:
            self.issues.append(str(exc))

    def fields(self) -> dict:
        return dict(limits=unique(self.limits), gaps=unique(self.gaps), issues=unique(self.issues))


class QueryResult(Analyzed, Generic[T]):
    items: tuple[T, ...] = ()
    precision: Precision = "syntactic"
    scope: str = ""
    searched_files: int = 0


class ReviewCoreError(Exception):
    """An actionable failure, safe to display without provider credentials."""


class GapError(ReviewCoreError):
    """A failure that is a known analysis gap rather than a bug or a bad request."""

    def __init__(self, gap: Gap):
        super().__init__(str(gap))
        self.gap = gap

    def at(self, path: str) -> GapError:
        return self if self.gap.path else GapError(self.gap.model_copy(update={"path": path}))
