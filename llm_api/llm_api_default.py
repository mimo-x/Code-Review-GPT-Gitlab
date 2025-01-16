import os
from math import trunc

from litellm import completion
from config.config import api_config as out_config
from llm_api.llm_api_interface import LLMApiInterface
from llm_api.load_api import create_llm_api_instance


class LLMApiDefault(LLMApiInterface):

    def __init__(self):
        self.model_name = None
        self.response = None

    def set_config(self, api_config: dict) -> bool:
        if api_config is None:
            raise ValueError("api_config is None")
        for key in api_config:
            if key == "MODEL_NAME":
                self.model_name = api_config[key]
                continue
            os.environ[key] = api_config[key]
        return True

    def generate_text(self, messages: list) -> bool:

        self.response = completion(
            model=self.model_name,
            messages=messages,
        )
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

