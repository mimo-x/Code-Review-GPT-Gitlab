import importlib
import warnings

from config.config import llm_api_impl, api_config


class LLMGenerator:

    @classmethod
    def new_model(cls, config = api_config):
        api = cls.create_model_instance()
        api.set_config(config)
        return api

    @classmethod
    def get_llm_api_class(cls):
        module_name, class_name = llm_api_impl.rsplit('.', 1)
        module = importlib.import_module(module_name)
        llm_class = getattr(module, class_name)
        return llm_class

    @classmethod
    def create_model_instance(cls):
        """
        使用工厂函数获取类实例
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            llm_class = cls.get_llm_api_class()
            return llm_class()
