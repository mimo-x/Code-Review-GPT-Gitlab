import requests
from tabulate import tabulate

def check_config():
    """
    Check the configuration
    :return: bool
    """
    results = []
    try:
        import config.config as config
        if check_exist(config, ["llm_api_impl", "api_config", "gpt_message",
                                "gitlab_server_url", "gitlab_private_token", "dingding_bot_webhook", "dingding_secret"]):
            results.append(["Configuration parameter existence", "Passed", "", "✅ Required parameters are available."])
        else:
            results.append(["Configuration parameter existence", "Failed", "Required parameters are missing", "❌ Required parameters are missing"])
            return print_results(results)

        api_check = check_api_config(config)
        if api_check['passed']:
            results.append(["API interface", "Passed", "", "✅ Model invocation can be used."])
        else:
            results.append(["API interface", "Failed", "\n".join(api_check['errors']), "❌ Model invocation cannot be used."])

        gitlab_check = check_gitlab_config(config)
        if gitlab_check['passed']:
            results.append(["Gitlab configuration", "Passed", "", "✅ Code review function can be used.\n✅ Comment function can be used."])
        else:
            results.append(["Gitlab configuration", "Failed",
                            "\n".join(gitlab_check['errors']),
                            "❌ Code review function cannot be used.\n❌ Comment function cannot be used."])
        dingding_check = check_dingding_config(config)
        if dingding_check['passed']:
            results.append(["Dingding configuration", "Passed", "", "✅ Notification on Dingtalk function can be used."])
        else:
            results.append(["Dingding configuration", "Failed",
                            "\n".join(dingding_check['errors']),
                            "⚠️ Notification on Dingtalk function cannot be used."])
    except ImportError:
        results.append(["Configuration file", "Failed", "config.py not found",
                        "❌ Cannot run any Service, please create a config.py file"])
        return print_results(results)
    except Exception as e:
        results.append(["Configuration file", "Failed", f"Error loading config.py: {e}",
                        "❌ Cannot run any Service, please check config.py file"])
        return print_results(results)

    return print_results(results)

def check_dingding_config(config):
    """
    Check the dingding configuration
    :return: dict
    """
    result = {'passed': True, 'errors': []}
    try:
        from response_module.response_target.msg_response.dingtalk_response import DingtalkResponse
        dingtalk_reply = DingtalkResponse({'type': 'merge_request', 'project_id': 1, 'merge_request_iid': 1})
        response = dingtalk_reply.send("连通性测试：测试消息，请勿回复。")
        if not response:
            error_msg = "Dingding configuration is invalid"
            result['errors'].append(error_msg)
            result['passed'] = False

    except Exception as e:
        result['errors'].append(str(e))
        result['passed'] = False

    return result

def check_gitlab_config(config):
    """
    Check the gitlab configuration
    :return: dict
    """
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

def check_api_config(config):
    """
    Check the API configuration
    :return: dict
    """
    result = {'passed': True, 'errors': []}
    try:
        from large_model.llm_generator import LLMGenerator
        api = LLMGenerator.new_model()
        api.generate_text([
            {"role": "system",
             "content": "你是一个有用的助手"
             },
            {"role": "user",
             "content": "请输出ok两个小写字母，不要输出其他任何内容",
             }
        ])
        res_str = api.get_respond_content()
        if not res_str or res_str == "":
            error_msg = "Model interface check failed: Please check if the model call related configuration is correct"
            result['errors'].append(error_msg)
            result['passed'] = False
        elif "ok" not in res_str:
            warning_msg = "Model interface check failed: The model did not return the expected result, but may still be available"
            result['errors'].append(warning_msg)
            result['passed'] = False

    except Exception as e:
        result['errors'].append(str(e))
        result['passed'] = False

    return result

def check_exist(config, arg_names):
    """
    Check if the variable is defined
    :param arg_names: variable name list
    :return: bool
    """
    res = True
    errors = []
    for arg_name in arg_names:
        if not hasattr(config, arg_name):
            errors.append(f"{arg_name} not found in config.py")
            res = False
    if errors:
        print("\n".join(errors))
    return res

def wrap_text(text, width):
    """
    Wrap text to a specified width.
    :param text: The text to wrap.
    :param width: The maximum width of each line.
    :return: The wrapped text.
    """
    if not text:
        return ""
    lines = []
    while len(text) > width:
        # Find the last space within the width limit
        wrap_at = text.rfind(' ', 0, width)
        if wrap_at == -1:
            wrap_at = width
        lines.append(text[:wrap_at])
        text = text[wrap_at:].lstrip()
    lines.append(text)
    return "\n".join(lines)

def print_results(results):
    """
    Print the results in a tabulated format
    :param results: list of lists containing the check results
    """
    wrapped_results = []
    for result in results:
        wrapped_result = [wrap_text(result[0], 30), wrap_text(result[1], 10),
                          wrap_text(result[2], 50), result[3]]
        wrapped_results.append(wrapped_result)
    table = tabulate(wrapped_results, headers=["Check", "Status", "Details", "Influence Service"], tablefmt="grid", stralign="left")
    print(table)
    return all(result[1] == "Passed" for result in results)

# 示例调用
if __name__ == "__main__":
    if check_config():
        print("All configuration checks passed")
    else:
        print("Some configuration checks failed")
