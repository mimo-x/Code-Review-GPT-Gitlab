import gradio as gr
from types import SimpleNamespace
from utils.logger import *
import json
import requests
import hmac
import base64
import urllib.parse
import time
import hashlib
import os
import textwrap


def test_llm_connection(api_key, api_base, model, provider):
    api_config = dict(api_key=api_key, api_base=api_base, model=model, provider=provider)
    api_check = check_api_config(api_config)
    if api_check["passed"]:
        return "✅ LLM 连接成功!"
    else:
        return "❌ LLM 连接失败"

def test_gitlab_connection(gitlab_server_url, gitlab_private_token):
    gitlab_config = dict(gitlab_server_url=gitlab_server_url, gitlab_private_token=gitlab_private_token)
    gitlab_config = SimpleNamespace(**gitlab_config)
    gitlab_check = check_gitlab_config(gitlab_config)
    if gitlab_check["passed"]:
        return "✅ Gitlab 连接成功!"
    else:
        return "❌ Gitlab 连接失败"

def test_dingding(dingding_bot_webhook, dingding_secret):
    dingding_config = dict(dingding_bot_webhook=dingding_bot_webhook, dingding_secret=dingding_secret)
    dingding_config = SimpleNamespace(**dingding_config)
    dingding_checked = check_dingding_config(dingding_config)
    if dingding_checked:
        return "✅ 钉钉机器人连接成功!"
    else:
        return "❌ 钉钉机器人连接失败"

def check_dingding_config(dingding_config):
    result = {'passed': True, 'errors': []}

    # get sign
    timestamp = str(round(time.time() * 1000))
    secret = dingding_config.dingding_secret
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))


    webhookurl = f"{dingding_config.dingding_bot_webhook}&timestamp={timestamp}&sign={sign}"
    # 构建请求头
    headers = {
        "Content-Type": "application/json",
    }

    # 构建请求体
    message_text = "连通性测试：测试消息，请勿回复。"
    message = {
        "msgtype": "markdown",
        "markdown": {
            "title": "Gitlab 通知",
            "text": message_text
        },
        "timestamp": timestamp,
        "sign": sign
    }

    # 发送HTTP POST请求
    response = requests.post(
        webhookurl,
        headers=headers,
        data=json.dumps(message)
    )

    # 检查响应
    if response.status_code == 200 and response.json()["errcode"] == 0:
        return True
    else:
        return False

def check_api_config(config) -> dict:
    result = {'passed': True, 'errors': []}

    try:
        from large_model.llm_generator import LLMGenerator

        api = LLMGenerator.new_model(config=config)
        api.generate_text([
            {
                "role": "system",
                "content": "你是一个有用的助手"
            },
            {
                "role": "user",
                "content": "请输出ok两个小写字母，不要输出其他任何内容",
            }
        ])
        res_str = api.get_respond_content()

        if not res_str or res_str == "":
            error_msg = "Model interface check failed: Please check if the model call related configuration is correct , response is empty"
            result['errors'].append(error_msg)
            result['passed'] = False

        elif "ok" not in res_str:
            warning_msg = f"Model interface check failed: The model did not return the expected result, but may still be available, response: {res_str}"
            result['errors'].append(warning_msg)
            result['passed'] = False

    except Exception as e:
        result['errors'].append(str(e))
        result['passed'] = False

    return result

def check_gitlab_config(config) -> dict:
    result = {'passed': True, 'errors': []}

    try:
        response = requests.get(config.gitlab_server_url)
        if response.status_code != 200:
            error_msg = f"Gitlab server URL {config.gitlab_server_url} is not available"
            result['errors'].append(error_msg)
            result['passed'] = False

        response = requests.get(f"{config.gitlab_server_url}/api/v4/projects",
                                headers={"PRIVATE-TOKEN": config.gitlab_private_token})
        if response.status_code != 200:
            error_msg = "Gitlab private token is invalid"
            result['errors'].append(error_msg)
            result['passed'] = False

    except Exception as e:
        result['errors'].append(str(e))
        result['passed'] = False

    return result

