import requests
from retrying import retry
from config.config import *
from utils.logger import log
from utils.dingding import send_dingtalk_message_by_sign

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_merge_request_id(branch_name, project_id):
    """
    根据分支名，获取mr_id
    :param branch_name: 分支名
    :param project_id: 项目id
    :return: 如果分支存在 mr 则返回mrid / 如果不存在mr 则返回 ""
    """
    url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests"

    params = {
        "source_branch": branch_name,
        "state": "opened"  # 可以根据需求选择合适的状态（opened、closed、merged等）
    }
    
    headers = {"Private-Token": gitlab_private_token}
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        merge_requests = response.json()
        if len(merge_requests) > 0:
            log.info(f"分支 '{branch_name}' 存在mr记录.{merge_requests}")
            return merge_requests[0].get('iid')
        else:
            log.info(f"分支 '{branch_name}' 没有未关闭的mr.")
    else:
        log.error(f"获取分支'{branch_name}' 失败！. Status code: {response.status_code}")
    return None


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_commit_list(merge_request_iid, project_id):
    api_url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/commits"
    
    headers = {"PRIVATE-TOKEN": gitlab_private_token}
    response = requests.get(api_url, headers=headers)

    commit_list = []
    if response.status_code == 200:
        commits = response.json()
        for commit in commits:
            print(f"Commit ID: {commit['id']}, Message: {commit['message']}")
            commit_list.append(commit['id'])
    else:
        log.error(f"Failed to fetch commits. Status code: {response.status_code}")
    return commit_list


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_merge_request_changes(project_id, merge_id):
    # URL for the GitLab API endpoint
    url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests/{merge_id}/changes"

    # Headers for the request
    headers = {
        "PRIVATE-TOKEN": gitlab_private_token
    }

    # Make the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        return response.json()["changes"]
    else:
        return None


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def add_comment_to_mr(project_id, merge_request_id, comment):
    """
    添加评论到GitLab的Merge Request

    :param gitlab_url: GitLab的基础URL
    :param project_id: 项目ID
    :param merge_request_id: Merge Request的ID
    :param token: GitLab的API token
    :param comment: 要添加的评论内容
    :return: Response JSON
    """
    headers = {
        "Private-Token": gitlab_private_token,
        "Content-Type": "application/json"
    }

    url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_id}/notes"
    data = {
        "body": comment
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 201:
        log.info(f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id}")
        return response.json()
    else:
        log.error(f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id} response:{response}")
        send_dingtalk_message_by_sign(f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id} response:{response}")
        response.raise_for_status()



@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_merge_request_comments(project_id, merge_request_iid):
    url = f"{gitlab_server_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/notes"

    headers = {"Private-Token": gitlab_private_token}
    response = requests.get(url, headers=headers)

    comments_content = ""
    if response.status_code == 200:
        comments = response.json()
        for comment in comments:
            author_username = comment['author']['username']
            comment_body = comment['body']
            print(f"Author: {author_username}")
            print(f"Comment: {comment_body}")
            comments_content += comment_body

    else:
        print(f" 获取mr comment 失败， Status code: {response.status_code}")
    return comments_content


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_commit_change_file(push_info):
    # 获取提交列表
    commit_list = push_info['commits']
    added_files_list = []
    modified_files_list = []
    # 遍历提交
    for commit in commit_list:
        added_files = commit.get('added', [])
        modified_files = commit.get('modified', [])
        added_files_list += added_files
        modified_files_list += modified_files

    return added_files_list + modified_files_list
