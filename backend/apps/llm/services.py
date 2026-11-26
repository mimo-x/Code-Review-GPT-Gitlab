"""
模型调用客户端：只负责把提示词发给配置好的模型并取回文本。
"""
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 页面上的提供商对应的 LiteLLM 路由前缀；unionllm/litellm 由模型名自带路由
_ROUTE_PREFIX = {'openai': 'openai', 'deepseek': 'deepseek', 'gemini': 'gemini'}


class LLMError(Exception):
    """所有模型客户端都调用失败。"""


@dataclass(frozen=True)
class Completion:
    text: str
    client: str


class LLMService:
    def __init__(self, llm_config, request_id=None):
        self.request_id = request_id
        self.provider = llm_config.provider
        self.model = llm_config.model
        self.api_key = llm_config.api_key
        self.api_base = llm_config.api_base
        # 避免 MR 文件较多时无限等待
        self.timeout = getattr(llm_config, 'timeout', None) or int(
            os.environ.get('LLM_API_TIMEOUT', '600')
        )
        if not self.api_key:
            logger.warning(f"[{self.request_id}] LLM 配置缺少 API Key，后续请求可能失败")

    @property
    def _call_params(self):
        """凭据只随本次请求传递，不写入进程环境，避免并发串用或泄漏给子进程。"""
        params = {
            'model': _routed_model(self.provider, self.model, self.api_base),
            'timeout': self.timeout,
        }
        if self.api_key:
            params['api_key'] = self.api_key
        if self.api_base:
            params['api_base'] = self.api_base
        return params

    def complete(self, prompt):
        """依次尝试 unionllm 和 litellm，全部失败时抛出 LLMError。"""
        for name, call in (('unionllm', self._call_unionllm), ('litellm', self._call_litellm)):
            try:
                text = call(prompt)
            except Exception as exc:
                logger.warning(f"[{self.request_id}] {name} 调用失败: {exc}")
                continue
            if text and text.strip():
                logger.info(f"[{self.request_id}] {name} 调用成功, 响应长度: {len(text)}")
                return Completion(text=text, client=name)
            logger.warning(f"[{self.request_id}] {name} 返回空响应")
        raise LLMError("unionllm 和 litellm 均调用失败")

    def _call_unionllm(self, prompt):
        from unionllm import unionchat

        response = unionchat(messages=[{"role": "user", "content": prompt}], **self._call_params)
        return response.get('choices', [{}])[0].get('message', {}).get('content', '')

    def _call_litellm(self, prompt):
        import litellm

        response = litellm.completion(
            messages=[{"role": "user", "content": prompt}], **self._call_params
        )
        return response.choices[0].message.content


def _routed_model(provider, model, api_base):
    """让页面上选的提供商配裸模型名也能工作，同时兼容已带前缀的写法。"""
    prefix = _ROUTE_PREFIX.get((provider or '').lower())
    if not prefix or model.startswith(f'{prefix}/'):
        return model
    # 模型名里的其他前缀（gemini/xxx 等）只当作模型名的一部分：
    # 配置的 Key 属于所选提供商，不能被发到别家的接口
    return f'{prefix}/{model}'
