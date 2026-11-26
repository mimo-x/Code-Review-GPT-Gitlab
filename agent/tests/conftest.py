from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from review_core.intel import CodeIntel
from review_core.workspace import Workspace


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "review-core@example.invalid")
        self.git("config", "user.name", "Review Core Test")

    def git(self, *args: str) -> str:
        return (
            subprocess.check_output(
                ["git", "-C", str(self.path), *args],
                stderr=subprocess.DEVNULL,
                env={
                    **os.environ,
                    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
                    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
                },
            )
            .decode()
            .strip()
        )

    def write(self, path: str, text: str | bytes):
        target = self.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode() if isinstance(text, str) else text)

    def commit(self, message: str = "revision") -> str:
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path):
    return Repository(tmp_path / "repo")


@pytest.fixture
def reviewed(repository, tmp_path):
    repository.write("users.py", 'def get_user(id):\n    return {"name": "test"}\n')
    repository.write(
        "api.py",
        'from users import get_user as fetch\n\ndef api(id):\n    return fetch(id)["name"]\n',
    )
    repository.write(
        "tests/test_users.py",
        "from users import get_user\n\ndef test_user():\n    assert get_user(1)\n",
    )
    base = repository.commit("base")
    repository.write(
        "users.py",
        'def get_user(id):\n    if id is None:\n        return None\n    return {"name": "test"}\n',
    )
    repository.write(
        "api.py",
        'from users import get_user as fetch\n\ndef api(id):\n    return fetch(id)["name"].upper()\n',
    )
    repository.write(
        "tests/test_users.py",
        "from users import get_user\n\ndef test_user():\n    assert get_user(None) is None\n",
    )
    head = repository.commit("head")
    workspace = Workspace.create(repository.path, tmp_path / "state", "test/project", base, head)
    return repository, workspace, CodeIntel(workspace)
