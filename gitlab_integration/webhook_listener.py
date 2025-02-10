import json
import threading

from flask import request, jsonify

from app.gitlab_utils import get_merge_request_id, get_commit_change_file, get_merge_request_changes
from gitlab_integration.gitlab_fetcher import GitlabMergeRequestFetcher
from reply_module.reply import Reply
from review_engine.review_engine import ReviewEngine
from service.chat_review import review_code_for_mr, review_code_for_add_commit
from utils.dingding import send_dingtalk_message_by_sign
from utils.logger import log


class WebhookListener:
    def __init__(self):
        pass

    def handle_webhook(self):
        """
        处理webhook的请求
        :return:
        """
        gitlab_payload = request.data.decode('utf-8')
        gitlab_payload = json.loads(gitlab_payload)
        log.info(f"🌈 ：{gitlab_payload}")
        event_type = gitlab_payload.get('object_kind')
        return self.call_handle(gitlab_payload, event_type)

    def call_handle(self, gitlab_payload, event_type):
        reply = Reply(gitlab_payload.get('project')['id'], gitlab_payload.get("object_attributes")["iid"])
        if event_type == 'merge_request':
            return self.handle_merge_request(gitlab_payload, reply)
        elif event_type == 'push':
            return self.handle_push(gitlab_payload, reply)
        else:
            return self.handle_other(gitlab_payload, reply)

    def handle_merge_request(self, gitlab_payload, reply):
        """
        处理合并请求事件
        """
        if gitlab_payload.get("object_attributes").get("state") == "opened" and gitlab_payload.get("object_attributes").get("merge_status") == "preparing":
            log.info("首次merge_request ", gitlab_payload)
            project_id = gitlab_payload.get('project')['id']
            merge_request_iid = gitlab_payload.get("object_attributes")["iid"]
            review_engine = ReviewEngine(reply)
            fetcher = GitlabMergeRequestFetcher(project_id, merge_request_iid)

            changes = fetcher.get_changes()
            info = fetcher.get_info()
            thread = threading.Thread(target=review_engine.handle_merge, args=(changes, info, gitlab_payload))
            thread.start()

            return jsonify({'status': 'success'}), 200
        return jsonify({'status': 'do not need check'}), 200

    def handle_push(self, gitlab_payload, reply):
        """
        处理推送事件
        """
        project_id = gitlab_payload.get('project')['id']
        merge_request_id = get_merge_request_id(gitlab_payload.get('ref').split("/")[-1], gitlab_payload.get("project_id"))


        if not merge_request_id:
            send_dingtalk_message_by_sign(
                f"Project_Name:{gitlab_payload['project']['name']}\n备注：分支 {gitlab_payload.get('ref')} 没有处于open状态的 Merge Request 不进行 Code Review。")
            return jsonify({'status': f'非存在MR分支,{gitlab_payload}'}), 200

        changed_files = get_commit_change_file(gitlab_payload)

        thread = threading.Thread(target=review_code_for_add_commit,
                                  args=(project_id, merge_request_id, changed_files, gitlab_payload))
        thread.start()

        return jsonify({'status': 'success'}), 200

    def handle_other(self, gitlab_payload, reply):
        """
        处理其他事件
        """
        event_type = gitlab_payload.get('object_kind')
        log.info(f"Unhandled event type: {event_type}")
        return jsonify({'status': 'unhandled event type'}), 200

webhook_listener = WebhookListener()