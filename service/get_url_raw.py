# -*- coding: utf-8 -*-
import urllib.parse
import requests
from config.config import gitlab_private_token, gitlab_server_url
from utils.logger import log


def encode_file_path(file_path):
    """
    对文件路径进行URL编码
    """
    encoded_file_path = urllib.parse.quote(file_path, safe='')
    return encoded_file_path


def get_gitlab_file_content(project_id, file_path, version):
    """
    get gitlab file content from file path
    :param project_id: Project ID
    :param file_path: file path
    :param version: branch or tag
    :return: if request is ok return file content else return None
    """

    headers = {
        'PRIVATE-TOKEN': gitlab_private_token
    }
    file_path = encode_file_path(file_path)
    url = f'{gitlab_server_url}/api/v4/projects/{project_id}/repository/files/{file_path}/raw?ref={version}'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        log.info(f'{url} API请求成功：{response.status_code} {response.reason}')
        file_content = response.text
        return file_content
    else:
        log.error(f'{url} API请求失败：{response.status_code} {response.reason}')
        return None
