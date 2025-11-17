"""
Review services for GitLab code review
"""
import os
import re
import shutil
import logging
import gitlab
from retrying import retry
from django.conf import settings

from apps.llm.services import LLMService
from utils.gitlab_parser import parse_diff_content

logger = logging.getLogger(__name__)


class GitlabService:
    """
    Service for interacting with GitLab API using python-gitlab library
    """

    def __init__(self, request_id=None):
        self.request_id = request_id
        self._load_config()
        self._init_gitlab_client()

    def _load_config(self):
        """
        从数据库加载GitLab配置，如果找不到活跃配置则回退到环境变量
        """
        try:
            from apps.llm.models import GitLabConfig
            gitlab_config = GitLabConfig.objects.filter(is_active=True).first()

            if gitlab_config:
                self.server_url = gitlab_config.server_url
                self.private_token = gitlab_config.private_token
                self.config_source = "database"
                logger.info(f"[{self.request_id}] GitLab配置加载成功 - 来源:数据库, 服务器:{self.server_url}")
            else:
                # 回退到环境变量
                self.server_url = getattr(settings, 'GITLAB_SERVER_URL', 'https://gitlab.com')
                self.private_token = getattr(settings, 'GITLAB_PRIVATE_TOKEN', '')
                self.config_source = "environment"
                logger.info(f"[{self.request_id}] GitLab配置加载成功 - 来源:环境变量, 服务器:{self.server_url}")

        except ImportError:
            logger.warning(f"[{self.request_id}] 无法导入GitLabConfig模型，使用环境变量配置")
            self.server_url = getattr(settings, 'GITLAB_SERVER_URL', 'https://gitlab.com')
            self.private_token = getattr(settings, 'GITLAB_PRIVATE_TOKEN', '')
            self.config_source = "environment"
        except Exception as e:
            logger.error(f"[{self.request_id}] GitLab配置加载失败: {e}", exc_info=True)
            # 使用环境变量作为最后回退
            self.server_url = getattr(settings, 'GITLAB_SERVER_URL', 'https://gitlab.com')
            self.private_token = getattr(settings, 'GITLAB_PRIVATE_TOKEN', '')
            self.config_source = "environment"

    def _init_gitlab_client(self):
        """
        初始化GitLab客户端
        """
        try:
            # 打印配置信息（隐藏敏感信息）
            masked_token = f"{self.private_token[:8]}...{self.private_token[-8:]}" if len(self.private_token) > 16 else "***"
            logger.info(f"[{self.request_id}] 开始初始化GitLab客户端 - 服务器:{self.server_url}, Token:{masked_token}")

            self.gl = gitlab.Gitlab(
                self.server_url,
                private_token=self.private_token,
                timeout=30
            )
            # 测试连接
            self.gl.auth()
            logger.info(f"[{self.request_id}] GitLab客户端初始化成功")
        except Exception as e:
            # 打印详细的错误信息和参数
            masked_token = f"{self.private_token[:8]}...{self.private_token[-8:]}" if len(self.private_token) > 16 else "***"
            logger.error(f"[{self.request_id}] GitLab客户端初始化失败")
            logger.error(f"[{self.request_id}] 详细参数:")
            logger.error(f"[{self.request_id}]   - 服务器URL: {self.server_url}")
            logger.error(f"[{self.request_id}]   - Token: {masked_token} (长度: {len(self.private_token)})")
            logger.error(f"[{self.request_id}]   - 配置来源: {self.config_source}")
            logger.error(f"[{self.request_id}]   - 错误类型: {type(e).__name__}")
            logger.error(f"[{self.request_id}]   - 错误信息: {str(e)}")
            self.gl = None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_merge_request_changes(self, project_id, merge_request_iid):
        """
        Get the changes of a merge request using python-gitlab library
        Returns the full response object including 'changes' field
        """
        if not self.gl:
            logger.error(f"[{self.request_id}] GitLab客户端未初始化")
            return None

        try:
            project = self.gl.projects.get(project_id)
            merge_request = project.mergerequests.get(merge_request_iid)
            changes = merge_request.changes()

            # changes() 已经返回字典格式，直接返回
            return changes
        except Exception as e:
            logger.error(f"[{self.request_id}] Error fetching merge request changes: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_merge_request_info(self, project_id, merge_request_iid):
        """
        Get merge request information using python-gitlab library
        """
        if not self.gl:
            logger.error(f"[{self.request_id}] GitLab客户端未初始化")
            return None

        try:
            project = self.gl.projects.get(project_id)
            merge_request = project.mergerequests.get(merge_request_iid)
            return merge_request.asdict()
        except Exception as e:
            logger.error(f"[{self.request_id}] Error fetching merge request info: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_file_content(self, project_id, file_path, branch_name='main'):
        """
        Get the content of a file from repository using python-gitlab library
        """
        if not self.gl:
            logger.error(f"[{self.request_id}] GitLab客户端未初始化")
            return None

        try:
            project = self.gl.projects.get(project_id)
            file_obj = project.files.get(file_path=file_path, ref=branch_name)
            return file_obj.decode()
        except Exception as e:
            logger.error(f"[{self.request_id}] Error fetching file content: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def post_merge_request_comment(self, project_id, merge_request_iid, comment):
        """
        Post a comment to a merge request using python-gitlab library
        """
        if not self.gl:
            logger.error(f"[{self.request_id}] GitLab客户端未初始化")
            return None

        try:
            project = self.gl.projects.get(project_id)
            merge_request = project.mergerequests.get(merge_request_iid)
            note = merge_request.notes.create({'body': comment})
            logger.info(f"[{self.request_id}] Comment posted successfully to MR #{merge_request_iid}")
            return note.asdict()
        except Exception as e:
            logger.error(f"[{self.request_id}] Error posting comment: {e}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_project_info(self, project_id):
        """
        Get project information using python-gitlab library
        """
        if not self.gl:
            logger.error(f"[{self.request_id}] GitLab客户端未初始化")
            return None

        try:
            project = self.gl.projects.get(project_id)
            return project.asdict()
        except Exception as e:
            logger.error(f"[{self.request_id}] Error fetching project info: {e}")
            return None


class ReviewService:
    """
    Service for performing code reviews
    """

    def __init__(self, project_id=None, request_id=None):
        self.project_id = project_id
        self.request_id = request_id
        self.llm_service = LLMService(request_id=request_id)
        self._load_config()

    def _load_config(self):
        """
        从数据库加载配置（优先级：项目配置 > 全局配置 > 环境变量）
        """
        try:
            from apps.llm.models import GitLabConfig
            from apps.webhook.models import Project
            
            # 尝试加载项目级配置
            if self.project_id:
                try:
                    project = Project.objects.get(project_id=self.project_id)
                    # 如果项目有自定义配置，使用项目配置
                    if project.exclude_file_types_list:
                        self.exclude_file_types = project.exclude_file_types_list
                    else:
                        self.exclude_file_types = getattr(settings, 'EXCLUDE_FILE_TYPES', [])
                    
                    if project.ignore_file_patterns_list:
                        self.ignore_file_types = project.ignore_file_patterns_list
                    else:
                        self.ignore_file_types = getattr(settings, 'IGNORE_FILE_TYPES', [])
                    
                    logger.info(f"[{self.request_id}] 使用项目级配置 - 项目ID:{self.project_id}")
                except Project.DoesNotExist:
                    # 项目不存在，使用默认配置
                    self.exclude_file_types = getattr(settings, 'EXCLUDE_FILE_TYPES', [])
                    self.ignore_file_types = getattr(settings, 'IGNORE_FILE_TYPES', [])
            else:
                # 没有项目ID，使用全局配置
                self.exclude_file_types = getattr(settings, 'EXCLUDE_FILE_TYPES', [])
                self.ignore_file_types = getattr(settings, 'IGNORE_FILE_TYPES', [])

            logger.info(f"[{self.request_id}] Review配置加载成功")

        except ImportError:
            logger.warning(f"[{self.request_id}] 无法导入配置模型，使用环境变量配置")
            self.exclude_file_types = getattr(settings, 'EXCLUDE_FILE_TYPES', [])
            self.ignore_file_types = getattr(settings, 'IGNORE_FILE_TYPES', [])
        except Exception as e:
            logger.error(f"[{self.request_id}] Review配置加载失败: {e}", exc_info=True)
            # 使用环境变量作为最后回退
            self.exclude_file_types = getattr(settings, 'EXCLUDE_FILE_TYPES', [])
            self.ignore_file_types = getattr(settings, 'IGNORE_FILE_TYPES', [])

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
