"""Review Agent 引擎：在 MR 的临时工作区上，以独立进程运行仓库 agent/ 目录里的审查 agent。

agent 需要 Python 3.12，和后端分开安装；它自己调查代码、去重并做终审，平台只负责
传入提交、模型和档位，再把结果交给统一的后处理和发布。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from apps.llm.services import _routed_model
from apps.llm.provider_api import base_url, provider_model_id

from ..rendering.labels import labels_for
from ..rendering.sanitize import code_span
from ..workspace import changed_paths
from .base import SEVERITIES, EngineError, Finding, Option, ReviewEngine, ReviewRequest, ReviewResult

TIERS = (("low", "日常"), ("high", "加强"), ("xhigh", "专家"))
RESULT_VERSION = "review-agent-result/v1"
API_KEY_ENV = "REVIEW_AGENT_API_KEY"
# 只把这些环境变量带进子进程：agent 读的是 MR 的代码，不该拿到服务端的其他凭据
_PASSED_ENV = ("PATH", "LANG", "LC_ALL", "TZ", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
               "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")


class ReviewAgentEngine(ReviewEngine):
    kind = "review_agent"
    label = "Review Agent"
    description = "基于代码变更图的多 Agent 审查。沿调用和依赖关系分工调查，更容易发现改动在其他模块引发的回归。"
    needs_worktree = True
    reviews_local_diff = True
    options = (
        Option("tier", "审查档位", "select", "low", choices=TIERS),
        Option("max_comments_low", "日常档最多保留问题数", "number", 10,
               minimum=1, maximum=100, advanced=True),
        Option("max_comments_high", "加强档最多保留问题数", "number", 20,
               minimum=1, maximum=100, advanced=True),
        Option("max_comments_xhigh", "专家档最多保留问题数", "number", 30,
               minimum=1, maximum=100, advanced=True),
        Option("timeout", "超时时间（秒）", "number", 1800, minimum=60, maximum=7200,
               advanced=True),
        Option("max_concurrency", "同时进行的模型请求数", "number", 5, minimum=1, maximum=64,
               advanced=True, help="受模型服务的并发限制影响，调高前请确认服务能承受。"),
    )

    def review(self, request: ReviewRequest) -> ReviewResult:
        if request.worktree is None or request.revisions is None:
            raise EngineError("Review Agent 需要 MR 的代码工作区")
        included, excluded = [], []
        for path in changed_paths(request.worktree, request.revisions):
            if request.scope.allows(path):
                included.append(path)
            else:
                excluded.append(path)
        result = ReviewResult(
            provider="review-agent",
            model=self.llm_config.model,
            reviewed_paths=tuple(included),
            excluded_paths=tuple(excluded),
        )
        if not included:
            return result
        python = Path(settings.REVIEW_AGENT_PYTHON)
        if not python.is_file():
            raise EngineError(f"未找到 Review Agent 的运行环境: {python}")
        tier = self.settings["tier"]
        with tempfile.TemporaryDirectory(prefix="review-agent-") as scratch:
            scratch = Path(scratch)
            payload = self._request(request, tier)
            if excluded:
                payload["excluded_paths"] = excluded
            (scratch / "request.json").write_text(
                json.dumps(payload), encoding="utf-8")
            data = self._run(python, scratch)
        if data.get("version") != RESULT_VERSION:
            raise EngineError(f"Review Agent 返回了不支持的结果版本: {data.get('version')}")
        labels = labels_for(request.language)
        result.findings = [_finding(item, labels) for item in data.get("findings", [])]
        result.usage = data.get("usage") or {}
        result.metadata = {"tier": tier, "duration_s": data.get("duration_s"), "dropped": data.get("dropped", 0)}
        result.failed_investigations = len(data.get("errors") or ())
        return result

    def _request(self, request: ReviewRequest, tier: str) -> dict:
        mr, revisions, llm = request.mr, request.revisions, self.llm_config
        connection = llm.connection
        model = {
            "name": _routed_model(connection.provider, llm.model, connection.api_base),
            "api_base": connection.api_base or None,
            "timeout": connection.timeout or 600,
            "max_concurrency": self.settings["max_concurrency"],
        }
        if connection.provider == "openai_responses":
            model.update(
                protocol="responses", name=provider_model_id(connection.provider, llm.model),
                api_base=base_url(connection.provider, connection.api_base),
            )
        return {
            "repository": str(request.worktree),
            "repository_id": f"gitlab-project-{mr.project_id}",
            "base_sha": revisions.base_sha,
            "start_sha": revisions.start_sha,
            "head_sha": revisions.head_sha,
            "merge_request": f"{mr.project_id}!{mr.mr_iid}",
            "state_dir": str(Path(settings.REVIEW_AGENT_STATE_DIR).resolve()),
            "config": {
                "tier": tier,
                "language": "zh-CN" if request.language == "zh-CN" else "en",
                "postprocess": {
                    "final_review": {"max_comments": self.settings[f"max_comments_{tier}"]},
                },
            },
            "model": model,
        }

    def _run(self, python: Path, scratch: Path) -> dict:
        output = scratch / "result.json"
        home = scratch / "home"
        home.mkdir()
        env = {key: os.environ[key] for key in _PASSED_ENV if key in os.environ}
        env.update(HOME=str(home), TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE="1",
                   LITELLM_LOCAL_MODEL_COST_MAP="True")
        if self.llm_config.connection.api_key:
            env[API_KEY_ENV] = self.llm_config.connection.api_key
        command = [str(python), "-m", "review_agent.run", "run",
                   "--request", str(scratch / "request.json"), "--output", str(output)]
        timeout = self.settings["timeout"]
        # 独立进程组：超时后连同 agent 启动的语言服务等子进程一起结束
        process = subprocess.Popen(command, cwd=scratch, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            _, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise EngineError(f"Review Agent 超时（{timeout} 秒）") from None
        if not output.is_file():
            raise EngineError(f"Review Agent 运行失败: {(stderr or '').strip()[-500:]}")
        data = json.loads(output.read_text(encoding="utf-8"))
        if process.returncode != 0 or data.get("error"):
            raise EngineError(f"Review Agent 运行失败: {data.get('error', '未知错误')}")
        return data


def _finding(item: dict, labels: dict) -> Finding:
    body = item.get("body") or ""
    if item.get("condition"):
        body += f"\n\n**{labels['condition']}**{labels['separator']}{item['condition']}"
    places = [code_span(f"{place['path']}:{place['start_line']}") for place in item.get("also") or []]
    if places:
        body += f"\n\n{labels['also_at']}{labels['separator']}{labels['list_separator'].join(places)}"
    severity = item.get("severity")
    return Finding(
        path=item["path"],
        title=item.get("title") or "",
        body=body,
        severity=severity if severity in SEVERITIES else "minor",
        category=item.get("category") or "defect",
        side="old" if item.get("side") == "old" else "new",
        start_line=item.get("start_line"),
        end_line=item.get("end_line"),
        existing_code=item.get("existing_code"),
        engine_meta={"also": item.get("also") or []},
    )
