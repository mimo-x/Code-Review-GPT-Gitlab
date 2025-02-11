# GPT 相关配置
# model list
model_quester_anster = "text-davinci-003"
model_gpt_35_turbo = "gpt-3.5-turbo"
model_gpt_4o = "gpt-4o"
model_programming_translate = "code-davinci-002"

# api 接口封装类
llm_api_impl = "large_model.api.default_api.DefaultApi"

# api 配置方式参考 docs/llm_api.md
# 默认使用认UnionLLM，参考：https://github.com/EvalsOne/UnionLLM/tree/main/docs
# UnionLLM兼容LiteLLM，参考LiteLLM文档：https://docs.litellm.ai/docs
api_config = {
    "api_key": "your openai key",
    "api_base": "https://api.openai.com/v1",
    "model": model_gpt_4o,
    "provider": "openai",
}

# 2. 提示词
gpt_message = """
         你是一位资深编程专家，gitlab的分支代码变更将以git diff 字符串的形式提供，请你帮忙review本段代码。然后你review内容的返回内容必须严格遵守下面的格式，包括标题内容。模板中的变量内容解释：变量5是代码中的优点儿 变量1是给review打分，分数区间为0~100分。 变量2 是code review发现的问题点。  变量3是具体的修改建议。变量4是你给出的修改后的代码。 必须要求：1. 以精炼的语言、严厉的语气指出存在的问题。2. 你的反馈内容必须使用严谨的markdown格式 3. 不要携带变量内容解释信息。4. 有清晰的标题结构。有清晰的标题结构。有清晰的标题结构。
返回格式严格如下：



### 😀代码评分：{变量1}

#### ✅代码优点：
{变量5}

#### 🤔问题点：
{变量2}

#### 🎯修改建议：
{变量3}

#### 💻修改后的代码：
```python
{变量4}

         """

# -------------Gitlab info------------------
# Gitlab url
gitlab_server_url = "https://gitlab.com"

# Gitlab private token
gitlab_private_token = "gitlab private token"

# Gitlab modifies the maximum number of files
maximum_files = 50


# ------------- Message notification --------------------
# dingding notification （un necessary）
dingding_bot_webhook = "https://oapi.dingtalk.com/robot/send?access_token=*****************************************"
dingding_secret = "S********************************950f"