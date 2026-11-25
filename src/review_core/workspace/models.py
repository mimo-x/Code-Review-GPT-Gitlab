from __future__ import annotations

from typing import Literal

from review_core.common import Record, Side


class DiffLine(Record):
    id: str
    kind: Literal["add", "delete", "context"]
    old_line: int | None
    new_line: int | None
    text: str


class Hunk(Record):
    id: str
    old_start: int
    old_length: int
    new_start: int
    new_length: int
    lines: tuple[DiffLine, ...]


class FileChange(Record):
    id: str
    old_path: str | None
    new_path: str | None
    status: str
    old_blob: str | None
    new_blob: str | None
    old_mode: str
    new_mode: str
    binary: bool = False
    hunks: tuple[Hunk, ...] = ()
    patch: str = ""


class Snapshot(Record):
    id: str
    repository_id: str
    base_sha: str
    start_sha: str
    head_sha: str
    previous_sha: str | None = None
    merge_request: str | None = None
    diff_version: str | None = None
    diff_policy: str = "git-myers-renames50-context3-v2"
    changes: tuple[FileChange, ...]

    def sha(self, side: Side) -> str:
        values = {"base": self.base_sha, "head": self.head_sha, "previous": self.previous_sha}
        value = values.get(side)
        if value is None:
            raise ValueError(f"Snapshot has no revision for side {side!r}")
        return value


class TreeEntry(Record):
    path: str
    mode: str
    kind: str
    oid: str
    size: int | None = None


class FileContent(Record):
    path: str
    side: Side
    sha: str
    blob_hash: str
    mode: str
    text: str
    total_lines: int
    start_line: int
    end_line: int


class TextMatch(Record):
    path: str
    side: Side
    line: int
    text: str
