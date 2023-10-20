import base64
import hashlib
import hmac
import time
import urllib
import requests
import json
from config.config import *
from utils.logger import *


def message_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            # 在这里可以添加你的错误处理逻辑，例如打印错误信息或记录日志
            log.error(f"dingding error occurred: {e}")

    return wrapper

@message_error_handler
def send_dingtalk_message_by_key_word(project_url):
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


def get_sign(timestamp):

    '''
    计算签名
    :param timestamp: 时间戳
    :return: 签名
    '''

    secret = dingding_secret
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return sign

@message_error_handler
def send_dingtalk_message_by_sign(message_text):
    """
    使用签名方式发送消息通知到钉钉群

    Args:
        webhook_url (str): 钉钉群聊机器人的Webhook地址
        secret (str): 机器人的安全设置中的密钥
        message_text (str): 消息文本内容

    Returns:
        bool: 消息是否发送成功
    """
    timestamp = str(round(time.time() * 1000))
    sign = get_sign(timestamp)
    webhookurl = f"{dingding_bot_webhook}&timestamp={timestamp}&sign={sign}"
    # 构建请求头
    headers = {
        "Content-Type": "application/json",
    }

    # 构建请求体
    message = {
        "msgtype": "text",
        "text": {
            "content": message_text
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
    if response.status_code == 200:
        print("消息已发送成功。")
        return True
    else:
        print("消息发送失败，HTTP状态码：", response.status_code)
        return False

if __name__ == "__main__":
    send_dingtalk_message_by_sign("hi")
