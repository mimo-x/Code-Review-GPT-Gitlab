import importlib
import os
import pkgutil
import subprocess
import sys

from utils.logger import log


def import_submodules(package_name):
    # 确保正确的工作目录
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    package = importlib.import_module(package_name)
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package_name}.{module_name}")

def run_command(command):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            log.info(output.strip())

    process.wait()
    out = process.communicate()
    out_len = len(out)
    # 获取是否有[1]
    if out_len > 1:
        stdout_output = out[1]
        if stdout_output:
            log.info(stdout_output.strip())
    if out_len > 2:
        stderr_output = out[2]
        if stderr_output:
            log.error(stderr_output.strip())
    return process.returncode

if __name__ == "__main__":
    from config.config import *
    def _build_authenticated_url(repo_url):
        # 如果 URL 使用 https
        token = gitlab_private_token
        if repo_url.startswith("https://"):
            return f"https://oauth2:{token}@{repo_url[8:]}"
        # 如果 URL 使用 http
        elif repo_url.startswith("http://"):
            return f"http://oauth2:{token}@{repo_url[7:]}"
        else:
            raise ValueError("Unsupported URL scheme")
    authenticated_url = _build_authenticated_url(gitlab_server_url)

    # Build the Git command
    branch_name = "test3"
    repo_path = "./repo"
    command = ["git", "clone", "--depth", "1"]
    if branch_name:
        command.extend(["--branch", branch_name])
        command.extend([authenticated_url, repo_path + "/" + str(branch_name)])
    else:
        command.extend([authenticated_url, repo_path + "/default"])
    # command 打印为字符串
    print(" ".join(command))
    # command 添加clone到的位置：
    if run_command(command) != 0:
        log.error("Failed to clone the repository")