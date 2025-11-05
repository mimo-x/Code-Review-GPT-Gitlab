"""
Review services for GitLab code review
"""
import os
import re
import shutil
import logging
import requests
from retrying import retry
from django.conf import settings

from apps.llm.services import LLMService
from utils.gitlab_parser import parse_diff_content

logger = logging.getLogger(__name__)


class GitlabService:
    """
    Service for interacting with GitLab API
    """

    def __init__(self):
        self.server_url = settings.GITLAB_SERVER_URL
        self.private_token = settings.GITLAB_PRIVATE_TOKEN
        self.headers = {
            "PRIVATE-TOKEN": self.private_token
        }

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_merge_request_changes(self, project_id, merge_request_iid):
        """
        Get the changes of a merge request
        """
        url = f"{self.server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/changes"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json().get("changes", [])
        except requests.RequestException as e:
            logger.error(f"Error fetching merge request changes: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_merge_request_info(self, project_id, merge_request_iid):
        """
        Get merge request information
        """
        url = f"{self.server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching merge request info: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_file_content(self, project_id, file_path, branch_name='main'):
        """
        Get the content of a file from repository
        """
        encoded_path = file_path.replace('/', '%2F')
        url = f"{self.server_url}/api/v4/projects/{project_id}/repository/files/{encoded_path}/raw?ref={branch_name}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching file content: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def post_merge_request_comment(self, project_id, merge_request_iid, comment):
        """
        Post a comment to a merge request
        """
        url = f"{self.server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/notes"

        data = {
            "body": comment
        }

        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            logger.info(f"Comment posted successfully to MR #{merge_request_iid}")
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error posting comment: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_project_info(self, project_id):
        """
        Get project information
        """
        url = f"{self.server_url}/api/v4/projects/{project_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching project info: {e}")
            return None


class ReviewService:
    """
    Service for performing code reviews
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.max_files = settings.GITLAB_MAX_FILES
        self.exclude_file_types = settings.EXCLUDE_FILE_TYPES
        self.ignore_file_types = settings.IGNORE_FILE_TYPES
        self.context_lines = settings.CONTEXT_LINES_NUM

    def review_merge_request(self, changes, payload):
        """
        Review a merge request
        """
        try:
            # Filter changes
            filtered_changes = self._filter_changes(changes)

            if not filtered_changes:
                return {
                    'content': '没有需要审查的代码变更',
                    'score': None,
                    'files_reviewed': []
                }

            # Limit number of files
            if len(filtered_changes) > self.max_files:
                logger.warning(f"Too many files changed ({len(filtered_changes)}), limiting to {self.max_files}")
                filtered_changes = filtered_changes[:self.max_files]

            # Build review context
            review_context = self._build_review_context(filtered_changes)

            # Get review from LLM
            review_result = self.llm_service.review_code(review_context)

            # Parse review result
            parsed_result = self._parse_review_result(review_result)

            parsed_result['files_reviewed'] = [change['new_path'] for change in filtered_changes]

            return parsed_result

        except Exception as e:
            logger.error(f"Error reviewing merge request: {e}", exc_info=True)
            return {
                'content': f'代码审查失败: {str(e)}',
                'score': None,
                'files_reviewed': []
            }

    def _filter_changes(self, changes):
        """
        Filter changes based on file types
        """
        filtered = []

        for change in changes:
            # Skip deleted files
            if change.get('deleted_file'):
                continue

            # Skip renamed files without content changes
            if change.get('renamed_file') and change.get('diff') == '':
                continue

            file_path = change.get('new_path', '')

            # Check if file type should be excluded
            should_exclude = False
            for exclude_type in self.exclude_file_types:
                if file_path.endswith(exclude_type.strip()):
                    should_exclude = False
                    break

            # Check if file should be ignored
            for ignore_pattern in self.ignore_file_types:
                if ignore_pattern.strip() in file_path:
                    should_exclude = True
                    break

            if not should_exclude:
                filtered.append(change)

        return filtered

    def _build_review_context(self, changes):
        """
        Build review context from changes
        """
        context_parts = []

        for change in changes:
            file_path = change.get('new_path', 'unknown')
            diff = change.get('diff', '')

            context_parts.append(f"\n## 文件: {file_path}\n")
            context_parts.append(f"```diff\n{diff}\n```\n")

        return '\n'.join(context_parts)

    def _parse_review_result(self, review_content):
        """
        Parse LLM review result to extract score and content
        """
        score = None

        # Try to extract score from content
        score_pattern = r'代码评分[:\s]*(\d+)'
        score_match = re.search(score_pattern, review_content)

        if score_match:
            try:
                score = int(score_match.group(1))
            except ValueError:
                pass

        return {
            'content': review_content,
            'score': score
        }
