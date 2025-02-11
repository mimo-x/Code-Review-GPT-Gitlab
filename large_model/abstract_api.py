from abc import ABC, abstractmethod

class AbstractApi(ABC):

    @abstractmethod
    def set_config(self, api_config: dict) -> bool:
        """设置模型配置"""
        pass

    @abstractmethod
    def generate_text(self, messages: str) -> bool:
        """根据提示生成文本"""
        pass

    @abstractmethod
    def get_respond_content(self) -> str:
        """获取模型返回内容"""
        pass

    @abstractmethod
    def get_respond_tokens(self) -> int:
        """获取模型返回token数"""
        pass