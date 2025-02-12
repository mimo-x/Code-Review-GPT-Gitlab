import requests
from retrying import retry
from config.config import *
from utils.logger import log

class GitlabMergeRequestFetcher:
    def __init__(self, project_id, merge_request_iid):
        self.project_id = project_id
        self.iid = merge_request_iid

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_changes(self):
        """
        Get the changes of the merge request
        :return: changes
        """
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}/changes"

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
    def get_info(self):
        # URL for the GitLab API endpoint
        url = f"{gitlab_server_url}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": gitlab_private_token
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            return None