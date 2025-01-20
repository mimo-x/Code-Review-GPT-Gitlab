# Config.py 配置指南
## 大模型配置
- `llm_api_impl`：大模型API接口实现
  - 默认`llm_api_default`使用`UnionLLM`进行多模型支持，`UnionLLM`兼容`LiteLLM`，
  支持模型和参数配置方式参见：[UnionLLM仓库](https://github.com/EvalsOne/UnionLLM/)和[LiteLLM文档](https://docs.litellm.ai/docs)。
  - 主流模型只需要修改`api_config`即可接入，无需修改该参数
  - 实现默认不支持的大模型接入，可实现`llm_api_interface`接口，并将类名传入该参数。
- `api_config`: 大模型API配置
  - 具体配置参见[UnionLLM仓库](https://github.com/EvalsOne/UnionLLM/)和[LiteLLM文档](https://docs.litellm.ai/docs)
  - `MODEL_NAME` 传入模型名称
  - `PROVIDER` 传入模型提供商
  - 该配置会自动传给`llm_api_impl`的`set_config`方法，用于初始化大模型API。 


## Gitlab配置
- `gitlab_server_url`: Gitlab服务器地址
- `gitlab_private_token`: Gitlab私有令牌
- `maximum_files`: Gitlab Merge Request最大文件数

## 消息通知配置
- `dingtalk_webhook`: 钉钉机器人Webhook
- `dingtalk_secret`: 钉钉机器人密钥