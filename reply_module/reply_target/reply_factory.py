from reply_module.reply_target.dingtalk_reply import DingtalkReply
from reply_module.reply_target.gitlab_reply import GitlabReply

class ReplyFactory:
    _registry = {}

    @classmethod
    def register_target(cls, target, target_class):
        cls._registry[target] = target_class

    @classmethod
    def get_reply_instance(cls, target, config):
        if target not in cls._registry:
            raise ValueError(f"Unknown target: {target}")
        return cls._registry[target](config)

    @classmethod
    def get_all_reply_instance(cls, config):
        return [target_class(config) for target_class in cls._registry.values()]

    @classmethod
    def get_all_targets(cls):
        return list(cls._registry.keys())



ReplyFactory.register_target('gitlab', GitlabReply)
ReplyFactory.register_target('dingtalk', DingtalkReply)