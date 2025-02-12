# Config.py 配置指南
## 大模型配置
- `llm_api_impl`：大模型API接口实现
  - 默认`llm_api_default`使用`UnionLLM`进行多模型支持，`UnionLLM`兼容`LiteLLM`，
  支持模型和参数配置方式参见：[UnionLLM仓库](https://github.com/EvalsOne/UnionLLM/)和[LiteLLM文档](https://docs.litellm.ai/docs)。
  - 主流模型只需要修改`api_config`即可接入，无需修改该参数
  - 实现默认不支持的大模型接入，可实现`AbstractApi`接口，并将类名传入该参数。
- `api_config`: 大模型API配置
  
  > 除必选参数外，其他参数根据模型需求填写，具体模型对应的参数参见[LiteLLM文档](https://docs.litellm.ai/docs)以及[UnionLLM仓库-DOC目录](https://github.com/EvalsOne/UnionLLM/tree/main/docs)中相应模型部分。具体而言：
  > 
  > 国外模型请查找[LiteLLM文档](https://docs.litellm.ai/docs)，并将`LiteLLM`示例中`litellm.completion`内的参数填写到`api_config`中，若示例需要通过环境变量鉴权，也请填写到`api_config`中。
  >   
  > 国内模型请查找[UnionLLM仓库-DOC目录](https://github.com/EvalsOne/UnionLLM/tree/main/docs)，并将`UnionLLM`示例中`unionchat`内的参数填写到`api_config`中，若示例需要通过环境变量鉴权，也请填写到`api_config`中。
  - 必选参数
      - `model` 传入模型名称
      - `provider` 传入模型提供商
  - 常用可选参数
    - `api_base` 传入API地址
    - `api_key` 传入API密钥
  - 其他可选参数
    - `max_tokens` 设置生成文本的最大长度
    - `temperature` 控制生成文本的随机性
    - `top_p` 控制生成文本的多样性
    - `n` 设置生成的文本数量
    - `logprobs` 返回生成文本的对数概率
    - `stream` 是否以流式方式返回生成结果
    - `stop` 设置生成文本的停止标记
    - `presence_penalty` 控制生成文本中重复内容的惩罚
    - `frequency_penalty` 控制生成文本中频繁出现内容的惩罚
    - `best_of` 从多次生成中选择最佳结果
    - `logit_bias` 调整生成文本中某些词的概率
    - `api_url` 传入API地址
    - `api_version` 传入API版本
    - `extra_headers` 传入额外的HTTP头信息
    - 其他参数请参考上述文档
  - 该配置会自动传给`llm_api_impl`的`set_config`方法，用于初始化大模型API。 
### 示例

#### DeepSeek

```python
api_config = {
    "api_key": "your deepseek key",
    "model": 'deepseek-chat',
    "provider": "deepseek",
}
```

#### ChatGPT
```python
# 直接传入
api_config = {
    "api_key": "your openai key",
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-3.5-turbo",
    "provider": "openai",
}
# 通过环境变量传入
api_config = {
    "OPENAI_API_KEY": "your openai key",
    "OPENAI_API_BASE": "https://api.openai.com/v1",
    "model": "gpt-3.5-turbo",
    "provider": "openai",
}
```
#### Ollama
```python
api_config = {
    "api_base": "http://localhost:11434",
    "model": "llama3.2",
    "provider": "ollama",
}
```


## Gitlab配置
- `gitlab_server_url`: Gitlab服务器地址
- `gitlab_private_token`: Gitlab私有令牌
- `maximum_files`: Gitlab Merge Request最大文件数

## 消息通知配置
- `dingtalk_webhook`: 钉钉机器人Webhook
- `dingtalk_secret`: 钉钉机器人密钥