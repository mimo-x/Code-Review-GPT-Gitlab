import os
from math import trunc

from litellm import completion
from config.config import api_config as out_config
from llm_api.llm_api_interface import LLMApiInterface
from llm_api.load_api import create_llm_api_instance
from unionllm import unionchat


class LLMApiDefault(LLMApiInterface):

    def __init__(self):
        self.params = {}
        self.response = None

    def set_config(self, api_config: dict) -> bool:
        if api_config is None:
            raise ValueError("api_config is None")
        for key in api_config:
            self.params[key] = api_config[key]
            # 如果为大写，则写入环境变量
            if key.isupper():
                os.environ[key] = api_config[key]
        return True

    def generate_text(self, messages: list) -> bool:
        try:
            self.response = unionchat(messages=messages, **self.params)
        except Exception as e:
            raise e
        return True

    def get_respond_content(self) -> str:
        return self.response['choices'][0]['message']['content']

    def get_respond_tokens(self) -> int:
        return trunc(int(self.response['usage']['total_tokens']))


# 示例使用
if __name__ == "__main__":
    api = create_llm_api_instance()
    api.set_config(out_config)
    api.generate_text([
        {"role": "system",
         "content": "你是一位作家"
         },
        {"role": "user",
         "content": "请写一首抒情的诗",
         }
    ])
    print(api.get_respond_content())
    print(api.get_respond_tokens())
