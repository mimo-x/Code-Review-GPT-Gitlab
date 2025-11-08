"""
Repository Manager for Code Review
Handles Git repository cloning, updating, and branch management
"""
import os
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Manages local Git repositories for code review
    """

    def __init__(self, request_id=None):
        self.request_id = request_id
        self.base_path = getattr(settings, 'REPOSITORY_BASE_PATH', '/tmp/code-review-repositories')
        self._ensure_base_directory()

    def _ensure_base_directory(self):
        """确保基础目录存在"""
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"[{self.request_id}] Repository base path: {self.base_path}")

    def _get_project_path(self, project_id):
        """获取项目的本地路径"""
        return os.path.join(self.base_path, f"project-{project_id}")

    def _run_git_command(self, command, cwd=None, timeout=300):
        """
        执行 Git 命令

        Args:
            command: Git 命令列表
            cwd: 工作目录
            timeout: 超时时间（秒）

        Returns:
            (success, output, error)
        """
        try:
            logger.info(f"[{self.request_id}] Executing git command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )

            if result.returncode == 0:
                logger.info(f"[{self.request_id}] Git command succeeded")
                return True, result.stdout, result.stderr
            else:
                logger.error(f"[{self.request_id}] Git command failed: {result.stderr}")
                return False, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            logger.error(f"[{self.request_id}] Git command timeout after {timeout}s")
            return False, "", f"Command timeout after {timeout}s"
        except Exception as e:
            logger.error(f"[{self.request_id}] Git command error: {e}", exc_info=True)
            return False, "", str(e)

    def get_or_clone_repository(self, project_url, project_id, access_token=None):
        """
        获取或克隆项目仓库

        Args:
            project_url: GitLab 项目 URL
            project_id: 项目 ID
            access_token: GitLab Access Token

        Returns:
            (success, repo_path, error_message)
        """
        repo_path = self._get_project_path(project_id)

        # 如果仓库已存在，尝试更新
        if os.path.exists(repo_path):
            logger.info(f"[{self.request_id}] Repository exists at {repo_path}, updating...")
            success = self._update_repository(repo_path)
            if success:
                return True, repo_path, None
            else:
                # 更新失败，删除并重新克隆
                logger.warning(f"[{self.request_id}] Update failed, removing and re-cloning...")
                shutil.rmtree(repo_path, ignore_errors=True)

        # 克隆新仓库
        logger.info(f"[{self.request_id}] Cloning repository from {project_url}")

        # 构建带 token 的 URL
        clone_url = self._build_authenticated_url(project_url, access_token)

        # 记录认证 URL（隐藏 token）
        if access_token and '@' in clone_url:
            masked_url = clone_url.replace(access_token, '****')
            logger.info(f"[{self.request_id}] Using authenticated URL: {masked_url}")
        else:
            logger.warning(f"[{self.request_id}] No authentication added to URL!")

        # 使用浅克隆以提高速度
        success, stdout, stderr = self._run_git_command([
            'git', 'clone',
            '--depth', '1',
            '--no-single-branch',  # 获取所有分支
            clone_url,
            repo_path
        ])

        if success:
            logger.info(f"[{self.request_id}] Repository cloned successfully to {repo_path}")
            return True, repo_path, None
        else:
            error_msg = f"Failed to clone repository: {stderr}"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, None, error_msg

    def _update_repository(self, repo_path):
        """
        更新已存在的仓库

        Args:
            repo_path: 仓库路径

        Returns:
            success (bool)
        """
        # 重置到干净状态
        self._run_git_command(['git', 'reset', '--hard'], cwd=repo_path)
        self._run_git_command(['git', 'clean', '-fd'], cwd=repo_path)

        # 拉取最新更新
        success, stdout, stderr = self._run_git_command(
            ['git', 'fetch', '--all', '--prune'],
            cwd=repo_path
        )

        return success

    def checkout_merge_request(self, repo_path, mr_iid, source_branch, target_branch='main'):
        """
        切换到 Merge Request 对应的分支

        Args:
            repo_path: 仓库路径
            mr_iid: MR IID
            source_branch: 源分支
            target_branch: 目标分支

        Returns:
            (success, error_message)
        """
        logger.info(f"[{self.request_id}] Checking out MR #{mr_iid} branch: {source_branch}")

        # 尝试切换到源分支
        success, stdout, stderr = self._run_git_command(
            ['git', 'checkout', source_branch],
            cwd=repo_path
        )

        if success:
            # 拉取最新更新
            self._run_git_command(['git', 'pull'], cwd=repo_path)
            logger.info(f"[{self.request_id}] Checked out branch {source_branch}")
            return True, None
        else:
            # 尝试从远程创建分支
            success, stdout, stderr = self._run_git_command(
                ['git', 'checkout', '-b', source_branch, f'origin/{source_branch}'],
                cwd=repo_path
            )

            if success:
                logger.info(f"[{self.request_id}] Created and checked out branch {source_branch}")
                return True, None
            else:
                error_msg = f"Failed to checkout branch {source_branch}: {stderr}"
                logger.error(f"[{self.request_id}] {error_msg}")
                return False, error_msg

    def get_commit_range(self, repo_path, target_branch='main'):
        """
        获取当前分支相对于目标分支的提交范围

        Args:
            repo_path: 仓库路径
            target_branch: 目标分支

        Returns:
            (success, commit_range, error_message)
        """
        # 获取当前分支名
        success, current_branch, stderr = self._run_git_command(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path
        )

        if not success:
            return False, None, f"Failed to get current branch: {stderr}"

        current_branch = current_branch.strip()

        # 获取 merge base
        success, merge_base, stderr = self._run_git_command(
            ['git', 'merge-base', f'origin/{target_branch}', current_branch],
            cwd=repo_path
        )

        if not success:
            # 如果找不到 merge base，使用最近一次提交
            logger.warning(f"[{self.request_id}] Cannot find merge base, using HEAD")
            return True, "HEAD~1..HEAD", None

        merge_base = merge_base.strip()
        commit_range = f"{merge_base}..HEAD"

        logger.info(f"[{self.request_id}] Commit range: {commit_range}")
        return True, commit_range, None

    def _build_authenticated_url(self, project_url, access_token):
        """
        构建带认证信息的 Git URL

        Args:
            project_url: 项目 URL
            access_token: Access Token

        Returns:
            带认证的 URL
        """
        if not access_token:
            return project_url

        # 处理 HTTPS URL
        if project_url.startswith('https://'):
            # 格式: https://oauth2:TOKEN@gitlab.com/user/repo.git
            url_parts = project_url.replace('https://', '').split('/', 1)
            if len(url_parts) == 2:
                host, path = url_parts
                return f"https://oauth2:{access_token}@{host}/{path}"

        # 处理 HTTP URL（用于本地开发环境）
        if project_url.startswith('http://'):
            # 格式: http://oauth2:TOKEN@localhost/user/repo.git
            url_parts = project_url.replace('http://', '').split('/', 1)
            if len(url_parts) == 2:
                host, path = url_parts
                return f"http://oauth2:{access_token}@{host}/{path}"

        return project_url

    def cleanup_old_repositories(self, days=7):
        """
        清理超过指定天数的旧仓库

        Args:
            days: 保留天数

        Returns:
            (cleaned_count, total_size_freed)
        """
        logger.info(f"[{self.request_id}] Starting repository cleanup (older than {days} days)")

        if not os.path.exists(self.base_path):
            return 0, 0

        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        total_size_freed = 0

        for item in os.listdir(self.base_path):
            item_path = os.path.join(self.base_path, item)

            if not os.path.isdir(item_path):
                continue

            # 检查最后修改时间
            mtime = datetime.fromtimestamp(os.path.getmtime(item_path))

            if mtime < cutoff_time:
                try:
                    # 计算大小
                    size = self._get_directory_size(item_path)

                    # 删除目录
                    shutil.rmtree(item_path)

                    cleaned_count += 1
                    total_size_freed += size

                    logger.info(f"[{self.request_id}] Removed old repository: {item} ({size / 1024 / 1024:.2f} MB)")

                except Exception as e:
                    logger.error(f"[{self.request_id}] Failed to remove {item_path}: {e}")

        logger.info(f"[{self.request_id}] Cleanup complete: {cleaned_count} repos, {total_size_freed / 1024 / 1024:.2f} MB freed")
        return cleaned_count, total_size_freed

    def _get_directory_size(self, path):
        """获取目录大小（字节）"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size

    def get_repository_info(self, repo_path):
        """
        获取仓库基本信息

        Args:
            repo_path: 仓库路径

        Returns:
            dict with repo info
        """
        info = {}

        # 当前分支
        success, branch, _ = self._run_git_command(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path
        )
        info['current_branch'] = branch.strip() if success else 'unknown'

        # 最新提交
        success, commit, _ = self._run_git_command(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path
        )
        info['latest_commit'] = commit.strip() if success else 'unknown'

        # 最新提交信息
        success, message, _ = self._run_git_command(
            ['git', 'log', '-1', '--pretty=%B'],
            cwd=repo_path
        )
        info['latest_commit_message'] = message.strip() if success else 'unknown'

        return info
