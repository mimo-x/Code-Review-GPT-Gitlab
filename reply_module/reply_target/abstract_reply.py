from abc import ABC, abstractmethod

class AbstractReply(ABC):
    @abstractmethod
    def __init__(self, project_id, merge_request_id):
        self.project_id = project_id
        self.merge_request_id = merge_request_id

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
