import base64
import hashlib
import hmac
import time
import urllib
import requests
import json
from config.config import *
from utils.logger import *
from response_module.abstract_response import AbstractResponseMessage


class DingtalkResponse(AbstractResponseMessage):
    def __init__(self, config):
        """
        Initializes the DingtalkResponse instance with configuration settings.
        
        Processes the provided configuration dictionary to set the response type. If the
        type is 'merge_request', additional identifiers for the project and merge request
        are initialized from the configuration.
        
        Args:
            config (dict): Dictionary containing configuration parameters. Must include
                a 'type' key, and if 'type' is 'merge_request', also 'project_id' and
                'merge_request_iid' keys.
        """
        super().__init__(config)
        self.type = config['type']
        if self.type == 'merge_request':
            self.project_id = config['project_id']
            self.merge_request_id = config['merge_request_iid']

    def send(self, message):
        if self.type == 'merge_request':
            return self.send_dingtalk_message_by_sign(message)
        else:
            return False

    def send_dingtalk_message_by_sign(self, message_text):
        """
        使用签名方式发送消息通知到钉钉群

        Args:
            message_text (str): 消息文本内容

        Returns:
            bool: 消息是否发送成功
        """
        timestamp = str(round(time.time() * 1000))
        sign = self.__get_sign(timestamp)
        webhookurl = f"{dingding_bot_webhook}&timestamp={timestamp}&sign={sign}"
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
        }

        # 构建请求体
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": "Gitlab 通知",
                "text": message_text
            },
            "timestamp": timestamp,
            "sign": sign
        }

        # 发送HTTP POST请求
        response = requests.post(
            webhookurl,
            headers=headers,
            data=json.dumps(message)
        )

        # 检查响应
        if response.status_code == 200 and response.json()["errcode"] == 0:
            log.info(f"评论信息发送成功：project_id:{self.project_id}  merge_request_id:{self.merge_request_id}")
            return True
        else:
            log.error(
                f"评论信息发送失败：project_id:{self.project_id}  merge_request_id:{self.merge_request_id} response:{response}")
            return False

    def send_dingtalk_message_by_key_word(self, project_url):
        """
        通过关键词发送

        """
        # 设置钉钉机器人的 Webhook URL
        webhook_url = dingding_bot_webhook

        # 要发送的消息内容
        message = f"新工程接入\nurl：{project_url}"

        headers = {"Content-Type": "application/json"}
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload))
        return response.json()

    def __get_sign(self, timestamp):
        """
        Computes a URL-encoded HMAC-SHA256 signature for the provided timestamp.
        
        This method concatenates the given timestamp and a predefined secret with a newline,
        computes the HMAC-SHA256 hash of the resulting string using the secret as the key,
        encodes the hash in Base64, and then URL-encodes the result.
        
        Parameters:
            timestamp: The timestamp used in signature generation.
        
        Returns:
            The URL-encoded signature string.
        """

        secret = dingding_secret
        secret_enc = secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign

if __name__ == '__main__':
    dingtalk = DingtalkResponse(1, 1)
    dingtalk.send("test message")