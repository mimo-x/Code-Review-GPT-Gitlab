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
        """
        Initialize a GitLab merge request fetcher.
        
        Assigns the project identifier and merge request IID, and sets up caches for
        tracking changes, file content, and merge request information.
        
        Parameters:
            project_id: The unique identifier for the GitLab project.
            merge_request_iid: The internal identifier for the merge request.
        """
        self.project_id = project_id
        self.iid = merge_request_iid
        self._changes_cache = None
        self._file_content_cache = {}
        self._info_cache = None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_changes(self, force=False):
        """
        Retrieve merge request changes via GitLab API.
        
        If cached changes are available and force is False, returns the cached data.
        Otherwise, performs a GET request to fetch the latest changes, caches them on success,
        and returns the list of changes. Returns None if the API request fails.
        
        Args:
            force (bool): If True, bypasses the cache to fetch fresh changes.
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
        Fetch the raw content of a repository file via the GitLab API.
        
        This method retrieves the file content from the specified branch by making a GET
        request to the GitLab API. The provided file path is URL-encoded for proper API
        endpoint formatting. Cached content is returned if available, unless the force
        flag is set to True.
        
        Args:
            file_path: The repository path of the file; forward slashes are URL-encoded.
            branch_name: The branch to fetch the file from (default is 'main').
            force: If True, bypasses the cache to retrieve fresh content.
        
        Returns:
            The raw file content as a string if the request is successful; otherwise, None.
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
        Retrieve merge request information.
        
        If cached data is available and force is False, the cached merge request details
        are returned. Otherwise, the method calls the GitLab API to fetch fresh information,
        caches the result, and returns it. If the API request fails, None is returned.
        
        Args:
            force (bool): If True, bypass the cache and retrieve fresh data.
        
        Returns:
            dict or None: The merge request information if successful; otherwise, None.
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
        """
        Initialize a GitlabRepoManager instance.
        
        Creates a unique repository path by combining the provided project ID with the current
        timestamp. The repository is initially marked as not cloned. The optional branch name
        parameter is accepted for potential branch-related operations, although it is not used
        during initialization.
        
        Args:
            project_id: Identifier for the GitLab project.
            branch_name: Optional branch name for repository operations.
        """
        self.project_id = project_id
        self.timestamp = int(time.time() * 1000)
        self.repo_path = f"./repo/{self.project_id}_{self.timestamp}"
        self.has_cloned = False

    def get_info(self):
        """
        Retrieve project information from GitLab.
        
        Makes a GET request to the GitLab API to fetch details for the project identified by the
        instance's project_id. Returns the JSON-decoded response if the request is successful (HTTP 200);
        otherwise, returns None.
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
        Shallow clones the repository to a local directory.
        
        Deletes any existing local clone, constructs an authenticated Git URL using
        repository information, and executes a shallow clone (depth of 1) for the specified
        branch. If cloning fails, an error is logged; otherwise, the repository is marked
        as cloned.
        
        Args:
            branch_name (str): The branch to clone (default "main").
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
        """
        Checks out the specified branch by performing a shallow clone if necessary.
        
        If the repository has not been cloned already, the method executes a shallow clone for the target branch.
        If the repository is already cloned, it verifies whether the branch is already checked out (unless forced)
        and performs a shallow clone if the branch differs or if force is True.
        
        Args:
            branch_name: The name of the branch to check out.
            force: If True, forces re-cloning of the branch even if it appears to be already checked out.
        """
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
        """
        Deletes the cloned repository directory if it exists.
        
        This method checks whether the repository path exists on the filesystem and removes it along with its contents. If the directory is not present, no action is taken.
        """
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

    # 查找相关文件列表
    def find_files_by_keyword(self, keyword, branch_name="main"):
        """
        Search for files whose content matches a regex pattern.
        
        Checks out the specified branch and recursively searches for files whose content
        matches the provided regular expression. Files that cannot be read due to encoding,
        permission, or existence issues are skipped.
        
        Args:
            keyword: Regular expression pattern to search for in file contents.
            branch_name: Branch to search in; defaults to "main".
        
        Returns:
            A list of file paths for files containing a match to the keyword.
        """
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
        """
        Builds an authenticated URL for repository access.
        
        This method embeds an OAuth2 token into the provided repository URL, supporting only
        URLs beginning with "http://" or "https://". For HTTPS URLs, it returns a URL in the
        format "https://oauth2:{token}@<rest_of_url>" and similarly for HTTP URLs. If the URL
        scheme is unsupported, a ValueError is raised.
        """
        token = gitlab_private_token
        if repo_url.startswith("https://"):
            return f"https://oauth2:{token}@{repo_url[8:]}"
        # 如果 URL 使用 http
        elif repo_url.startswith("http://"):
            return f"http://oauth2:{token}@{repo_url[7:]}"
        else:
            raise ValueError("Unsupported URL scheme")