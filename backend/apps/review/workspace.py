"""审查用的代码工作区：每个项目一个 bare 镜像，每次审查一个按 SHA 检出的临时工作树。"""
from __future__ import annotations

import base64
import fcntl
import logging
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

from .engines.base import Revisions

logger = logging.getLogger(__name__)

_FULL_HISTORY_DEPTH = "2147483647"
_LOCK_TIMEOUT_S = 600
_STALE_WORKTREE_S = 24 * 3600
_GIT_TIMEOUT_S = 300


class WorkspaceError(Exception):
    """仓库无法准备好。"""


class RepositoryWorkspace:
    def __init__(self, base_path=None, request_id=None):
        self.base_path = Path(base_path or settings.REPOSITORY_BASE_PATH)
        self.request_id = request_id
        self.mirrors = self.base_path / "mirrors"
        self.worktrees = self.base_path / "worktrees"
        self.mirrors.mkdir(parents=True, exist_ok=True)
        self.worktrees.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def checkout(self, project_id, clone_url, access_token, revisions: Revisions,
                 mr_iid, target_branch):
        """提供固定在 head_sha 的工作树，退出时删除。令牌不会落到磁盘。"""
        mirror = self.mirrors / f"project-{project_id}.git"
        worktree = self.worktrees / f"project-{project_id}-{uuid.uuid4().hex}"
        env = _git_env(access_token)
        with self._project_lock(project_id):
            self._remove_stale_worktrees(mirror, project_id)
            self._ensure_mirror(mirror)
            self._fetch(mirror, clone_url, env, revisions, mr_iid, target_branch)
            try:
                self._git(mirror, env, "worktree", "add", "--detach", str(worktree),
                          revisions.head_sha)
            except Exception:
                # 超时等情况下目录可能已经建了一半
                self._remove_worktree(mirror, worktree)
                raise
        try:
            yield worktree
        finally:
            with self._project_lock(project_id):
                self._remove_worktree(mirror, worktree)

    def _ensure_mirror(self, mirror: Path) -> None:
        if not (mirror / "HEAD").exists():
            subprocess.run(
                ["git", "init", "--bare", "--quiet", str(mirror)],
                check=True, capture_output=True, timeout=30,
            )

    def _fetch(self, mirror, clone_url, env, revisions, mr_iid, target_branch) -> None:
        missing = [sha for sha in revisions.unique if not self._has_commit(mirror, sha)]
        if not missing:
            return
        try:
            self._git(mirror, env, "fetch", "--no-tags", "--depth=1", clone_url, *missing)
        except WorkspaceError as exc:
            logger.info("[%s] 按 SHA 拉取失败，改拉 MR 引用: %s", self.request_id, exc)
        missing = [sha for sha in missing if not self._has_commit(mirror, sha)]
        if not missing:
            return
        # 服务端不允许按 SHA 拉取时，退回到 MR 引用和目标分支的完整历史
        self._git(
            mirror, env, "fetch", "--no-tags", f"--depth={_FULL_HISTORY_DEPTH}", clone_url,
            f"+refs/merge-requests/{mr_iid}/head:refs/review/mr-{mr_iid}",
            f"+refs/heads/{target_branch}:refs/review/target-{mr_iid}",
        )
        missing = [sha for sha in missing if not self._has_commit(mirror, sha)]
        if missing:
            raise WorkspaceError(f"找不到提交: {', '.join(sha[:8] for sha in missing)}")

    def _has_commit(self, mirror: Path, sha: str) -> bool:
        result = subprocess.run(
            ["git", f"--git-dir={mirror}", "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0

    def _remove_worktree(self, mirror: Path, worktree: Path) -> None:
        try:
            self._git(mirror, _git_env(None), "worktree", "remove", "--force", str(worktree))
        except WorkspaceError as exc:
            logger.warning("[%s] 删除工作树失败: %s", self.request_id, exc)
            shutil.rmtree(worktree, ignore_errors=True)
            self._git(mirror, _git_env(None), "worktree", "prune")

    def _remove_stale_worktrees(self, mirror: Path, project_id) -> None:
        """回收进程崩溃后遗留的工作树。"""
        cutoff = time.time() - _STALE_WORKTREE_S
        stale = [
            path for path in self.worktrees.glob(f"project-{project_id}-*")
            if path.stat().st_mtime < cutoff
        ]
        for path in stale:
            shutil.rmtree(path, ignore_errors=True)
        if stale and mirror.exists():
            self._git(mirror, _git_env(None), "worktree", "prune")

    def _git(self, mirror: Path, env: dict, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", f"--git-dir={mirror}", *args],
                env=env, capture_output=True, text=True, timeout=_GIT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceError(f"git {args[0]} 超时") from exc
        if result.returncode != 0:
            raise WorkspaceError(f"git {args[0]} 失败: {result.stderr.strip()[:300]}")
        return result.stdout

    @contextmanager
    def _project_lock(self, project_id):
        """跨进程互斥；用非阻塞重试，避免卡住 gevent worker 的事件循环。"""
        lock_path = self.base_path / f".project-{project_id}.lock"
        with open(lock_path, "w") as lock_file:
            deadline = time.monotonic() + _LOCK_TIMEOUT_S
            while True:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise WorkspaceError("等待仓库锁超时") from None
                    time.sleep(0.2)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)


def _git_env(access_token: str | None) -> dict[str, str]:
    """通过环境变量传认证头，令牌不进命令行、不进 .git/config。"""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    if access_token:
        credentials = base64.b64encode(f"oauth2:{access_token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credentials}",
        })
    return env
