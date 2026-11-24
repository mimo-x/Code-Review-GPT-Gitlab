"""
Review services for GitLab code review
"""
import logging
import gitlab
from gitlab.exceptions import GitlabHttpError
from retrying import retry
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class DraftNotesUnsupported(Exception):
    """GitLab 版本过旧，没有草稿评论接口。"""


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
        从数据库加载GitLab配置，未配置时抛出异常
        """
        try:
            from apps.llm.models import GitLabConfig
        except ImportError as exc:
            logger.error(f"[{self.request_id}] 无法导入 GitLabConfig 模型: {exc}")
            raise ImproperlyConfigured("GitLabConfig 模型不可用，请检查应用安装和迁移") from exc

        gitlab_config = GitLabConfig.objects.filter(is_active=True).first()

        if not gitlab_config:
            error_msg = "未找到已激活的 GitLab 配置，请在管理后台创建并启用对应配置"
            logger.error(f"[{self.request_id}] {error_msg}")
            raise ImproperlyConfigured(error_msg)

        self.server_url = gitlab_config.server_url
        self.private_token = gitlab_config.private_token
        self.config_source = "database"
        logger.info(f"[{self.request_id}] GitLab配置加载成功 - 来源:数据库, 服务器:{self.server_url}")

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

    @property
    def current_user_id(self):
        """当前令牌对应的账号，用来识别机器人自己发过的评论。"""
        if not self.gl or not self.gl.user:
            raise RuntimeError("GitLab客户端未初始化")
        return self.gl.user.id

    def _merge_request(self, project_id, merge_request_iid):
        if not self.gl:
            raise RuntimeError("GitLab客户端未初始化")
        return self.gl.projects.get(project_id).mergerequests.get(merge_request_iid)

    def get_latest_diff_refs(self, project_id, merge_request_iid):
        """changes 接口还没有 diff_refs 时，从 MR 最新的 diff 版本读取。"""
        try:
            versions = self._merge_request(project_id, merge_request_iid).diffs.list(
                per_page=1, get_all=False
            )
        except Exception as e:
            logger.warning(f"[{self.request_id}] 读取 MR diff 版本失败: {e}")
            return None
        if not versions:
            return None
        version = versions[0]
        return {
            'base_sha': version.base_commit_sha,
            'start_sha': version.start_commit_sha,
            'head_sha': version.head_commit_sha,
        }

    def list_merge_request_discussions(self, project_id, merge_request_iid):
        merge_request = self._merge_request(project_id, merge_request_iid)
        return [d.attributes for d in merge_request.discussions.list(get_all=True)]

    def create_merge_request_discussion(self, project_id, merge_request_iid, body, position):
        """发布行内评论。写操作不自动重试，避免重复发布。"""
        merge_request = self._merge_request(project_id, merge_request_iid)
        return merge_request.discussions.create({'body': body, 'position': position})

    def update_merge_request_note(self, project_id, merge_request_iid, note_id, body):
        merge_request = self._merge_request(project_id, merge_request_iid)
        return merge_request.notes.update(note_id, {'body': body})

    # 草稿评论：先存成只有自己可见的草稿，再一次性发布成一轮 review。
    # python-gitlab 3.15 没有封装这组接口，直接走 HTTP。

    def _draft_notes_path(self, project_id, merge_request_iid):
        if not self.gl:
            raise RuntimeError("GitLab客户端未初始化")
        return f"/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes"

    def list_draft_notes(self, project_id, merge_request_iid):
        """当前账号在这个 MR 上未发布的草稿；GitLab 不支持草稿时抛出 DraftNotesUnsupported。"""
        path = self._draft_notes_path(project_id, merge_request_iid)
        try:
            return self.gl.http_list(path, get_all=True)
        except GitlabHttpError as exc:
            if exc.response_code in (404, 405):
                raise DraftNotesUnsupported(str(exc)) from exc
            raise

    def create_draft_note(self, project_id, merge_request_iid, body, position):
        path = self._draft_notes_path(project_id, merge_request_iid)
        return self.gl.http_post(path, post_data={'note': body, 'position': position})

    def delete_draft_note(self, project_id, merge_request_iid, draft_id):
        path = self._draft_notes_path(project_id, merge_request_iid)
        self.gl.http_delete(f"{path}/{draft_id}")

    def publish_draft_notes(self, project_id, merge_request_iid):
        """发布当前账号在这个 MR 上的全部草稿。"""
        path = self._draft_notes_path(project_id, merge_request_iid)
        self.gl.http_post(f"{path}/bulk_publish")

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
