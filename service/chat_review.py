import concurrent.futures
import threading
import openai
from openai import OpenAIError
from app.gitlab_utils import *
from config.config import gitlab_server_url, gitlab_private_token, openai_api_key, openai_baseurl, openai_model_name
from service.content_handle import filter_diff_content
from utils.logger import log
from utils.dingding import send_dingtalk_message_by_sign

# 配置openai
headers = {
    "PRIVATE-TOKEN": gitlab_private_token,
}


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def post_comments(project_id, commit_id, content):
    """
    add comment for gitlab's commits
    :param project_id: gitlab peoject id
    :param commit_id: gitlab commit id
    :param content: comment info
    :return: None
    """
    data = {
        'note': content
    }
    comments_url = f'{gitlab_server_url}/api/v4/projects/{project_id}/repository/commits/{commit_id}/comments'
    response = requests.post(comments_url, headers=headers, json=data)
    log.debug(f"请求结果: {response.json}")
    if response.status_code == 201:
        comment_data = response.json()
        # 处理创建的评论数据
        log.info(f"创建评论成功，评论id: {comment_data}")
    else:
        log.error(f"请求失败，状态码: {response.status_code}")


def wait_and_retry(exception):
    return isinstance(exception, OpenAIError)


@retry(retry_on_exception=wait_and_retry, stop_max_attempt_number=3, wait_fixed=60000)
def generate_review_note(change):
    try:
        content = filter_diff_content(change['diff'])
        openai.api_key = openai_api_key
        openai.api_base = openai_baseurl
        messages = [
            {"role": "system",
             "content": gpt_message
             },
            {"role": "user",
             "content": f"请review这部分代码变更{content}",
             },
        ]
        log.info(f"发送给gpt 内容如下：{messages}")
        response = openai.ChatCompletion.create(
            model=openai_model_name,
            messages=messages,
        )
        new_path = change['new_path']
        log.info(f'对 {new_path} review中...')
        response_content = response['choices'][0]['message']['content'].replace('\n\n', '\n')
        total_tokens = response['usage']['total_tokens']
        review_note = f'# 📚`{new_path}`' + '\n\n'
        review_note += f'({total_tokens} tokens) {"AI review 意见如下:"}' + '\n\n'
        review_note += response_content + """
    ----
    ----
    ----
    ----
    ----
    ----
    ----
        """
        log.info(f'对 {new_path} review结束')
        return review_note
    except Exception as e:
        send_dingtalk_message_by_sign(f"GPT error:{e}")
        log.error(f"GPT error:{e}")


def chat_review(index, project_id, project_commit_id, content, context, merge_comment_info):
    log.info('开始code review')
    if index:
        review_info = f"\n# {index}.commit_id {project_commit_id} \n"
    else:
        log.info(f"🚚 mr_changes{content}")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = []
        result_lock = threading.Lock()

        def process_input(val):
            result = generate_review_note(val)
            with result_lock:
                results.append(result)

        futures = []
        for change in content:
            if any(change["new_path"].endswith(ext) for ext in ['.py', '.java', '.class', '.vue', ".go"]) and not any(
                change["new_path"].endswith(ext) for ext in ["mod.go"]):
                futures.append(executor.submit(process_input, change))
            else:
                log.info(f"{change['new_path']} 非目标检测文件！")

        concurrent.futures.wait(futures)

    return "\n\n".join(results) if results else ""


# 针对于每个 commit 进行 cr
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def review_code(project_id, project_commit_id, merge_id, context):
    review_info = ""
    index = 0
    for commit_id in project_commit_id:
        index += 1
        url = f'{gitlab_server_url}/api/v4/projects/{project_id}/repository/commits/{commit_id}/diff'
        log.info(f"开始请求gitlab的{url}   ,commit: {commit_id}的diff内容")

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            # 开始处理请求的类容
            log.info(f"开始处理All请求的类容: {content}")
            review_info += chat_review(index, project_id, commit_id, content, context, "")

        else:
            log.error(f"请求gitlab的{url}commit失败，状态码：{response.status_code}")
            raise Exception(f"请求gitlab的{url}commit失败，状态码：{response.status_code}")
    add_comment_to_mr(project_id, merge_id, review_info)


# 针对mr进行cr
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def review_code_for_mr(project_id, merge_id, gitlab_message):
    # 获取diff分支的修改文件列表
    changes = get_merge_request_changes(project_id, merge_id)

    if changes and len(changes) <= maximum_files:
        # Code Review 信息
        review_info = chat_review("", project_id, "", changes, "", "")
        if review_info:
            add_comment_to_mr(project_id, merge_id, review_info)
            send_dingtalk_message_by_sign(
                f"project_name:{gitlab_message['project']['name']}\nmr_url:{gitlab_message['object_attributes']['url']}\nfrom:{gitlab_message['object_attributes']['source_branch']} to:{gitlab_message['object_attributes']['target_branch']} \n修改文件个数：{len(changes)}\ncodereview状态：✅")
        else:
            send_dingtalk_message_by_sign(
                f"project_name:{gitlab_message['project']['name']}\nmr_url:{gitlab_message['object_attributes']['url']}\nfrom:{gitlab_message['object_attributes']['source_branch']} to:{gitlab_message['object_attributes']['target_branch']} \n修改文件个数：{len(changes)} 存在已经提交mr，所有文件已进行mr \ncodereview状态：pass✅")

    elif changes and len(changes) > maximum_files:
        send_dingtalk_message_by_sign(
            f"project_name:{gitlab_message['project']['name']}\n备注：修改{len(changes)} > 50个文件不进行codereview ⚠️ \nmr_url:{gitlab_message['object_attributes']['url']}\nfrom:{gitlab_message['object_attributes']['source_branch']} to:{gitlab_message['object_attributes']['target_branch']}")
    else:
        send_dingtalk_message_by_sign(
            f"project_name:{gitlab_message['project']['name']}\n获取merge_request信息失败❌，project_id:{project_id} | merge_id{merge_id} | mr:{gitlab_message}")
        log.error(f"获取merge_request信息失败，project_id:{project_id} | merge_id{merge_id}")
        raise Exception(f"获取merge_request信息失败，project_id:{project_id} | merge_id{merge_id}")


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def review_code_for_add_commit(project_id, merge_id, commit_change_files, gitlab_message):
    """
    code review for gitlab commit
    :param project_id:
    :param merge_id:
    :param commit_change_files:
    :param gitlab_message:
    :return: 
    """
    if len(commit_change_files) > 50:
        send_dingtalk_message_by_sign(
            f"project_name:{gitlab_message['project']['name']}\n备注：(增量commit)修改文件{len(commit_change_files)}个 > 50个 不进行codereview ⚠️ \n分支名：{gitlab_message.get('ref')}")

    # 获取diff分支的修改文件列表
    merge_change_files = get_merge_request_changes(project_id, merge_id)

    # 根据增量commit 修改文件列表过滤merge request二次修改的文件
    change_files = [file_content for file_content in merge_change_files if
                    file_content["new_path"] in commit_change_files]

    print("😊增量commit 修改文件列表", change_files)
    if len(change_files) <= 50:
        review_info = chat_review("", project_id, "", change_files, "", "")
        if review_info:
            add_comment_to_mr(project_id, merge_id, review_info)
            send_dingtalk_message_by_sign(
                f"project_name:{gitlab_message['project']['name']}\n增量修改文件个数：{len(change_files)}\ncodereview状态：✅")

    else:
        send_dingtalk_message_by_sign(
            f"project_name:{gitlab_message['project']['name']}\n备注：增量commit 修改{len(change_files)} > 50个文件不进行codereview ⚠️ \n")


