import concurrent.futures
import threading

from retrying import retry
from config.config import GPT_MESSAGE, MAX_FILES
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import filter_diff_content, add_context_to_diff
from utils.logger import log
from utils.args_check import file_need_check
from utils.tools import create_markdown_table


def chat_review(changes, generate_review, *args, **kwargs):
    log.info('开始code review')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        review_results = []
        result_lock = threading.Lock()

        def process_change(change):
            result = generate_review(change, *args, **kwargs)
            with result_lock:
                review_results.append(result)

        futures = []
        for change in changes:
            if not file_need_check(change["new_path"]):
                log.info(f"{change['new_path']} 非目标检测文件！")
                continue
            
            futures.append(executor.submit(process_change, change))

        # 等待所有任务完成
        concurrent.futures.wait(futures)

    # 合并结果
    return "\n\n".join(review_results) if review_results else ""

@retry(stop_max_attempt_number=3, wait_fixed=60000)
def chat_review_summary(changes, model):

    summary_note = ""
    diff_list = []
    file_list = []
    # 获取所有diff和变更文件
    for change in changes:
        diff_list.append(change['diff'])
        file_list.append(change['new_path'])
    for i in range(len(file_list)):
        file_list[i] = f"`{file_list[i]}`<br>"

    messages = [
        {
            "role": "system",
            "content": "你是一位资深编程专家，gitlab的分支代码变更将以git diff 字符串数组的形式提供，diff包括多个地方的代码修改，请从中提取出\
         主要的代码变更，并将这些变更总结为一段简洁的描述，突出关键的修改内容和其影响，要求只输出一段话，不需要分点回答。"
        },
        {
            "role": "user",
            "content": f"请review这部分代码变更 {diff_list}",
        },
    ]
    log.info("LLM 对代码变更总结中...")
    model.generate_text(messages)
    response_content = model.get_respond_content().replace('\n\n', '\n')
    log.info("LLM 代码变更总结完成")

    # markdown 总结表格
    headers = ["File(s)", "Change Summary"]
    rows = [
        ["".join(file_list), response_content]
    ]
    markdown_table = create_markdown_table(headers, rows)
    summary_note = f" # ⭐ 总结\n\n {markdown_table} \n\n"
    return summary_note

@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_review_note_with_context(change, model, gitlab_fetcher, merge_info):
    try:
        # prepare
        source_code = gitlab_fetcher.get_file_content(change['new_path'], merge_info['source_branch'])
        new_path = change['new_path']
        content = add_context_to_diff(change['diff'], source_code)
        messages = [
            {
                "role": "system",
                "content": GPT_MESSAGE
             },
            {
                "role": "user",
                "content": f"请review这部分代码变更 {content}",
            },
        ]
        
        # review
        log.info(f"发送给 LLM 内容如下：{messages}")
        model.generate_text(messages)
        log.info(f'对 {new_path} review中...')
        response_content = model.get_respond_content().replace('\n\n', '\n')
        total_tokens = model.get_respond_tokens()
        
        # response 
        review_note = f'# 📚`{new_path}`' + '\n\n'
        review_note += f'({total_tokens} tokens) {"AI review 意见如下:"}' + '\n\n'
        review_note += response_content + "\n\n---\n\n---\n\n"
        
        log.info(f'对 {new_path} review结束')
        return review_note
    
    except Exception as e:
        log.error(f"LLM Review error:{e}")
        return ""


class MainReviewHandle(ReviewHandle):
    def merge_handle(self, gitlabMergeRequestFetcher, gitlabRepoManager, hook_info, reply, model):
        changes = gitlabMergeRequestFetcher.get_changes()
        merge_info = gitlabMergeRequestFetcher.get_info()
        self.default_handle(changes, merge_info, hook_info, reply, model, gitlabMergeRequestFetcher)


    def default_handle(self, changes, merge_info, hook_info, reply, model, gitlab_fetcher):
        if changes and len(changes) <= MAX_FILES:
            review_summary = chat_review_summary(changes, model)
            review_info = chat_review(changes, generate_review_note_with_context, model, gitlab_fetcher, merge_info)
            review_info = review_summary + review_info

            if review_info:
                reply.add_reply({
                    'content': review_info,
                    'msg_type': 'MAIN, SINGLE',
                    'target': 'all',
                })
                reply.add_reply({
                    'title': '__MAIN_REVIEW__',
                    'content': (
                        f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                        f"### 合并请求详情\n"
                        f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                        f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                        f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n\n"
                        f"### 变更详情\n"
                        f"- **修改文件个数**: `{len(changes)}`\n"
                        f"- **Code Review 状态**: ✅\n"
                    ),
                    'target': 'dingtalk',
                    'msg_type': 'MAIN, SINGLE',
                })
            else:
                reply.add_reply({
                    'title': '__MAIN_REVIEW__',
                    'content': (
                        f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                        f"### 合并请求详情\n"
                        f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                        f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                        f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n\n"
                        f"### 变更详情\n"
                        f"- **修改文件个数**: `{len(changes)}`\n"
                        f"- **备注**: 存在已经提交的 MR，所有文件已进行 MR\n"
                        f"- **Code Review 状态**: pass ✅\n"
                    ),
                    'target': 'dingtalk',
                    'msg_type': 'MAIN, SINGLE',
                })


        elif changes and len(changes) > MAX_FILES:
            reply.add_reply({
                'title': '__MAIN_REVIEW__',
                'content': (
                    f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                    f"### 备注\n"
                    f"修改 `{len(changes)}` 个文件 > 50 个文件，不进行 Code Review ⚠️\n\n"
                    f"### 合并请求详情\n"
                    f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                    f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                    f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n"
                ),
                'target': 'dingtalk',
                'msg_type': 'MAIN, SINGLE',
            })

        else:
            log.error(f"获取merge_request信息失败，project_id: {hook_info['project']['id']} |"
                      f" merge_iid: {hook_info['object_attributes']['iid']}")


