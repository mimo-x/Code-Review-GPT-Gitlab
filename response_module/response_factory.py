from response_module.abstract_response import AbstractResponse, AbstractResponseMessage
from response_module.response_target.msg_response.dingtalk_response import DingtalkResponse
from response_module.response_target.msg_response.gitlab_response import GitlabResponse


class ResponseFactory:
    _registry_msg = {}
    _registry_other = {}

    @classmethod
    def register_target(cls, target, target_class):
        # 检测是否实现了AbstractResponseMessage接口
        """
        Registers a response target with its associated response class.
        
        Ensures that target_class is a subclass of AbstractResponse, raising a TypeError if not.
        If target_class does not implement AbstractResponseMessage, it is also added to an alternate registry.
        In all cases, target_class is registered as a message target.
        
        Args:
            target: The identifier for the response target.
            target_class: A class expected to implement AbstractResponse.
            
        Raises:
            TypeError: If target_class is not a subclass of AbstractResponse.
        """
        if not issubclass(target_class, AbstractResponse):
            raise TypeError(f'{target_class} does not implement AbstractResponse')
        if not issubclass(target_class, AbstractResponseMessage):
            cls._registry_other[target] = target_class
        cls._registry_msg[target] = target_class

    @classmethod
    def get_message_instance(cls, target, config):
        """
        Retrieves a message response instance for a given target.
        
        Checks if the target is registered in the message registry and returns a new instance
        of the associated message response class initialized with the provided configuration.
        Returns None if the target is not found.
        
        Args:
            target: The key identifying the registered message response.
            config: The configuration used to instantiate the message response.
        """
        if target not in cls._registry_msg:
            return None
        return cls._registry_msg[target](config)

    @classmethod
    def get_other_instance(cls, target, config):
        """
        Retrieve a non-message response instance for the given target.
        
        If the target is not registered in the non-message responses registry, returns None.
        
        Args:
            target: Identifier for the response class to instantiate.
            config: Configuration used to initialize the response instance.
        
        Returns:
            The instantiated non-message response object if found; otherwise, None.
        """
        if target not in cls._registry_other:
            return None
        return cls._registry_other[target](config)

    @classmethod
    def get_all_message_instance(cls, config):
        """
        Return instances of all registered message response classes.
        
        Args:
            config: Configuration data used to initialize each message response instance.
        
        Returns:
            List of instances for each registered message response.
        """
        return [target_class(config) for target_class in cls._registry_msg.values()]

    @classmethod
    def get_all_other_instance(cls, *args, **kwargs):
        """
        Instantiates all registered other response classes.
        
        For each class stored in the other response registry, a new instance is created by
        calling its constructor with the provided positional and keyword arguments. Returns
        a list of these instances.
        """
        return [target_class(*args, **kwargs) for target_class in cls._registry_other.values()]

    @classmethod
    def get_all_message_targets(cls):
        """
        Returns a list of all registered message targets.
        
        This method retrieves the keys from the internal message registry, which represent
        the targets for the registered message response classes.
        """
        return list(cls._registry_msg.keys())

    @classmethod
    def get_all_other_targets(cls):
        """
        Returns a list of all registered non-message response targets.
        
        This method retrieves the keys from the registry of other response classes,
        providing a collection of all targets not associated with message responses.
        """
        return list(cls._registry_other.keys())


ResponseFactory.register_target('gitlab', GitlabResponse)
ResponseFactory.register_target('dingtalk', DingtalkResponse)
# ResponseFactory.register_target('temp', TemplateResponse)
if __name__ == '__main__':
    print(ResponseFactory.get_all_message_targets())
