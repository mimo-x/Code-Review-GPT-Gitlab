"""Claude Code 引擎：在 MR 的临时工作树里运行 claude 命令行。"""
from __future__ import annotations

import json
import logging
import os
import subprocess

from django.conf import settings

from .base import EngineError, ReviewEngine, ReviewRequest, ReviewResult
from .output import parse_output
from .prompting import build_review_prompt

logger = logging.getLogger(__name__)

WORKSPACE_NOTE = (
    "当前目录是这个 MR 最新提交的工作区，需要上下文时可以读取和搜索其中的文件。"
    "审查范围只限下面的 diff，不要修改任何文件。"
)


class ClaudeCli:
    """claude 可执行文件的调用封装；环境变量只进子进程，不写入全局。"""

    def __init__(self, cli_path="claude", timeout=300, anthropic_base_url=None,
                 anthropic_auth_token=None):
        self.cli_path = cli_path
        self.timeout = timeout
        self.anthropic_base_url = anthropic_base_url
        self.anthropic_auth_token = anthropic_auth_token

    @classmethod
    def from_config(cls) -> "ClaudeCli":
        """配置优先级：数据库 > 环境变量 > 默认值。"""
        from apps.llm.models import ClaudeCliConfig

        config = ClaudeCliConfig.objects.filter(is_active=True).first()
        if config:
            return cls(
                cli_path=config.cli_path or "claude",
                timeout=config.timeout or 300,
                anthropic_base_url=config.anthropic_base_url,
                anthropic_auth_token=config.anthropic_auth_token,
            )
        return cls(
            cli_path=getattr(settings, "CLAUDE_CLI_PATH", "claude"),
            timeout=getattr(settings, "CLAUDE_CLI_TIMEOUT", 300),
            anthropic_base_url=os.environ.get("ANTHROPIC_BASE_URL"),
            anthropic_auth_token=os.environ.get("ANTHROPIC_AUTH_TOKEN"),
        )

    def environment(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = self.anthropic_base_url
        if self.anthropic_auth_token:
            env["ANTHROPIC_AUTH_TOKEN"] = self.anthropic_auth_token
        return env

    def validate_cli_installation(self) -> tuple[bool, str | None]:
        try:
            result = self._probe("--help")
        except FileNotFoundError:
            return False, f"Claude CLI not found at: {self.cli_path}"
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"Error validating Claude CLI: {exc}"
        if result.returncode != 0:
            return False, f"Claude CLI help command failed: {result.stderr}"
        return True, None

    def get_cli_version(self) -> tuple[bool, str | None, str | None]:
        try:
            result = self._probe("--version")
        except (OSError, subprocess.SubprocessError) as exc:
            return False, None, str(exc)
        if result.returncode != 0:
            return False, None, result.stderr
        return True, result.stdout.strip(), None

    def _probe(self, flag: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.cli_path, flag],
            env=self.environment(),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def run(self, prompt: str, cwd) -> dict:
        """提示词走 stdin：diff 可能超过单个命令行参数的长度限制。"""
        try:
            process = subprocess.run(
                [self.cli_path, "-p", "--output-format", "json"],
                input=prompt,
                cwd=cwd,
                env=self.environment(),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineError(f"Claude CLI timeout after {self.timeout}s") from exc
        except FileNotFoundError as exc:
            raise EngineError(f"Claude CLI not found at: {self.cli_path}") from exc
        except OSError as exc:
            raise EngineError(f"Error executing Claude CLI: {exc}") from exc
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "").strip()[:500]
            raise EngineError(f"Claude CLI 执行失败: {detail}")
        try:
            data = json.loads(process.stdout.strip())
        except json.JSONDecodeError as exc:
            raise EngineError("Failed to parse Claude CLI JSON output") from exc
        if data.get("is_error"):
            raise EngineError(f"Claude CLI 返回错误: {data.get('result', 'unknown')}")
        return data


class ClaudeCodeEngine(ReviewEngine):
    kind = "claude_code"
    needs_worktree = True

    def review(self, request: ReviewRequest) -> ReviewResult:
        cli = ClaudeCli.from_config()
        valid, error = cli.validate_cli_installation()
        if not valid:
            raise EngineError(f"代码审查失败：{error}")
        data = cli.run(build_review_prompt(request, WORKSPACE_NOTE), cwd=request.worktree)
        parsed = parse_output(data.get("result", ""))
        return ReviewResult(
            provider="claude-cli",
            model=next(iter(data.get("modelUsage") or {}), "claude-cli"),
            summary=parsed.summary,
            findings=parsed.findings,
            structured=parsed.structured,
            usage=data.get("usage") or {},
            metadata={
                "duration_ms": data.get("duration_ms", 0),
                "num_turns": data.get("num_turns", 0),
                "total_cost_usd": data.get("total_cost_usd", 0.0),
            },
        )
