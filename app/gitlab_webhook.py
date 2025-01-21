import json
import threading
from os import abort
from flask import Blueprint, request, jsonify
# from config.config import WEBHOOK_VERIFY_TOKEN
from service.chat_review import review_code, review_code_for_mr, review_code_for_add_commit
from utils.logger import log
from app.gitlab_utils import get_commit_list, get_merge_request_id, get_commit_change_file
from utils.dingding import send_dingtalk_message_by_sign

git = Blueprint('git', __name__)


@git.route('/api')
def question():
    return 'hello world'


@git.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # 获取gitlab的webhook的token
        webhook_token = request.headers.get('X-Gitlab-Token')

        # gitlab的webhook的token验证
        # if webhook_token == WEBHOOK_VERIFY_TOKEN:
        return jsonify({'status': 'success'}), 200
        #else:
        #    return jsonify({'status': 'bad token'}), 401

    elif request.method == 'POST':
        """
        webhook的主要逻辑,获取gitlab的推送信息
        """
        # 获取gitlab的推送信息
        gitlab_payload = request.data.decode('utf-8')
        # 将gitlab的推送信息转换为字典
        gitlab_payload = json.loads(gitlab_payload)
        log.info(f"🌈 ：{gitlab_payload}")
        # 获取项目的类型
        event_type = gitlab_payload.get('object_kind')

        # 首次发起mr时候触发
        if event_type == 'merge_request' and gitlab_payload.get("object_attributes").get(
            "state") == "opened" and gitlab_payload.get("object_attributes").get("merge_status") == "preparing":
            # 验证通过，获取commit的信息
            log.info("首次merge_request ", gitlab_payload)
            # 获取项目id
            project_id = gitlab_payload.get('project')['id']
            # 获取merge request ID
            merge_request_id = gitlab_payload.get("object_attributes")["iid"]

            thread = threading.Thread(target=review_code_for_mr, args=(project_id, merge_request_id, gitlab_payload))
            thread.start()

            return jsonify({'status': 'success'}), 200
        elif event_type == 'push':
            # 获取merge request ID
            merge_request_id = get_merge_request_id(gitlab_payload.get('ref').split("/")[-1], gitlab_payload.get("project_id"))
            # 获取项目id
            project_id = gitlab_payload.get('project')['id']
            if not merge_request_id:
                send_dingtalk_message_by_sign(
                    f"Project_Name:{gitlab_payload['project']['name']}\n备注：分支 {gitlab_payload.get('ref')} 没有处于open状态的 Merge Request 不进行 Code Review。")
                return jsonify({'status': f'非存在MR分支,{gitlab_payload}'}), 200

            changed_files = get_commit_change_file(gitlab_payload)

            thread = threading.Thread(target=review_code_for_add_commit,
                                      args=(project_id, merge_request_id, changed_files, gitlab_payload))
            thread.start()

            return jsonify({'status': 'success'}), 200

        else:
            log.error("不是merge")
            return jsonify({'status': '操作不为push'}), 200

        return jsonify({'status': f'未匹配到规则,{gitlab_payload}'}), 200

    else:
        abort(400)
