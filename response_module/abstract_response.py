from abc import ABC, abstractmethod

class AbstractResponse(ABC):
    @abstractmethod
    def __init__(self, config):
        self.config = config


class AbstractResponseMessage(AbstractResponse):
    @abstractmethod
    def __init__(self, config):
        super().__init__(config)

    @abstractmethod
    def send(self, message):
        pass


class AbstractResponseOther(AbstractResponse):
    @abstractmethod
    def __init__(self, config):
        super().__init__(config)

    @abstractmethod
    def set_state(self, *args, **kwargs):
        pass

    @abstractmethod
    def send(self, *args, **kwargs):
        pass