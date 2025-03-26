import concurrent.futures
import threading

from retrying import retry

from config.config import gpt_message
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import filter_diff_content
from utils.logger import log


def chat_review(changes, generate_review, *args, **kwargs):
    """
    Concurrently generates code review notes for eligible file changes.
    
    Filters the provided changes based on file extension criteria—processing only files
    ending with .py, .java, .class, .vue, or .go while excluding those ending with
    'mod.go'. For each eligible change, the function concurrently calls the supplied
    review generation function using any additional arguments provided, aggregates the
    results, and returns them joined by two newlines. If no reviews are generated, an empty
    string is returned.
    """
    log.info('开始code review')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        review_results = []
        result_lock = threading.Lock()

        def process_change(change):
            """
            Processes a single code change and appends its review note to shared results.
            
            This function calls the external review generator with the provided change and
            any additional arguments to produce a review note. It then appends the result to
            a shared list in a thread-safe manner.
                
            Args:
                change: The code change object to be reviewed.
            """
            result = generate_review(change,  *args, **kwargs)
            with result_lock:
                review_results.append(result)

        futures = []
        for change in changes:
            if any(change["new_path"].endswith(ext) for ext in ['.py', '.java', '.class', '.vue', ".go"]) and not any(
                change["new_path"].endswith(ext) for ext in ["mod.go"]):
                futures.append(executor.submit(process_change, change))
            else:
                log.info(f"{change['new_path']} 非目标检测文件！")

        concurrent.futures.wait(futures)

    return "\n\n".join(review_results) if review_results else ""

@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_review_note(change, model):
    """
    Generates a formatted review note for a code change.
    
    Extracts and filters the diff content from the provided change, builds messages for the AI model
    to review the change, and formats the response with token count and file path details. Logs the
    progress and any errors encountered.
    
    Parameters:
        change: Dictionary containing code change details, including 'diff' and 'new_path' keys.
        model: AI model instance with methods to generate text and retrieve the generated content and token count.
    
    Returns:
        A string containing the formatted review note.
    """
    try:
        content = filter_diff_content(change['diff'])
        messages = [
            {"role": "system",
             "content": gpt_message
             },
            {"role": "user",
             "content": f"请review这部分代码变更{content}",
             },
        ]
        log.info(f"发送给gpt 内容如下：{messages}")
        model.generate_text(messages)
        new_path = change['new_path']
        log.info(f'对 {new_path} review中...')
        response_content = model.get_respond_content().replace('\n\n', '\n')
        total_tokens = model.get_respond_tokens()
        review_note = f'# 📚`{new_path}`' + '\n\n'
        review_note += f'({total_tokens} tokens) {"AI review 意见如下:"}' + '\n\n'
        review_note += response_content + "\n\n---\n\n---\n\n"
        log.info(f'对 {new_path} review结束')
        return review_note
    except Exception as e:
        log.error(f"GPT error:{e}")


class MainReviewHandle(ReviewHandle):
    def merge_handle(self, gitlabMergeRequestFetcher, gitlabRepoManager, hook_info, reply, model):
        """
        Handles a merge request by fetching changes and merge information.
        
        Retrieves changes and merge details from the GitLab merge request fetcher and delegates
        processing to default_handle along with hook info, reply data, and a review model.
        """
        changes = gitlabMergeRequestFetcher.get_changes()
        merge_info = gitlabMergeRequestFetcher.get_info()
        self.default_handle(changes, merge_info, hook_info, reply, model)

    def default_handle(self, changes, merge_info, hook_info, reply, model):
        """
        Processes a merge request by generating and dispatching code review replies.
        
        This method checks whether the number of file changes in a merge request is within an acceptable
        limit (50 files). For merge requests with changes equal to or below this limit, it attempts to
        generate review content via a code review function. If review information is produced, it sends
        detailed replies containing both the review and merge details; otherwise, it sends a reply indicating
        that an existing merge request has already been processed. If the count of changed files exceeds
        50, a reply is dispatched to indicate that code review is skipped. When no change information is
        provided, an error is logged.
        
        Args:
            changes: A list of file changes included in the merge request.
            merge_info: Merge request information (currently unused).
            hook_info: A dictionary with hook details such as project info, MR URL, and branch names.
            reply: An object used to send replies to various targets.
            model: The model or mechanism used for generating the review note.
        """
        maximum_files = 50
        if changes and len(changes) <= maximum_files:
            # Code Review 信息
            review_info = chat_review(changes, generate_review_note, model)
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


        elif changes and len(changes) > maximum_files:
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