def show_config():
    if os.path.exists("../../config/config.py"):
        from config import config
        config_value = f'''\
                # api 接口封装类
                llm_api_impl = "{config.llm_api_impl}"
                
                api_config = {{
                    "api_key": "{config.api_config["api_key"]}",
                    "api_base": "{config.api_config["api_base"]}",
                    "model": "{config.api_config["model"]}",
                    "provider": "{config.api_config["provider"]}",
                }}
                
                # ------------------Gitlab info--------------------------
                GITLAB_SERVER_URL = "{config.gitlab_server_url}"
                GITLAB_PRIVATE_TOKEN = "{config.gitlab_private_token}"
                MAX_FILES = 50
                
                # ------------- Message notification --------------------
                DINGDING_BOT_WEBHOOK = "{config.dingding_bot_webhook}"
                DINGDING_SECRET = "{config.dingding_secret}"
        '''
        return textwrap.dedent(config_value)

def show_current_config(llm_api, api_key, api_base, model, provider,
                gitlab_url, gitlab_token, max_files,
                dingding_webhook, dingding_secret):
    config = f'''\
            # api 接口封装类
            llm_api_impl = "{llm_api}"
            
            api_config = {{
                "api_key": "{api_key}",
                "api_base": "{api_base}",
                "model": '{model}',
                "provider": "{provider}",
            }}
            
            # ------------------Gitlab info--------------------------
            GITLAB_SERVER_URL = "{gitlab_url}"
            GITLAB_PRIVATE_TOKEN = "{gitlab_token}"
            MAX_FILES = {max_files}
            
            # ------------- Message notification --------------------
            DINGDING_BOT_WEBHOOK = "{dingding_webhook}"
            DINGDING_SECRET = "{dingding_secret}"
    '''
    return textwrap.dedent(config)

def save_config(llm_api, api_key, api_base, model, provider,
                gitlab_url, gitlab_token, max_files,
                dingding_webhook, dingding_secret):
    config = f'''\
            # api 接口封装类
            llm_api_impl = "{llm_api}"
            
            api_config = {{
                "api_key": "{api_key}",
                "api_base": "{api_base}",
                "model": '{model}',
                "provider": "{provider}",
            }}
            
            # ------------------Gitlab info--------------------------
            GITLAB_SERVER_URL = "{gitlab_url}"
            GITLAB_PRIVATE_TOKEN = "{gitlab_token}"
            MAX_FILES = {max_files}
            
            # ------------- Message notification --------------------
            DINGDING_BOT_WEBHOOK = "{dingding_webhook}"
            DINGDING_SECRET = "{dingding_secret}"
            '''
    config = textwrap.dedent(config)

    prompt_msg = '''\
    # Prompt
    GPT_MESSAGE = """
             你是一位资深编程专家，gitlab的分支代码变更将以git diff 字符串的形式提供，请你帮忙review本段代码。然后你review内容的返回内容必须严格遵守下面的格式，包括标题内容。模板中的变量内容解释：
             变量5为: 代码中的优点。变量1:给review打分，分数区间为0~100分。变量2：code review发现的问题点。变量3：具体的修改建议。变量4：是你给出的修改后的代码。 
             必须要求：1. 以精炼的语言、严厉的语气指出存在的问题。2. 你的反馈内容必须使用严谨的markdown格式 3. 不要携带变量内容解释信息。4. 有清晰的标题结构。有清晰的标题结构。有清晰的标题结构。
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
    ```
             """
    '''

    prompt_msg = textwrap.dedent(prompt_msg)

    custom_file_config = '''\
    # ------------- code review settings --------------------
    # expect file types
    EXCLUDE_FILE_TYPES = ['.py', '.java', '.class', '.vue', ".go",".c",".cpp"]
    
    # ignore file types
    IGNORE_FILE_TYPES = ["mod.go"]
    '''
    custom_file_config = textwrap.dedent(custom_file_config)

    try:
        with open("../../config/config.py", "w", encoding='utf-8') as f:
            f.write(config)
            f.write("\n")
            f.write(prompt_msg)
            f.write("\n")
            f.write(custom_file_config)
        return "✅ 配置保存成功!"
    except Exception as e:
        return f"❌ 配置保存失败: {str(e)}"

def translate_file(file, service, from_lang, to_lang, is_first_page):
    # 这里添加翻译逻辑
    return "文件翻译结果将显示在这里"

# 定义主题色
theme = gr.themes.Base()

