"""
OpenCode CLI Service for Code Review
Handles OpenCode CLI command execution and output parsing
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


class OpenCodeCliService:
    """Service for executing OpenCode CLI commands for code review"""

    def __init__(self, request_id: str | None = None):
        self.request_id = request_id
        self.cli_path = getattr(settings, 'OPENCODE_CLI_PATH', 'opencode')
        self.timeout = 300
        self.auth_content = ''
        self.config_content = ''
        self.env_content = ''
        self.default_command = 'review'
        self._load_config()

    def _load_config(self):
        """Load CLI settings from database or fall back to env/defaults"""
        try:
            from apps.llm.models import OpenCodeCliConfig

            config = OpenCodeCliConfig.objects.filter(is_active=True).first()
            if config:
                self.timeout = config.timeout or self.timeout
                self.auth_content = config.auth_content or ''
                self.config_content = config.config_content or ''
                self.env_content = config.env_content or ''
                logger.info(f"[{self.request_id}] OpenCode CLI 配置加载成功 - Timeout: {self.timeout}s")
                if self.auth_content:
                    logger.info(f"[{self.request_id}] 已配置 auth.json 内容")
                if self.config_content:
                    logger.info(f"[{self.request_id}] 已配置 opencode.json 内容")
                if self.env_content:
                    logger.info(f"[{self.request_id}] 已配置 .env 内容")
            else:
                logger.info(f"[{self.request_id}] 未找到数据库配置，使用默认 CLI 设置")
        except Exception as exc:
            logger.warning(f"[{self.request_id}] 读取 OpenCode CLI 配置失败: {exc}")

    def validate_cli_installation(self) -> Tuple[bool, str | None]:
        """确认 CLI 可执行"""
        try:
            result = subprocess.run(
                [self.cli_path, '--version'],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                return False, result.stderr.strip() or result.stdout.strip() or 'OpenCode CLI 返回错误'
            return True, None
        except FileNotFoundError:
            return False, f"未找到 OpenCode CLI，可执行文件: {self.cli_path}"
        except Exception as exc:
            return False, str(exc)

    def get_cli_version(self) -> Tuple[bool, str | None, str | None]:
        """获取 CLI 版本"""
        try:
            result = subprocess.run(
                [self.cli_path, '--version'],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return True, result.stdout.strip() or result.stderr.strip(), None
            return False, None, result.stderr.strip() or '获取版本失败'
        except Exception as exc:
            return False, None, str(exc)

    def review_code(self, repo_path: str, commit_range: str | None = None, custom_prompt: str | None = None):
        """
        通过 OpenCode CLI 执行代码审查

        Args:
            repo_path: 仓库路径
            commit_range: 提交范围（传递给 review 命令的参数）

        Returns:
            (success, result_data, error_message)
        """
        start_time = time.time()
        logger.info(f"[{self.request_id}] 启动 OpenCode CLI 审查, repo={repo_path}, range={commit_range}")

        command = self._build_command(commit_range, custom_prompt)
        success, stdout, stderr = self._execute_command(command, repo_path)

        if not success:
            error_msg = stderr or stdout or 'OpenCode CLI 执行失败'
            logger.error(f"[{self.request_id}] OpenCode CLI 执行失败: {error_msg}")
            return False, None, error_msg

        parsed = self._parse_json_output(stdout)
        if parsed is None:
            error_msg = "无法解析 OpenCode CLI 输出"
            logger.error(f"[{self.request_id}] {error_msg}")
            return False, None, error_msg

        parsed['duration_ms'] = int((time.time() - start_time) * 1000)
        logger.info(f"[{self.request_id}] OpenCode CLI 审查完成，耗时 {parsed.get('duration_ms', 0)}ms")
        return True, parsed, None

    def _build_command(self, commit_range: str | None, custom_prompt: str | None) -> List[str]:
        command = [
            self.cli_path,
            'run',
            '--command',
            self.default_command,
            '--format',
            'json',
            '--print-logs',
        ]

        message_parts: List[str] = []
        if commit_range:
            message_parts.append(commit_range)
        if custom_prompt:
            message_parts.append(custom_prompt)

        if message_parts:
            command.append('--')
            command.append('\n\n'.join(message_parts).strip())

        return command

    def _execute_command(self, command: List[str], cwd: str) -> Tuple[bool, str, str]:
        env = os.environ.copy()
        logger.info(f"[{self.request_id}] 执行命令: {' '.join(command)}")
        env.setdefault('OPENCODE_AUTO_SHARE', '0')

        prepared_env, temp_home = self._prepare_environment(env)
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=prepared_env,
                check=False,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, '', f'OpenCode CLI 执行超时（{self.timeout}s）'
        except Exception as exc:
            return False, '', str(exc)
        finally:
            if temp_home:
                shutil.rmtree(temp_home, ignore_errors=True)

    def _parse_json_output(self, stdout: str) -> Dict | None:
        if not stdout:
            return None

        aggregated_text: List[str] = []
        events: List[Dict] = []
        tools_used: Dict[str, int] = {}

        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"[{self.request_id}] 非 JSON 行: {line[:80]}")
                continue

            events.append(event)
            if event.get('type') == 'text':
                part = event.get('part', {})
                text = part.get('text') or ''
                if text:
                    aggregated_text.append(text)
            if event.get('type') == 'tool_use':
                part = event.get('part', {})
                tool_name = part.get('tool') or part.get('state', {}).get('title')
                if tool_name:
                    tools_used[tool_name] = tools_used.get(tool_name, 0) + 1
            if event.get('type') == 'error':
                message = event.get('error') or event
                return {
                    'type': 'result',
                    'subtype': 'error',
                    'is_error': True,
                    'result': json.dumps(message, ensure_ascii=False),
                    'duration_ms': 0,
                    'metadata': {
                        'events': events,
                    },
                }

        result_text = '\n'.join(aggregated_text).strip()
        return {
            'type': 'result',
            'subtype': 'success',
            'is_error': False,
            'result': result_text,
            'duration_ms': 0,
            'metadata': {
                'events_count': len(events),
                'tools_used': tools_used,
            },
        }

    def _prepare_environment(self, env):
        """
        创建临时 HOME，并复制 auth/config/env 配置
        """
        temp_home = tempfile.mkdtemp(prefix='opencode-home-')
        prepared_env = env.copy()
        prepared_env['HOME'] = temp_home

        data_dir = Path(temp_home) / '.local' / 'share' / 'opencode'
        config_dir = Path(temp_home) / '.config' / 'opencode'
        data_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)

        if self.auth_content:
            self._write_content(self.auth_content, data_dir / 'auth.json', 'auth.json')

        if self.config_content:
            self._write_content(self.config_content, config_dir / 'opencode.json', 'opencode.json')

        if self.env_content:
            self._load_env_content(prepared_env, self.env_content)

        return prepared_env, temp_home

    def _write_content(self, content: str, target_path: Path, label: str):
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding='utf-8')
            logger.info(f"[{self.request_id}] 已写入 {label}")
        except Exception as exc:
            logger.warning(f"[{self.request_id}] 写入 {label} 失败: {exc}")

    def _load_env_content(self, env: dict, env_text: str):
        try:
            for raw_line in env_text.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if '=' not in stripped:
                    continue
                key, value = stripped.split('=', 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
            logger.info(f"[{self.request_id}] 已加载 .env 内容，共 {len(env_text.splitlines())} 行")
        except Exception as exc:
            logger.warning(f"[{self.request_id}] 解析 .env 内容失败: {exc}")
