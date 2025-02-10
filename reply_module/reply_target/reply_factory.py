from reply_module.reply_target.dingtalk_reply import DingtalkReply
from reply_module.reply_target.gitlab_reply import GitlabReply

class ReplyFactory:
    _registry = {}

    @classmethod
    def register_target(cls, target, target_class):
        cls._registry[target] = target_class

    @classmethod
    def get_reply_instance(cls, target, project_id, merge_request_id):
        if target not in cls._registry:
            raise ValueError(f"Unknown target: {target}")
        return cls._registry[target](project_id, merge_request_id)

    @classmethod
    def get_all_reply_instance(cls, project_id, merge_request_id):
        return [target_class(project_id, merge_request_id) for target_class in cls._registry.values()]

    @classmethod
    def get_all_targets(cls):
        return list(cls._registry.keys())



ReplyFactory.register_target('gitlab', GitlabReply)
ReplyFactory.register_target('dingtalk', DingtalkReply)