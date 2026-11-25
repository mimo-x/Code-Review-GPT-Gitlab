from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from review_core.common import ReviewCoreError
from review_core.workspace import Workspace
from review_core.workspace.git import redacted_stderr


def test_snapshot_survives_dirty_checkout_branch_advance_and_source_removal(reviewed, tmp_path):
    repository, workspace, _ = reviewed
    expected = workspace.read_file("users.py").text
    repository.write("users.py", "unexpected working tree content")
    repository.commit("advance")
    repository.git("checkout", workspace.snapshot.base_sha)
    assert workspace.read_file("users.py").text == expected
    repository.git("config", "remote.origin.url", "https://credential@example.invalid/private")
    imported = Workspace.create(
        repository.path,
        tmp_path / "credential-import",
        "credential-source",
        workspace.snapshot.base_sha,
        workspace.snapshot.head_sha,
    )
    assert b"credential" not in imported.git.run("config", "--list")
    assert b"remote" not in imported.git.run("config", "--list")
    assert workspace.git.run("config", "--get-regexp", "core.bare").strip() == b"core.bare true"
    assert b"credential" not in workspace.git.run("config", "--list")
    assert b"remote" not in workspace.git.run("config", "--list")
    repository.path.rename(tmp_path / "source-gone")
    restored = Workspace.load(tmp_path / "state", workspace.snapshot.id)
    restored.git.run("gc", "--prune=now")
    assert restored.read_file("users.py").text == expected


def test_all_changed_lines_have_accurate_sides(reviewed):
    _, workspace, _ = reviewed
    for change in workspace.snapshot.changes:
        for hunk in change.hunks:
            for line in hunk.lines:
                for side, path, number in (
                    ("base", change.old_path, line.old_line),
                    ("head", change.new_path, line.new_line),
                ):
                    if number:
                        actual = workspace.read_file(path, side, number, number).text
                        assert actual.rstrip("\n") == line.text.rstrip("\n")
                        assert workspace.is_diff_line(path, number, side)
    assert not workspace.is_diff_line("api.py", 1000, "head")


def test_special_paths_binary_empty_mode_and_rename(repository, tmp_path):
    repository.write("旧 名\tfile.py", "value = 1\n")
    repository.write("binary.bin", b"\0old")
    repository.write("run.sh", "echo old\n")
    base = repository.commit("base")
    repository.git("mv", "旧 名\tfile.py", "新 名\nfile.py")
    repository.write("binary.bin", b"\0new")
    repository.write("empty.txt", "")
    (repository.path / "run.sh").chmod(0o755)
    (repository.path / "link").symlink_to("/etc/passwd")
    head = repository.commit("head")
    workspace = Workspace.create(repository.path, tmp_path / "state", "special", base, head)
    assert len(workspace.snapshot.changes) == 5
    assert any(change.status.startswith("R") for change in workspace.snapshot.changes)
    assert workspace.read_file("新 名\nfile.py").text == "value = 1\n"
    assert workspace.read_file("link").text == "/etc/passwd"
    assert workspace.read_file("empty.txt").text == ""
    assert next(
        change for change in workspace.snapshot.changes if change.new_path == "binary.bin"
    ).binary
    with pytest.raises(ReviewCoreError, match="Binary"):
        workspace.read_file("binary.bin")
    with pytest.raises(ReviewCoreError, match="relative"):
        workspace.read_file("../outside")


def test_concurrent_import_and_snapshot_identity(reviewed, tmp_path):
    repository, workspace, _ = reviewed

    def make(_):
        return Workspace.create(
            repository.path,
            tmp_path / "parallel",
            "test/project",
            workspace.snapshot.base_sha,
            workspace.snapshot.head_sha,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        copies = list(executor.map(make, range(4)))
    assert {copy.snapshot.id for copy in copies} == {workspace.snapshot.id}
    assert all(copy.snapshot == workspace.snapshot for copy in copies)


def test_full_sha_required_and_gitlab_version_pinned(repository, tmp_path):
    repository.write("a.py", "x=1\n")
    base = repository.commit()
    repository.write("a.py", "x=2\n")
    head = repository.commit()
    with pytest.raises(ReviewCoreError, match="immutable"):
        Workspace.create(repository.path, tmp_path / "state", "p", "main", head)
    workspace = Workspace.from_gitlab_version(
        repository.path,
        tmp_path / "state",
        "p",
        {
            "base_commit_sha": base,
            "start_commit_sha": base,
            "head_commit_sha": head,
            "merge_request_id": 42,
            "id": 7,
        },
        previous_sha=base,
    )
    assert workspace.snapshot.diff_version == "7"
    assert workspace.read_file("a.py", "previous").text == "x=1\n"


def test_text_search_distinguishes_no_match_from_timeout(reviewed, monkeypatch):
    import subprocess

    _, workspace, _ = reviewed
    assert workspace.search("get_user").complete
    assert workspace.search("never-present").items == ()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 0.001)

    monkeypatch.setattr("review_core.workspace.service.subprocess.run", timeout)
    result = workspace.search("get_user")
    assert not result.complete
    assert result.limits and not result.issues


