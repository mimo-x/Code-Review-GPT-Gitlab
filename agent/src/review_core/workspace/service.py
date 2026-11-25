from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import subprocess
import threading
from collections.abc import Sequence
from functools import cached_property, lru_cache
from pathlib import Path, PurePosixPath

from unidiff import PatchSet

from review_core.common import (
    Gap,
    GapError,
    QueryResult,
    ReviewCoreError,
    Side,
    source_lines,
    stable_id,
)
from review_core.storage import Store

from .git import BlobReader, Git, git_env, import_objects
from .models import DiffLine, FileChange, FileContent, Hunk, Snapshot, TextMatch, TreeEntry

ATTRIBUTES = ("linguist-generated", "linguist-vendored")


class Workspace:
    def __init__(self, git: Git, snapshot: Snapshot, store: Store):
        self.git = git
        self.snapshot = snapshot
        self.store = store
        self._trees: dict[str, dict[str, TreeEntry]] = {}
        self._blobs = BlobReader(git)
        self._cached_blob = lru_cache(maxsize=16)(self._blobs.read)
        self._cached_size = lru_cache(maxsize=4096)(self._blob_size)
        self._attributes: dict[str, dict[str, dict[str, str]]] = {}

    @classmethod
    def create(
        cls,
        repository: Path,
        state_dir: Path,
        repository_id: str,
        base_sha: str,
        head_sha: str,
        *,
        start_sha: str | None = None,
        previous_sha: str | None = None,
        merge_request: str | None = None,
        diff_version: str | None = None,
    ) -> Workspace:
        start_sha = start_sha or base_sha
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        identity = dict(
            repository_id=repository_id,
            base_sha=base_sha.lower(),
            head_sha=head_sha.lower(),
            start_sha=start_sha.lower(),
            previous_sha=previous_sha.lower() if previous_sha else None,
            merge_request=merge_request,
            diff_version=diff_version,
            diff_policy="git-myers-renames50-context3-v2",
        )
        snapshot_id = stable_id(identity)
        revisions = tuple(sha for sha in (base_sha, start_sha, head_sha, previous_sha) if sha)
        git = import_objects(
            repository, state_dir / "repositories" / (stable_id(repository_id) + ".git"), revisions
        )
        store = Store(state_dir / "state.sqlite3")
        existing = store.get("snapshots-v1", snapshot_id)
        if existing:
            return cls(git, Snapshot.model_validate(existing), store)
        changes = cls._diff(git, base_sha, head_sha, snapshot_id)
        snapshot = Snapshot(id=snapshot_id, changes=changes, **identity)
        store.put("snapshots-v1", snapshot_id, snapshot.model_dump(mode="json"))
        return cls(git, snapshot, store)

    @classmethod
    def from_gitlab_version(
        cls,
        repository: Path,
        state_dir: Path,
        repository_id: str,
        version: dict,
        *,
        previous_sha: str | None = None,
    ) -> Workspace:
        # Local object diffs also cover files omitted by GitLab API size limits.
        return cls.create(
            repository,
            state_dir,
            repository_id,
            version["base_commit_sha"],
            version["head_commit_sha"],
            start_sha=version["start_commit_sha"],
            previous_sha=previous_sha,
            merge_request=str(version["merge_request_id"]),
            diff_version=str(version["id"]),
        )

    @classmethod
    def load(cls, state_dir: Path, snapshot_id: str) -> Workspace:
        store = Store(state_dir / "state.sqlite3")
        payload = store.get("snapshots-v1", snapshot_id)
        if payload is None:
            raise ReviewCoreError("Snapshot not found")
        snapshot = Snapshot.model_validate(payload)
        git = Git(state_dir / "repositories" / (stable_id(snapshot.repository_id) + ".git"))
        for side in ("base", "head"):
            git.commit(snapshot.sha(side))
        return cls(git, snapshot, store)

    @staticmethod
    def _diff(git: Git, base: str, head: str, snapshot_id: str) -> tuple[FileChange, ...]:
        raw = git.run(
            "diff",
            "--raw",
            "-z",
            "--no-abbrev",
            "--no-ext-diff",
            "--no-textconv",
            "--find-renames=50%",
            base,
            head,
            "--",
            timeout=120,
        ).split(b"\0")
        empty = git.run("hash-object", "-w", "--stdin", data=b"").decode().strip()
        changes = []
        position = 0
        while position < len(raw) and raw[position]:
            old_mode, new_mode, old_oid, new_oid, status = (
                raw[position].decode().lstrip(":").split()
            )
            position += 1
            old_path = raw[position].decode("utf-8", "surrogateescape")
            position += 1
            new_path = old_path
            if status.startswith(("R", "C")):
                new_path = raw[position].decode("utf-8", "surrogateescape")
                position += 1
            if status == "A":
                old_path = None
            if status == "D":
                new_path = None
            old_blob = None if set(old_oid) == {"0"} else old_oid
            new_blob = None if set(new_oid) == {"0"} else new_oid
            file_id = stable_id([snapshot_id, old_path, new_path])
            patch = ""
            hunks = []
            binary = False
            if "160000" not in (old_mode, new_mode):
                patch_bytes = git.run(
                    "diff",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--no-color",
                    "--diff-algorithm=myers",
                    "--no-indent-heuristic",
                    "--unified=3",
                    old_blob or empty,
                    new_blob or empty,
                    "--",
                    timeout=120,
                )
                patch_text = patch_bytes.decode("utf-8", "replace")
                binary = "Binary files " in patch_text.split("@@", 1)[0]
                # Paths come from NUL-delimited raw metadata; unidiff only parses hunk bodies.
                lines = patch_text.splitlines(keepends=True)
                first = next((i for i, line in enumerate(lines) if line.startswith("@@ ")), None)
                if first is not None:
                    body = "".join(lines[first:])
                    parsed = PatchSet("--- a/file\n+++ b/file\n" + body)[0]
                    patch = f"--- {old_path or '/dev/null'}\n+++ {new_path or '/dev/null'}\n{body}"
                    for number, hunk in enumerate(parsed):
                        hunk_id = stable_id([file_id, number])
                        diff_lines = []
                        for line in hunk:
                            if line.line_type == "\\":
                                if diff_lines:
                                    previous = diff_lines[-1]
                                    diff_lines[-1] = previous.model_copy(
                                        update={"text": previous.text.removesuffix("\n")}
                                    )
                                continue
                            kind = {"+": "add", "-": "delete", " ": "context"}[line.line_type]
                            if kind == "delete":
                                address = f"base:{old_path}:{line.source_line_no}"
                            elif kind == "add":
                                address = f"head:{new_path}:{line.target_line_no}"
                            else:
                                address = f"context:{old_path}:{line.source_line_no}:{line.target_line_no}"
                            diff_lines.append(
                                DiffLine(
                                    id=address,
                                    kind=kind,
                                    old_line=line.source_line_no,
                                    new_line=line.target_line_no,
                                    text=line.value,
                                )
                            )
                        hunks.append(
                            Hunk(
                                id=hunk_id,
                                old_start=hunk.source_start,
                                old_length=hunk.source_length,
                                new_start=hunk.target_start,
                                new_length=hunk.target_length,
                                lines=tuple(diff_lines),
                            )
                        )
                elif binary:
                    patch = "Binary content changed"
            if not patch:
                patch = f"{status}: {old_path} -> {new_path}; modes {old_mode} -> {new_mode}"
            changes.append(
                FileChange(
                    id=file_id,
                    old_path=old_path,
                    new_path=new_path,
                    status=status,
                    old_blob=old_blob,
                    new_blob=new_blob,
                    old_mode=old_mode,
                    new_mode=new_mode,
                    binary=binary,
                    hunks=tuple(hunks),
                    patch=patch,
                )
            )
        return tuple(changes)

    def tree(self, side: Side = "head") -> dict[str, TreeEntry]:
        sha = self.snapshot.sha(side)
        if sha not in self._trees:
            entries = {}
            for record in self.git.run("ls-tree", "-rlz", "--full-tree", sha).split(b"\0"):
                if not record:
                    continue
                metadata, name = record.split(b"\t", 1)
                mode, kind, oid, size = metadata.decode().split()
                path = name.decode("utf-8", "surrogateescape")
                entries[path] = TreeEntry(
                    path=path,
                    mode=mode,
                    kind=kind,
                    oid=oid,
                    size=int(size) if size.isdigit() else None,
                )
            self._trees[sha] = entries
        return self._trees[sha]

    def entry(self, path: str, side: Side = "head") -> TreeEntry:
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or ".." in pure_path.parts or "\0" in path:
            raise ReviewCoreError("Expected a repository-relative path")
        entry = self.tree(side).get(path)
        if entry is None:
            raise ReviewCoreError(f"Path does not exist on {side}: {path}")
        return entry

    def read_bytes(self, path: str, side: Side = "head", max_bytes: int = 8_000_000) -> bytes:
        entry = self.entry(path, side)
        if entry.kind != "blob":
            raise GapError(
                Gap(kind="unreadable", path=path, detail=f"a {entry.kind}, not file content")
            )
        if self.blob_size(path, side) > max_bytes:
            raise GapError(
                Gap(kind="unindexed", path=path, detail=f"exceeds the {max_bytes} byte read limit")
            )
        return self._cached_blob(entry.oid)

    def blob_size(self, path: str, side: Side = "head") -> int:
        entry = self.entry(path, side)
        if entry.kind != "blob":
            raise GapError(
                Gap(kind="unreadable", path=path, detail=f"a {entry.kind}, not file content")
            )
        # ls-tree -l already listed every blob size; no extra Git process per file.
        return entry.size if entry.size is not None else self._cached_size(entry.oid)

    def _blob_size(self, oid: str) -> int:
        return int(self.git.run("cat-file", "-s", oid))

    def read_file(
        self,
        path: str,
        side: Side = "head",
        start_line: int = 1,
        end_line: int | None = None,
    ) -> FileContent:
        data = self.read_bytes(path, side)
        if b"\0" in data:
            raise GapError(
                Gap(kind="unreadable", path=path, detail="Binary file cannot be read as source")
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GapError(
                Gap(kind="unreadable", path=path, detail="source encoding is not UTF-8")
            ) from exc
        lines = source_lines(text)
        if start_line < 1 or (end_line is not None and end_line < start_line):
            raise ReviewCoreError("Invalid line range")
        if lines and start_line > len(lines):
            raise ReviewCoreError("Line range starts beyond end of file")
        stop = min(len(lines), end_line if end_line is not None else len(lines))
        entry = self.entry(path, side)
        return FileContent(
            path=path,
            side=side,
            sha=self.snapshot.sha(side),
            blob_hash=entry.oid,
            mode=entry.mode,
            text="".join(lines[start_line - 1 : stop]),
            total_lines=len(lines),
            start_line=start_line,
            end_line=stop,
        )

    def find_files(
        self, query: str, side: Side = "head", *, case_sensitive: bool = False
    ) -> QueryResult[dict]:
        """Files whose repository path contains query (substring match on the whole path)."""
        if not query.strip():
            raise ReviewCoreError("File search expects a nonempty query")
        needle = query if case_sensitive else query.lower()
        items = tuple(
            {"path": entry.path, "side": side, "size": entry.size}
            for entry in sorted(self.tree(side).values(), key=lambda entry: entry.path)
            if entry.kind == "blob"
            and needle in (entry.path if case_sensitive else entry.path.lower())
        )
        return QueryResult[dict](
            items=items,
            precision="text",
            scope=f"paths on {side} containing {query!r}",
            searched_files=len(self.tree(side)),
        )

    def read_diff(self, path: str | None = None) -> tuple[FileChange, ...]:
        return tuple(
            change
            for change in self.snapshot.changes
            if path is None or path in (change.old_path, change.new_path)
        )

    def export(self, side: Side, paths) -> Path:
        """Materialize files of one revision on disk for external analyzers (read-only use).

        Files go to a directory per commit, so repeated exports only add what is missing;
        content at a commit never changes, which makes the cache safe to share.
        """
        sha = self.snapshot.sha(side)
        root = self.exports(self.git.path.parent.parent) / sha
        for path in paths:
            target = root / path
            if target.exists():
                continue
            try:
                data = self.read_bytes(path, side)
            except ReviewCoreError:
                continue  # submodules, oversized or missing paths are not exported
            target.parent.mkdir(parents=True, exist_ok=True)
            # per thread: reviews of one snapshot may export the same file at once
            writer = f"{os.getpid()}.{threading.get_ident()}"
            temporary = target.with_name(f".{target.name}.{writer}.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, target)
        return root

    @staticmethod
    def exports(state_dir: Path) -> Path:
        return state_dir / "exports"

    @classmethod
    def discard_exports(cls, state_dir: Path, shas) -> None:
        """Delete the exported files of these commits. Exports are a cache, rebuilt on demand,
        but never cleaned up otherwise; over many snapshots they fill the disk. The caller
        must know no review in progress still uses them."""
        for sha in shas:
            shutil.rmtree(cls.exports(state_dir) / sha, ignore_errors=True)

    def is_diff_line(self, path: str, line: int, side: Side, *, changed_only: bool = False) -> bool:
        if side not in ("base", "head"):
            return False
        for change in self.snapshot.changes:
            expected = change.old_path if side == "base" else change.new_path
            if path != expected:
                continue
            for hunk in change.hunks:
                for item in hunk.lines:
                    coordinate = item.old_line if side == "base" else item.new_line
                    if coordinate == line and (not changed_only or item.kind != "context"):
                        return True
        return False

    def attributes(self, path: str, side: Side = "head") -> dict[str, str]:
        sha = self.snapshot.sha(side)
        if sha not in self._attributes:
            # One check-attr over the whole tree instead of one Git process per file.
            paths = [entry.path for entry in self.tree(side).values() if entry.kind == "blob"]
            raw = self.git.run(
                "check-attr",
                f"--source={sha}",
                "-z",
                "--stdin",
                *ATTRIBUTES,
                data=b"".join(path.encode("utf-8", "surrogateescape") + b"\0" for path in paths),
                timeout=300,
            ).split(b"\0")
            table: dict[str, dict[str, str]] = {}
            for i in range(0, len(raw) - 2, 3):
                name = raw[i].decode("utf-8", "surrogateescape")
                table.setdefault(name, {})[raw[i + 1].decode()] = raw[i + 2].decode()
            self._attributes[sha] = table
        return dict(self._attributes[sha].get(path, dict.fromkeys(ATTRIBUTES, "unspecified")))

    def search(
        self,
        pattern: str | Sequence[str],
        side: Side = "head",
        path_glob: str = "*",
        timeout: float = 10,
        *,
        words: bool = False,
        regex: bool = False,
        case_sensitive: bool = True,
        exclude_glob: str | None = None,
    ) -> QueryResult[TextMatch]:
        """Literal (or extended-regex) search; several patterns match any of them in one pass."""
        patterns = (pattern,) if isinstance(pattern, str) else tuple(pattern)
        if not patterns or any(
            not item.strip() or "\0" in item or "\n" in item for item in patterns
        ):
            raise ReviewCoreError("Search expects nonempty single-line patterns")
        options = [
            "-n",
            "-z",
            "-I",
            "-E" if regex else "-F",
            *(["-w"] if words else []),
            *([] if case_sensitive else ["-i"]),
        ]
        expressions = [part for item in patterns for part in ("-e", item)]
        command = self.git.command("grep", *options, *expressions, self.snapshot.sha(side), "--")
        limits = ()
        try:
            process = subprocess.run(command, capture_output=True, env=git_env(), timeout=timeout)
            if process.returncode not in (0, 1):
                detail = process.stderr.decode("utf-8", "replace").strip().splitlines()
                if regex and detail:
                    raise ReviewCoreError(f"Invalid search pattern: {detail[-1][:200]}")
                raise ReviewCoreError("Git text search failed")
            output = process.stdout
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or b""
            limits = (f"text search deadline of {timeout:g}s; remaining files were not searched",)
        matches = []
        offset = 0
        while offset < len(output):
            name_end = output.find(b"\0", offset)
            number_end = output.find(b"\0", name_end + 1)
            line_end = output.find(b"\n", number_end + 1)
            if min(name_end, number_end, line_end) < 0:
                break
            name = output[offset:name_end].split(b":", 1)[1].decode("utf-8", "surrogateescape")
            number = int(output[name_end + 1 : number_end])
            value = output[number_end + 1 : line_end].decode("utf-8", "replace")
            if fnmatch.fnmatchcase(name, path_glob) and not (
                exclude_glob and fnmatch.fnmatchcase(name, exclude_glob)
            ):
                matches.append(TextMatch(path=name, side=side, line=number, text=value))
            offset = line_end + 1
        return QueryResult[TextMatch](
            items=tuple(matches),
            precision="text",
            limits=limits,
            scope=f"{'regex' if regex else 'literal'} search on {side}, paths {path_glob}"
            + (f" excluding {exclude_glob}" if exclude_glob else ""),
            searched_files=0 if limits else len(self.tree(side)),
        )

    @cached_property
    def content_digest(self) -> str:
        return hashlib.sha256(self.snapshot.model_dump_json().encode()).hexdigest()
