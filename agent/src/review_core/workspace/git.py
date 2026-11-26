from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from filelock import FileLock

from review_core.common import ReviewCoreError, stable_id


def git_env() -> dict[str, str]:
    # Credential-bearing environment variables and user Git config never enter readers.
    return {
        "PATH": os.defpath + os.pathsep + "/opt/homebrew/bin",
        "HOME": tempfile.gettempdir(),
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_LITERAL_PATHSPECS": "1",
    }


def redacted_stderr(stderr: bytes, limit: int = 300) -> str:
    # Git errors can name remotes; strip URL userinfo so credentials never reach callers.
    lines = stderr.decode("utf-8", "replace").strip().splitlines()
    first = lines[0] if lines else ""
    return re.sub(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]+@", r"\1***@", first)[:limit]


class Git:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def command(self, *args: str) -> list[str]:
        return [
            "git",
            "-C",
            str(self.path),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.quotePath=false",
            "-c",
            "core.attributesFile=/dev/null",
            "-c",
            "diff.external=",
            "-c",
            "core.pager=cat",
            *args,
        ]

    def run(self, *args: str, data: bytes | None = None, timeout: float = 30) -> bytes:
        try:
            result = subprocess.run(
                self.command(*args),
                input=data,
                capture_output=True,
                env=git_env(),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReviewCoreError(f"Git {args[0]} exceeded {timeout:g}s") from exc
        if result.returncode:
            detail = redacted_stderr(result.stderr)
            suffix = f": {detail}" if detail else ""
            raise ReviewCoreError(f"Git {args[0]} failed (exit {result.returncode}){suffix}")
        return result.stdout

    def has_commit(self, sha: str) -> bool:
        try:
            self.commit(sha)
        except ReviewCoreError:
            return False
        return True

    def commit(self, sha: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", sha):
            raise ReviewCoreError(
                "Expected a full immutable commit SHA, not a branch or expression"
            )
        resolved = self.run("rev-parse", "--verify", f"{sha}^{{commit}}").decode().strip()
        if resolved != sha.lower():
            raise ReviewCoreError("SHA must identify a commit directly, not an annotated tag")
        return resolved


class BlobReader:
    """One long-lived `git cat-file --batch` process, so reads do not fork per blob.

    Thread-safe; restarted after a fork or a crash. Reading a blob object never follows a
    symlink or invokes checkout filters.
    """

    def __init__(self, git: Git):
        self.git = git
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._pid = 0

    def read(self, oid: str) -> bytes:
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", oid):
            raise ReviewCoreError("Expected a full object id")
        with self._lock:
            for _attempt in range(2):
                process = self._running()
                try:
                    process.stdin.write(oid.encode() + b"\n")
                    process.stdin.flush()
                    header = process.stdout.readline().split()
                    if len(header) == 3 and header[1] == b"blob":
                        size = int(header[2])
                        data = process.stdout.read(size)
                        process.stdout.read(1)
                        if len(data) == size:
                            return data
                    elif len(header) == 2 and header[1] == b"missing":
                        raise ReviewCoreError(f"Git object is missing: {oid}")
                    elif len(header) == 3:
                        process.stdout.read(int(header[2]) + 1)
                        raise ReviewCoreError(f"Git object is a {header[1].decode()}, not a blob")
                except (BrokenPipeError, OSError, ValueError):
                    pass
                self.close()
            raise ReviewCoreError("Git blob reader failed")

    def _running(self) -> subprocess.Popen:
        if self._process is None or self._process.poll() is not None or self._pid != os.getpid():
            self._process = subprocess.Popen(
                self.git.command("cat-file", "--batch"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=git_env(),
            )
            self._pid = os.getpid()
        return self._process

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None or self._pid != os.getpid():
            return
        try:
            process.stdin.close()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
        finally:
            process.stdout.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def import_objects(source: Path, destination: Path, revisions: tuple[str, ...]) -> Git:
    """Copy the trees of pinned commits only, never history, remotes, config or worktree.

    Reviews read fixed trees, so every imported commit is a shallow boundary. This makes
    shallow, partial-history and full sources import identically and keeps imports small.
    """
    origin = Git(source)
    commits = tuple(dict.fromkeys(origin.commit(sha) for sha in revisions))
    object_format = origin.run("rev-parse", "--show-object-format").decode().strip()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(destination) + ".lock"):
        if not destination.exists():
            temporary = Path(tempfile.mkdtemp(dir=destination.parent, prefix="init-"))
            try:
                Git(temporary).run(
                    "init", "--bare", "--template=", f"--object-format={object_format}"
                )
                temporary.rename(destination)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        target = Git(destination)
        missing = [sha for sha in commits if not target.has_commit(sha)]
        if missing:
            _copy_trees(origin, target, missing)
        _add_shallow_boundaries(destination, commits)
        for sha in commits:
            target.run("update-ref", f"refs/review-core/{stable_id(sha)}", sha)
        # Fails on any missing tree or blob; parents are intentionally out of scope.
        target.run("rev-list", "--objects", "--no-walk", *commits, timeout=300)
    return target


def _copy_trees(origin: Git, target: Git, commits: list[str]) -> None:
    listing = origin.run("rev-list", "--objects", "--no-walk", *commits, timeout=300)
    entries = [line for line in listing.splitlines() if line]
    oids = b"".join(line.split(b" ", 1)[0] + b"\n" for line in entries)
    status = target.run("cat-file", "--batch-check=%(objectname)", data=oids, timeout=300)
    absent = {line.split(b" ", 1)[0] for line in status.splitlines() if line.endswith(b" missing")}
    wanted = b"".join(line + b"\n" for line in entries if line.split(b" ", 1)[0] in absent)
    if not wanted:
        return
    with tempfile.TemporaryFile() as pack:
        try:
            # Object names with paths let pack-objects pick good deltas.
            result = subprocess.run(
                origin.command("pack-objects", "--stdout"),
                input=wanted,
                stdout=pack,
                stderr=subprocess.PIPE,
                env=git_env(),
                timeout=600,
            )
            if result.returncode:
                raise ReviewCoreError(
                    "Cannot export the requested Git trees: " + redacted_stderr(result.stderr)
                )
            pack.seek(0)
            result = subprocess.run(
                target.command("index-pack", "--stdin"),
                stdin=pack,
                capture_output=True,
                env=git_env(),
                timeout=600,
            )
            if result.returncode:
                raise ReviewCoreError(
                    "Cannot import the requested Git trees: " + redacted_stderr(result.stderr)
                )
        except subprocess.TimeoutExpired as exc:
            raise ReviewCoreError("Git object import exceeded 600s") from exc


def _add_shallow_boundaries(destination: Path, commits: tuple[str, ...]) -> None:
    shallow = destination / "shallow"
    current = set(shallow.read_text().split()) if shallow.exists() else set()
    if set(commits) <= current:
        return
    temporary = destination / "shallow.review-core.tmp"
    temporary.write_text("".join(sha + "\n" for sha in sorted(current | set(commits))))
    os.replace(temporary, shallow)
