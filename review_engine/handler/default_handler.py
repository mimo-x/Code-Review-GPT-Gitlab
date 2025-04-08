import concurrent.futures
import threading

from retrying import retry
from config.config import GPT_MESSAGE, MAX_FILES
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import filter_diff_content, add_context_to_diff
from utils.logger import log
from utils.args_check import file_need_check
from utils.tools import batch
from review_engine.review_prompt import (REVIEW_SUMMARY_SETTING, FILE_DIFF_REVIEW_PROMPT, BATCH_SUMMARY_PROMPT,
                                         FINAL_SUMMARY_PROMPT,SUMMARY_OUTPUT_PROMPT)


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

    return "<details open><summary><h1>修改文件列表</h1></summary>" + "\n\n".join(review_results) +"</details>" if review_results else ""


def chat_review_summary(changes, model):
    log.info("开始 code review summary")
    file_diff_map = {}
    file_summary_map = {}
    summary_lock = threading.Lock()

    for change in changes:
        if change['new_path'] not in file_diff_map:
            if not file_need_check(change["new_path"]):
                continue
            file_diff_map[change['new_path']] = filter_diff_content(change['diff'])

    # 对单个文件diff进行总结
    with concurrent.futures.ThreadPoolExecutor() as executor:
        def process_summary(file, diff, model):
            summary = generate_diff_summary(file, diff, model)
            with summary_lock:
                file_summary_map[file] = summary

        futures = []
        for file, diff in file_diff_map.items():
            futures.append(executor.submit(process_summary, file, diff, model))
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    log.info("code diff review完成，batch summary中")
    summaries_content = ""
    batchsize = 8
    # 分批对单文件summary 进行汇总
    for batch_data in batch(file_summary_map, batchsize):
        for file in batch_data:
            summaries_content += f"---\n{file}: {file_summary_map[file]}\n"
        batch_changesets_prompt = BATCH_SUMMARY_PROMPT.replace("$raw_summary", summaries_content)
        batch_summary_msg = [
            {"role": "system",
             "content": REVIEW_SUMMARY_SETTING
             },
            {"role": "user",
             "content": f"{batch_changesets_prompt}"
             }
        ]
        model.generate_text(batch_summary_msg)
        summaries_content = model.get_respond_content().replace('\n\n', '\n')

    # 总结生成 summary 和 file summary 表格
    final_summaries_content = SUMMARY_OUTPUT_PROMPT.replace("$summaries_content", summaries_content)
    final_summary_msg = [
        {"role": "system",
         "content": REVIEW_SUMMARY_SETTING
         },
        {"role": "user",
         "content": FINAL_SUMMARY_PROMPT
         },
        {"role": "user",
         "content": f"{final_summaries_content}"
         }
    ]
    summary_result = generate_diff_summary(model=model, messages=final_summary_msg)
    log.info("code diff review summary完成")
    return summary_result+"\n\n---\n\n" if summary_result else ""


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_diff_summary(file=None, diff=None, model=None, messages=None):
    file_diff_prompt =  FILE_DIFF_REVIEW_PROMPT.replace('$file_diff', diff) if diff else ""
    messages = [
        {"role": "system",
         "content": REVIEW_SUMMARY_SETTING
         },
        {
            "role": "user",
            "content": f"{file_diff_prompt}",
        },
    ] if messages is None else messages
    model.generate_text(messages)
    response_content = model.get_respond_content().replace('\n\n', '\n')
    if response_content:
        return response_content
    else:
        return "summarize: nothing obtained from LLM"


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
        response_content = response_content.replace(
            '<think>',
            '<details><summary>已深度思考</summary>\n<think>'
        ).replace(
            '</think>',
            '</think>\n</details>\n'
        )
        total_tokens = model.get_respond_tokens()

        # response
        review_note = f"<details><summary>📚<strong><code>{new_path}</code></strong></summary>\
        <div>({total_tokens} tokens) AI review 意见如下:</div> \n\n\n\n {response_content} \n\n <hr><hr></details>"

        # review_note += f'# 📚`{new_path}`' + '\n\n'
        # review_note += f'({total_tokens} tokens) {"AI review 意见如下:"}' + '\n\n'
        # review_note += response_content + "\n\n---\n\n---\n\n"
        
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
                      f" merge_iid: {hook_info['object_attributes']['iid']} | merge_info: {merge_info}")