with gr.Blocks(title="配置管理", theme=theme) as demo:
    gr.Markdown("# 系统配置管理")
    
    with gr.Row():
        # 左侧配置区
        with gr.Column(scale=3):
            with gr.Tabs():
                # LLM配置标签页
                with gr.Tab("LLM"):
                    with gr.Group():
                        llm_api = gr.Textbox(label="LLM API 实现类", value="large_model.api.default_api.DefaultApi")
                        with gr.Row():
                            api_key = gr.Textbox(label="API Key", type="password", scale=2)
                            test_llm_btn = gr.Button("测试连接", variant="primary", size="sm", scale=1)
                        api_base = gr.Textbox(label="API Base URL")
                        with gr.Row():
                            model = gr.Textbox(label="模型名称", scale=2)
                            provider = gr.Dropdown(label="Provider", choices=["openai", "deepseek", "ollama"], scale=1)
                        llm_output = gr.Textbox(label="测试结果", lines=1)
                
                # Gitlab配置标签页
                with gr.Tab("Gitlab"):
                    with gr.Group():
                        with gr.Row():
                            gitlab_url = gr.Textbox(label="Gitlab URL", scale=2)
                            test_gitlab_btn = gr.Button("测试连接", variant="primary", size="sm", scale=1)
                        gitlab_token = gr.Textbox(label="Private Token", type="password")
                        max_files = gr.Number(label="最大文件数", value=50)
                        gitlab_output = gr.Textbox(label="测试结果", lines=1)
                
                # 钉钉配置标签页
                with gr.Tab("钉钉"):
                    with gr.Group():
                        with gr.Row():
                            dingding_webhook = gr.Textbox(label="Webhook URL", scale=2)
                            test_dingding_btn = gr.Button("测试连接", variant="primary", size="sm", scale=1)
                        dingding_secret = gr.Textbox(label="Secret", type="password")
                        dingding_output = gr.Textbox(label="测试结果", lines=1)
            
            # 保存按钮
            with gr.Row():
                save_btn = gr.Button("保存所有配置", variant="primary", size="lg")
                save_output = gr.Textbox(label="保存结果", lines=1)
        
        # 右侧预览区
        with gr.Column(scale=2):
            gr.Markdown("### 配置预览")
            preview = gr.Code(
                label="当前配置",
                language="python",
                lines=25,
                value=textwrap.dedent("""\
                    # api 接口封装类
                    llm_api_impl = "large_model.api.default_api.DefaultApi"
                    
                    api_config = {
                        "api_key": "your-api-key",
                        "api_base": "your-api-base",
                        "model": "your-model",
                        "provider": "openai",
                    }
                    
                    # ------------------Gitlab info--------------------------
                    GITLAB_SERVER_URL = "your-gitlab-url"
                    GITLAB_PRIVATE_TOKEN = "your-token"
                    MAX_FILES = 50
                    
                    # ------------- Message notification --------------------
                    DINGDING_BOT_WEBHOOK = "your-webhook"
                    DINGDING_SECRET = "your-secret"
                """))
            # 添加一个按钮，用于显示当前配置
            show_config_btn = gr.Button("显示当前配置", variant="primary", size="sm")
            # show_config_output = gr.Textbox(label="当前配置", lines=25)

    # 事件绑定
    test_llm_btn.click(
        test_llm_connection,
        inputs=[api_key, api_base, model, provider],
        outputs=llm_output
    )
    
    test_gitlab_btn.click(
        test_gitlab_connection,
        inputs=[gitlab_url, gitlab_token],
        outputs=gitlab_output
    )
    
    test_dingding_btn.click(
        test_dingding,
        inputs=[dingding_webhook, dingding_secret],
        outputs=dingding_output
    )

    # show_config_btn.click(
    #     show_config,
    #     inputs=[],
    #     outputs=preview
    # )
    show_config_btn.click(
        show_current_config,
        inputs=[
            llm_api, api_key, api_base, model, provider,
            gitlab_url, gitlab_token, max_files,
            dingding_webhook, dingding_secret
        ],
        outputs=preview
    )

    
    save_btn.click(
        save_config,
        inputs=[
            llm_api, api_key, api_base, model, provider,
            gitlab_url, gitlab_token, max_files,
            dingding_webhook, dingding_secret
        ],
        outputs=save_output
    )


if __name__ == "__main__":
    demo.launch()
    # 动态加载渲染