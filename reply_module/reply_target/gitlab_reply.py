import requests
from retrying import retry
from config.config import *
from reply_module.reply_target.abstract_reply import AbstractReply
from utils.logger import log

# 继承AbstractReply类，实现send方法
class GitlabReply(AbstractReply):
    def __init__(self, project_id, merge_request_id):
        super().__init__(project_id, merge_request_id)

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def send(self, message):
        headers = {
            "Private-Token": gitlab_private_token,
            "Content-Type": "application/json"
        }
        project_id = self.project_id
        merge_request_id = self.merge_request_id
        url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_id}/notes"
        data = {
            "body": message
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            log.info(f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id}")
            return True
        else:
            log.error(
                f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id} response:{response}")
            return False

if __name__ == '__main__':
    gitlab_reply = GitlabReply(9885, 18)
    gitlab_reply.send("test")