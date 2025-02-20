from response_module.abstract_response import AbstractResponse, AbstractResponseMessage
from response_module.response_target.msg_response.dingtalk_response import DingtalkResponse
from response_module.response_target.msg_response.gitlab_response import GitlabResponse


class ResponseFactory:
    _registry_msg = {}
    _registry_other = {}

    @classmethod
    def register_target(cls, target, target_class):
        # 检测是否实现了AbstractResponseMessage接口
        if not issubclass(target_class, AbstractResponse):
            raise TypeError(f'{target_class} does not implement AbstractResponse')
        if not issubclass(target_class, AbstractResponseMessage):
            cls._registry_other[target] = target_class
        cls._registry_msg[target] = target_class

    @classmethod
    def get_message_instance(cls, target, config):
        if target not in cls._registry_msg:
            return None
        return cls._registry_msg[target](config)

    @classmethod
    def get_other_instance(cls, target, config):
        if target not in cls._registry_other:
            return None
        return cls._registry_other[target](config)

    @classmethod
    def get_all_message_instance(cls, config):
        return [target_class(config) for target_class in cls._registry_msg.values()]

    @classmethod
    def get_all_other_instance(cls, *args, **kwargs):
        return [target_class(*args, **kwargs) for target_class in cls._registry_other.values()]

    @classmethod
    def get_all_message_targets(cls):
        return list(cls._registry_msg.keys())

    @classmethod
    def get_all_other_targets(cls):
        return list(cls._registry_other.keys())


ResponseFactory.register_target('gitlab', GitlabResponse)
ResponseFactory.register_target('dingtalk', DingtalkResponse)
# ResponseFactory.register_target('temp', TemplateResponse)
if __name__ == '__main__':
    print(ResponseFactory.get_all_message_targets())
