import os
import re
import shutil
import subprocess
import time

import requests
from retrying import retry
from config.config import *
from utils.logger import log
from utils.tools import run_command


class GitlabMergeRequestFetcher:
    def __init__(self, project_id, merge_request_iid):
        self.project_id = project_id
        self.iid = merge_request_iid
        self._changes_cache = None
        self._file_content_cache = {}
        self._info_cache = None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_changes(self, force=False):
        """
        Get the changes of the merge request
        :return: changes
        """
        if self._changes_cache and not force:
            return self._changes_cache
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}/changes"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": gitlab_private_token
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._changes_cache = response.json()["changes"]
            return response.json()["changes"]
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    # 获取文件内容
    def get_file_content(self, file_path, branch_name='main', force=False):
        """
        Get the content of the file
        :param file_path: The path of the file
        :return: The content of the file
        """
        # 对file_path中的'/'转换为'%2F'
        file_path = file_path.replace('/', '%2F')
        if file_path in self._file_content_cache and not force:
            return self._file_content_cache[file_path]
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}/repository/files/{file_path}/raw?ref={branch_name}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": gitlab_private_token
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._file_content_cache[file_path] = response.text
            return response.text
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_info(self, force=False):
        """
        Get the merge request information
        :return: Merge request information
        """
        if self._info_cache and not force:
            return self._info_cache
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": gitlab_private_token
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._info_cache = response.json()
            return response.json()
        else:
            return None

# gitlab仓库clone和管理
class GitlabRepoManager:
    def __init__(self, project_id, branch_name = ""):
        self.project_id = project_id
        self.timestamp = int(time.time() * 1000)
        self.repo_path = f"./repo/{self.project_id}_{self.timestamp}"
        self.has_cloned = False

    def get_info(self):
        """
        Get the project information
        :return: Project information
        """
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": gitlab_private_token
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def shallow_clone(self, branch_name = "main"):
        """
        Perform a shallow clone of the repository
        param branch_name: The name of the branch to clone
        """
        # If the target directory exists, remove it
        self.delete_repo()

        # Build the authenticated URL
        authenticated_url = self._build_authenticated_url(self.get_info()["http_url_to_repo"])

        # Build the Git command
        command = ["git", "clone", authenticated_url, "--depth", "1"]
        if branch_name:
            command.extend(["--branch", branch_name])
            command.extend([self.repo_path + "/" + str(branch_name)])
        else:
            command.extend([self.repo_path + "/default"])
        # command 添加clone到的位置：
        if run_command(command) != 0:
            log.error("Failed to clone the repository")
        self.has_cloned = True

    # 切换分支
    def checkout_branch(self, branch_name, force=False):
        # Build the Git command
        if not self.has_cloned:
            self.shallow_clone(branch_name)
        else:
            # 检查是否已经在目标分支上
            if not force and os.path.exists(self.repo_path + "/" + str(branch_name) + "/.git"):
                return
            else:
                self.shallow_clone(branch_name)

    # 删除库
    def delete_repo(self):
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

    # 查找相关文件列表
    def find_files_by_keyword(self, keyword, branch_name="main"):
        matching_files = []
        regex = re.compile(keyword)
        self.checkout_branch(branch_name)
        for root, _, files in os.walk(self.repo_path + "/" + str(branch_name)):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if regex.search(content):
                            matching_files.append(file_path)
                except (UnicodeDecodeError, FileNotFoundError, PermissionError):
                    # 跳过无法读取的文件
                    continue

        return matching_files


    # 构建带有身份验证信息的 URL
    def _build_authenticated_url(self, repo_url):
        # 如果 URL 使用 https
        token = gitlab_private_token
        if repo_url.startswith("https://"):
            return f"https://oauth2:{token}@{repo_url[8:]}"
        # 如果 URL 使用 http
        elif repo_url.startswith("http://"):
            return f"http://oauth2:{token}@{repo_url[7:]}"
        else:
            raise ValueError("Unsupported URL scheme")