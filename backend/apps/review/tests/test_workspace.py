"""工作区：固定到 SHA、并发隔离、不落盘令牌。"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.review.engines.base import Revisions
from apps.review.workspace import RepositoryWorkspace, WorkspaceError
from .conftest import BASE_SOURCE, HEAD_SOURCE, git


def clone_url(origin):
    return f"file://{origin.bare}"


def revisions(origin, head=None):
    return Revisions(origin.base_sha, origin.base_sha, head or origin.head_sha)


def test_checkout_is_pinned_to_the_sha_and_removed(origin, tmp_path):
    workspace = RepositoryWorkspace(tmp_path / "repos")
    with workspace.checkout(1, clone_url(origin), "secret", revisions(origin), 42, "main") as path:
        assert (path / "app.py").read_text() == HEAD_SOURCE
        assert git(path, "rev-parse", "HEAD") == origin.head_sha
        assert git(path, "cat-file", "-t", origin.base_sha) == "commit"
    assert not path.exists()


def test_concurrent_reviews_see_their_own_revision(origin, tmp_path):
    workspace = RepositoryWorkspace(tmp_path / "repos")

    def read(head):
        with workspace.checkout(1, clone_url(origin), None, revisions(origin, head), 42, "main") as path:
            return (path / "app.py").read_text()

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(read, [origin.base_sha, origin.head_sha] * 2))
    assert results == [BASE_SOURCE, HEAD_SOURCE] * 2


def test_token_is_not_written_to_the_mirror(origin, tmp_path):
    workspace = RepositoryWorkspace(tmp_path / "repos")
    with workspace.checkout(1, clone_url(origin), "super-secret-token", revisions(origin), 42, "main"):
        pass
    for file in (tmp_path / "repos").rglob("*"):
        if file.is_file() and file.stat().st_size < 1_000_000:
            assert b"super-secret-token" not in file.read_bytes()


def test_falls_back_to_merge_request_ref(origin, tmp_path, monkeypatch):
    workspace = RepositoryWorkspace(tmp_path / "repos")
    real_git = workspace._git
    fetches = []

    def reject_fetch_by_sha(mirror, env, *args):
        if args[0] == "fetch":
            fetches.append(args)
            if "--depth=1" in args:
                raise WorkspaceError("server does not allow fetching by SHA")
        return real_git(mirror, env, *args)

    monkeypatch.setattr(workspace, "_git", reject_fetch_by_sha)
    with workspace.checkout(1, clone_url(origin), None, revisions(origin), 42, "main") as path:
        assert (path / "app.py").read_text() == HEAD_SOURCE
    assert len(fetches) == 2
    assert "+refs/merge-requests/42/head:refs/review/mr-42" in fetches[1]


def test_missing_commit_is_an_error(origin, tmp_path):
    workspace = RepositoryWorkspace(tmp_path / "repos")
    with pytest.raises(WorkspaceError):
        with workspace.checkout(1, clone_url(origin), None, revisions(origin, "f" * 40), 42, "main"):
            pass