def test_diff_and_reads_preserve_missing_newline_and_unicode_separators(repository, tmp_path):
    repository.write("a.py", 'value = "old\u2028text"\nlast = 1')
    base = repository.commit()
    repository.write("a.py", 'value = "new\u2028text"\nlast = 2')
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    assert workspace.read_file("a.py").total_lines == 2
    assert workspace.read_file("a.py", "head", 2, 2).text == "last = 2"
    changed = [line for hunk in workspace.snapshot.changes[0].hunks for line in hunk.lines]
    assert next(line for line in changed if line.new_line == 2).text == "last = 2"


def test_shallow_source_imports_only_pinned_trees(repository, tmp_path):
    repository.write("a.py", "x = 1\n")
    base = repository.commit()
    repository.write("a.py", "x = 2\n")
    middle = repository.commit()
    repository.write("a.py", "x = 3\n")
    head = repository.commit()
    repository.git("config", "uploadpack.allowAnySHA1InWant", "true")
    shallow = tmp_path / "shallow.git"
    subprocess.run(["git", "init", "-q", "--bare", str(shallow)], check=True)
    for sha in (base, head):
        subprocess.run(
            [
                "git",
                "--git-dir",
                str(shallow),
                "fetch",
                "-q",
                "--depth=1",
                repository.path.as_uri(),
                sha,
            ],
            check=True,
        )
    workspace = Workspace.create(shallow, tmp_path / "state", "p", base, head)
    assert workspace.read_file("a.py", "base").text == "x = 1\n"
    assert workspace.read_file("a.py").text == "x = 3\n"
    assert [line.text for line in workspace.snapshot.changes[0].hunks[0].lines] == [
        "x = 1\n",
        "x = 3\n",
    ]
    assert not workspace.git.has_commit(middle)
    assert workspace.git.run("rev-list", "--count", head).strip() == b"1"
    again = Workspace.create(repository.path, tmp_path / "state", "p", middle, head)
    assert again.read_file("a.py", "base").text == "x = 2\n"
    again.git.run("gc", "--prune=now")
    assert Workspace.load(tmp_path / "state", workspace.snapshot.id).read_file("a.py").text


def test_git_failures_keep_a_redacted_reason():
    stderr = b"fatal: unable to access 'https://user:secret@example.invalid/x.git/': 403\nmore"
    assert redacted_stderr(stderr) == (
        "fatal: unable to access 'https://***@example.invalid/x.git/': 403"
    )


def test_submodule_pointer_is_retained_without_checkout(repository, tmp_path):
    repository.write("a.py", "x=1\n")
    base = repository.commit()
    repository.git("update-index", "--add", "--cacheinfo", f"160000,{base},dependency")
    repository.git("commit", "-m", "add gitlink")
    head = repository.git("rev-parse", "HEAD")
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    change = workspace.snapshot.changes[0]
    assert change.new_mode == "160000"
    assert change.new_blob == base
    with pytest.raises(ReviewCoreError, match="not file content"):
        workspace.read_file("dependency")


def test_blob_reader_and_tree_wide_attributes(repository, tmp_path):
    repository.write(".gitattributes", "gen/* linguist-generated\n")
    repository.write("gen/out.py", "x = 1\n")
    repository.write("src/a.py", "y = 2\n")
    sha = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", sha, sha)
    assert workspace.attributes("gen/out.py")["linguist-generated"] == "set"
    assert workspace.attributes("src/a.py")["linguist-generated"] == "unspecified"
    assert workspace.blob_size("src/a.py") == 6
    reads = [workspace.read_file(path).text for path in ("src/a.py", "gen/out.py") * 20]
    assert reads[:2] == ["y = 2\n", "x = 1\n"]
    workspace._blobs.close()
    assert workspace.read_file("src/a.py").text == "y = 2\n"
    with pytest.raises(ReviewCoreError, match="missing"):
        workspace._blobs.read("0" * 40)
    with pytest.raises(ReviewCoreError, match="read limit"):
        workspace.read_bytes("src/a.py", max_bytes=3)


def test_exports_are_shared_by_threads_and_discarded_per_commit(reviewed, tmp_path):
    _, workspace, _ = reviewed
    state = tmp_path / "state"
    with ThreadPoolExecutor(max_workers=8) as pool:  # one file, exported by many at once
        roots = set(pool.map(lambda _: workspace.export("head", ["users.py"]), range(16)))
    (root,) = roots
    assert root == Workspace.exports(state) / workspace.snapshot.head_sha
    assert (root / "users.py").read_text() == workspace.read_file("users.py").text
    base = workspace.export("base", ["users.py"])
    Workspace.discard_exports(state, [workspace.snapshot.head_sha])
    assert not root.exists() and (base / "users.py").is_file()
    # a cache: the next export rebuilds what it needs
    assert (workspace.export("head", ["users.py"]) / "users.py").is_file()
