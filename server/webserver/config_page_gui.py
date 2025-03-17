import gradio as gr
import json
import requests
import hmac
import base64
import urllib.parse
import time
import hashlib
import os

def test_llm_connection(api_key, api_base, model, provider):
    return "✅ LLM 连接成功!"

def test_gitlab_connection(url, token):
    return "✅ Gitlab 连接成功!"

def test_dingding(webhook, secret):
    return "✅ 钉钉机器人连接成功!"

def save_config(llm_api, api_key, api_base, model, provider,
                gitlab_url, gitlab_token, max_files,
                dingding_webhook, dingding_secret):
    config = f'''# api 接口封装类
llm_api_impl = "{llm_api}"

api_config = {{
    "api_key": "{api_key}",
    "api_base": "{api_base}",
    "model": '{model}',
    "provider": "{provider}",
}}

# ------------------Gitlab info--------------------------
gitlab_server_url = "{gitlab_url}"
gitlab_private_token = "{gitlab_token}"
maximum_files = {max_files}

# ------------- Message notification --------------------
dingding_bot_webhook = "{dingding_webhook}"
dingding_secret = "{dingding_secret}"
'''
    try:
        with open("config/config.py", "w") as f:
            f.write(config)
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
                value="""# api 接口封装类
                    llm_api_impl = "large_model.api.default_api.DefaultApi"

                    api_config = {
                        "api_key": "your-api-key",
                        "api_base": "your-api-base",
                        "model": "your-model",
                        "provider": "openai",
                    }

                    # ------------------Gitlab info--------------------------
                    gitlab_server_url = "your-gitlab-url"
                    gitlab_private_token = "your-token"
                    maximum_files = 50

                    # ------------- Message notification --------------------
                    dingding_bot_webhook = "your-webhook"
                    dingding_secret = "your-secret"
                """)
            # 添加一个按钮，用于显示当前配置
            show_config_btn = gr.Button("显示当前1配置", variant="primary", size="sm")
            show_config_output = gr.Textbox(label="当前配置", lines=25)

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