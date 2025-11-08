"""
Claude CLI Service for Code Review
Handles Claude CLI command execution and output parsing
"""
import os
import json
import logging
import subprocess
from django.conf import settings

logger = logging.getLogger(__name__)


class ClaudeCliService:
    """
    Service for executing Claude CLI commands for code review
    """

    def __init__(self, request_id=None):
        self.request_id = request_id
        self.cli_path = getattr(settings, 'CLAUDE_CLI_PATH', 'claude')
        self.timeout = getattr(settings, 'CLAUDE_CLI_TIMEOUT', 300)
        self.default_prompt = getattr(
            settings,
            'CLAUDE_CLI_DEFAULT_PROMPT',
            "请帮我 code review 最近一次提交的内容，从以下角度分析：\n"
            "1. 代码质量和最佳实践\n"
            "2. 潜在的 bug 和安全问题\n"
            "3. 性能优化建议\n"
            "4. 代码风格和可读性\n\n"
            "请提供具体的改进建议。"
        )

    def review_code(self, repo_path, custom_prompt=None, commit_range=None):
        """
        使用 Claude CLI 执行代码审查

        Args:
            repo_path: 仓库本地路径
            custom_prompt: 自定义审查提示（可选）
            commit_range: Git 提交范围，如 "HEAD~1..HEAD"（可选）

        Returns:
            (success, result_data, error_message)
            result_data 格式:
            {
                "type": "result",
                "subtype": "success",
                "result": "审查内容...",
                "duration_ms": 12345,
                "usage": {...},
                ...
            }
        """
        prompt = custom_prompt or self.default_prompt

        logger.info(f"[{self.request_id}] Starting Claude CLI code review")
        logger.info(f"[{self.request_id}] Repository: {repo_path}")
        logger.info(f"[{self.request_id}] Commit range: {commit_range or 'latest commit'}")

        try:
            # 构建 Claude 命令
            command = self._build_command(prompt, commit_range)

            # 执行命令
            success, output, error = self._execute_command(command, repo_path)

            if not success:
                logger.error(f"[{self.request_id}] Claude CLI execution failed: {error}")
                return False, None, error

            # 解析 JSON 输出
            result_data = self._parse_json_output(output)

            if result_data is None:
                error_msg = "Failed to parse Claude CLI JSON output"
                logger.error(f"[{self.request_id}] {error_msg}")
                return False, None, error_msg

            # 检查是否成功
            if result_data.get('is_error', False):
                error_msg = result_data.get('result', 'Unknown error from Claude CLI')
                logger.error(f"[{self.request_id}] Claude CLI returned error: {error_msg}")
                return False, result_data, error_msg

            logger.info(f"[{self.request_id}] Claude CLI review completed successfully")
            logger.info(f"[{self.request_id}] Duration: {result_data.get('duration_ms', 0)}ms")

            return True, result_data, None

        except Exception as e:
            error_msg = f"Unexpected error during Claude CLI execution: {str(e)}"
            logger.error(f"[{self.request_id}] {error_msg}", exc_info=True)
            return False, None, error_msg

    def _build_command(self, prompt, commit_range=None):
        """
        构建 Claude CLI 命令

        Args:
            prompt: 审查提示
            commit_range: Git 提交范围

        Returns:
            命令列表
        """
        command = [self.cli_path, '-p', prompt, '--output-format', 'json']

        # 如果指定了提交范围，可以在 prompt 中包含
        if commit_range:
            # Claude CLI 会自动分析当前目录的 git 状态
            # 我们可以通过 prompt 指导它关注特定的提交范围
            pass

        return command

    def _execute_command(self, command, cwd):
        """
        执行 Claude CLI 命令

        Args:
            command: 命令列表
            cwd: 工作目录

        Returns:
            (success, stdout, stderr)
        """
        try:
            logger.info(f"[{self.request_id}] Executing: {' '.join(command)}")
            logger.info(f"[{self.request_id}] Working directory: {cwd}")

            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )

            if result.returncode == 0:
                logger.info(f"[{self.request_id}] Claude CLI command succeeded")
                return True, result.stdout, result.stderr
            else:
                logger.error(f"[{self.request_id}] Claude CLI command failed with code {result.returncode}")
                logger.error(f"[{self.request_id}] Stderr: {result.stderr}")
                return False, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            error_msg = f"Claude CLI timeout after {self.timeout}s"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, "", error_msg

        except FileNotFoundError:
            error_msg = f"Claude CLI not found at: {self.cli_path}"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, "", error_msg

        except Exception as e:
            error_msg = f"Error executing Claude CLI: {str(e)}"
            logger.error(f"[{self.request_id}] {error_msg}", exc_info=True)
            return False, "", error_msg

    def _parse_json_output(self, output):
        """
        解析 Claude CLI 的 JSON 输出

        Args:
            output: 命令输出

        Returns:
            解析后的字典，失败返回 None
        """
        try:
            # Claude CLI 输出的是单行 JSON
            data = json.loads(output.strip())

            logger.debug(f"[{self.request_id}] Parsed JSON output successfully")
            logger.debug(f"[{self.request_id}] Type: {data.get('type')}, Subtype: {data.get('subtype')}")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"[{self.request_id}] JSON parse error: {e}")
            logger.error(f"[{self.request_id}] Output: {output[:500]}...")  # 只记录前500字符
            return None

        except Exception as e:
            logger.error(f"[{self.request_id}] Unexpected error parsing output: {e}")
            return None

    def review_with_security_focus(self, repo_path, commit_range=None):
        """
        执行安全性重点的代码审查

        Args:
            repo_path: 仓库路径
            commit_range: 提交范围

        Returns:
            (success, result_data, error_message)
        """
        security_prompt = (
            "请帮我 code review 最近一次提交的内容，从安全角度进行深度分析：\n\n"
            "1. **安全漏洞检测**\n"
            "   - SQL 注入风险\n"
            "   - XSS 跨站脚本漏洞\n"
            "   - CSRF 跨站请求伪造\n"
            "   - 命令注入风险\n"
            "   - 路径遍历漏洞\n\n"
            "2. **敏感信息泄露**\n"
            "   - 硬编码的密码、API Key、Token\n"
            "   - 敏感数据明文存储或传输\n"
            "   - 日志中的敏感信息\n\n"
            "3. **认证和授权**\n"
            "   - 认证机制缺陷\n"
            "   - 权限校验不当\n"
            "   - 会话管理问题\n\n"
            "4. **输入验证**\n"
            "   - 缺少输入验证\n"
            "   - 不安全的序列化\n\n"
            "请详细说明发现的每个安全问题，并提供修复建议。"
        )

        return self.review_code(repo_path, security_prompt, commit_range)

    def review_with_performance_focus(self, repo_path, commit_range=None):
        """
        执行性能优化重点的代码审查

        Args:
            repo_path: 仓库路径
            commit_range: 提交范围

        Returns:
            (success, result_data, error_message)
        """
        performance_prompt = (
            "请帮我 code review 最近一次提交的内容，从性能优化角度分析：\n\n"
            "1. **算法和数据结构**\n"
            "   - 时间复杂度优化机会\n"
            "   - 空间复杂度优化\n"
            "   - 更高效的数据结构选择\n\n"
            "2. **数据库优化**\n"
            "   - N+1 查询问题\n"
            "   - 缺少索引\n"
            "   - 低效的查询语句\n\n"
            "3. **资源管理**\n"
            "   - 内存泄漏风险\n"
            "   - 未关闭的资源\n"
            "   - 缓存使用机会\n\n"
            "4. **并发和异步**\n"
            "   - 可以异步处理的操作\n"
            "   - 并发安全问题\n\n"
            "请提供具体的性能优化建议和预期收益。"
        )

        return self.review_code(repo_path, performance_prompt, commit_range)

    def get_cli_version(self):
        """
        获取 Claude CLI 版本

        Returns:
            (success, version, error_message)
        """
        try:
            result = subprocess.run(
                [self.cli_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )

            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"[{self.request_id}] Claude CLI version: {version}")
                return True, version, None
            else:
                return False, None, result.stderr

        except Exception as e:
            return False, None, str(e)

    def validate_cli_installation(self):
        """
        验证 Claude CLI 是否正确安装

        Returns:
            (is_valid, error_message)
        """
        # 检查命令是否存在
        try:
            result = subprocess.run(
                [self.cli_path, '--help'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )

            if result.returncode == 0:
                logger.info(f"[{self.request_id}] Claude CLI is properly installed")
                return True, None
            else:
                error_msg = f"Claude CLI help command failed: {result.stderr}"
                logger.error(f"[{self.request_id}] {error_msg}")
                return False, error_msg

        except FileNotFoundError:
            error_msg = f"Claude CLI not found at: {self.cli_path}"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, error_msg

        except Exception as e:
            error_msg = f"Error validating Claude CLI: {str(e)}"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, error_msg
