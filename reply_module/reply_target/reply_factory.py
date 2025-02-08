from reply_module.reply_target.dingtalk_reply import DingtalkReply
from reply_module.reply_target.gitlab_reply import GitlabReply


class ReplyFactory:
    @staticmethod
    def get_reply_instance(target, project_id, merge_request_id):
        if target == 'gitlab':
            return GitlabReply(project_id, merge_request_id)
        elif target == 'dingtalk':
            return DingtalkReply(project_id, merge_request_id)
        else:
            raise ValueError(f"Unknown target: {target}")