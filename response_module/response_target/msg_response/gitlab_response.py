import requests
from retrying import retry
from config.config import *
from response_module.abstract_response import AbstractResponse
from utils.logger import log

# 继承AbstractReply类，实现send方法
class GitlabResponse(AbstractResponse):
    def __init__(self, config):
        super().__init__(config)
        self.type = config['type']
        if self.type == 'merge_request':
            self.project_id = config['project_id']
            self.merge_request_id = config['merge_request_iid']

    def send(self, message):
        if self.type == 'merge_request':
            return self.send_merge(message)
        else:
            return False

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def send_merge(self, message):
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