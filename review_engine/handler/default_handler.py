import concurrent.futures
import threading

from retrying import retry

from config.config import gpt_message
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import filter_diff_content
from utils.logger import log


def chat_review(changes, model):
    log.info('开始code review')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        review_results = []
        result_lock = threading.Lock()

        def process_change(change):
            result = generate_review_note(change, model)
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
        log.error(f"GPT error:{e}")


class MainReviewHandle(ReviewHandle):
    def merge_handle(self, changes, merge_info, hook_info, reply, model):
        self.default_handle(changes, merge_info, hook_info, reply, model)

    def default_handle(self, changes, merge_info, hook_info, reply, model):
        maximum_files = 50
        if changes and len(changes) <= maximum_files:
            # Code Review 信息
            review_info = chat_review(changes, model)
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

if __name__ == '__main__':
    main_handle = MainReviewHandle()
    from gitlab_integration.gitlab_fetcher import GitlabMergeRequestFetcher
    from reply_module.reply import Reply
    fetcher = GitlabMergeRequestFetcher(9885, 18)
    changes = fetcher.get_changes()
    info = fetcher.get_info()
    reply = Reply({'type': 'merge_request',
                     'project_id': 9885,
                     'merge_request_iid': 18})
    from large_model.llm_generator import LLMGenerator
    model = LLMGenerator.new_model()
    hook_info = {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "user": {
            "id": 1,
            "name": "John Doe",
            "username": "johndoe",
            "avatar_url": "https://example.com/uploads/user/avatar/1/index.jpg"
        },
        "project": {
            "id": 15,
            "name": "Example Project",
            "description": "An example project",
            "web_url": "https://example.com/example/project",
            "avatar_url": None,
            "git_ssh_url": "git@example.com:example/project.git",
            "git_http_url": "https://example.com/example/project.git",
            "namespace": "Example",
            "visibility_level": 20,
            "path_with_namespace": "example/project",
            "default_branch": "main",
            "homepage": "https://example.com/example/project",
            "url": "https://example.com/example/project.git",
            "ssh_url": "git@example.com:example/project.git",
            "http_url": "https://example.com/example/project.git"
        },
        "object_attributes": {
            "id": 99,
            "iid": 1,
            "target_branch": "main",
            "source_branch": "feature-branch",
            "source_project_id": 15,
            "target_project_id": 15,
            "title": "Merge feature-branch into main",
            "state": "opened",
            "merge_status": "can_be_merged",
            "url": "https://example.com/example/project/-/merge_requests/1",
            "created_at": "2025-02-10T12:34:56Z",
            "updated_at": "2025-02-10T12:34:56Z"
        },
        "changes": {
            "total_changes": 51,
            "files": [
                {"old_path": "file1.txt", "new_path": "file1.txt", "a_mode": "100644", "b_mode": "100644", "diff": "diff content"},
                # ... 50 more file changes ...
            ]
        }
    }
    main_handle.merge_handle(changes, info, hook_info, reply, model)
