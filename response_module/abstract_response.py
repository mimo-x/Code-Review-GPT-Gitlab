from abc import ABC, abstractmethod

class AbstractResponse(ABC):
    @abstractmethod
    def __init__(self, config):
        """
        Initialize the response instance with a configuration.
        
        The provided configuration is stored for use by subclasses.
        """
        self.config = config


class AbstractResponseMessage(AbstractResponse):
    @abstractmethod
    def __init__(self, config):
        """
        Initialize the instance with the provided configuration.
        
        Delegates to the superclass constructor to set up the instance.
        """
        super().__init__(config)

    @abstractmethod
    def send(self, message):
        """
        Sends a message.
        
        Subclasses must override this method to deliver the provided message using the
        appropriate communication mechanism.
        
        Args:
            message: The content or payload of the message to be sent.
        """
        pass


class AbstractResponseOther(AbstractResponse):
    @abstractmethod
    def __init__(self, config):
        """
        Initialize the response instance with the specified configuration.
        
        This constructor passes the configuration to the parent initializer to establish
        the necessary settings for the response object.
        """
        super().__init__(config)

    @abstractmethod
    def set_state(self, *args, **kwargs):
        """
        Set the state of the response.
        
        Subclasses must override this method to update the internal state based on the
        provided positional and keyword arguments.
        """
        pass

    @abstractmethod
    def send(self, *args, **kwargs):
        """
        Sends a response using provided arguments.
        
        Subclasses must override this method to handle sending a response
        or triggering appropriate actions based on supplied positional and keyword
        arguments.
        """
        pass