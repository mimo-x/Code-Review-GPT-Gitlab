from abc import ABC, abstractmethod

class AbstractReply(ABC):
    @abstractmethod
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def send(self, message):
        pass

    # # 发送失败调用
    # @abstractmethod
    # def send_failed(self, message):
    #     pass
    #
    # # 发送成功调用
    # @abstractmethod
    # def send_success(self, message):
    #     pass
