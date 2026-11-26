"""Review one merge request from a JSON request, for a host platform that runs the agent as
a separate process:

    review-agent run --request request.json --output result.json

The request names the repository, the revisions, the review config and the model; the API
key comes from the REVIEW_AGENT_API_KEY environment variable, never from the request. The
result lists the findings to post (RESULT_VERSION), most important first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import ReviewConfig

RESULT_VERSION = "review-agent-result/v1"
API_KEY_ENV = "REVIEW_AGENT_API_KEY"

STRICT = ConfigDict(extra="forbid")


class ModelSpec(BaseModel):
    model_config = STRICT

    # a LiteLLM model name with its route, e.g. "openai/deepseek-chat"; for the Responses
    # API the model id as the server knows it
    name: str
    api_base: str | None = None
    protocol: Literal["chat", "responses"] = "chat"
    timeout: float = Field(default=600, gt=0)
    retries: int = Field(default=3, ge=0)
    # model requests in flight at once, across every assignment of the review
    max_concurrency: int = Field(default=8, ge=1)


class RunRequest(BaseModel):
    model_config = STRICT

    repository: Path  # a local Git repository holding the revisions
    repository_id: str
    base_sha: str
    head_sha: str
    start_sha: str | None = None
    merge_request: str | None = None
    excluded_paths: tuple[str, ...] = ()
    state_dir: Path  # private, persistent: snapshots and episodes are kept here
    config: dict = Field(default_factory=dict)  # ReviewConfig data, e.g. {"tier": "low"}
    model: ModelSpec


def make_policy(spec: ModelSpec, api_key: str | None):
    from .policy import GatedPolicy, LiteLLMPolicy, ResponsesPolicy

    if spec.protocol == "responses":
        if not spec.api_base:
            raise ValueError("the Responses API needs model.api_base")
        policy = ResponsesPolicy(spec.name, api_base=spec.api_base, api_key=api_key or "",
                                 timeout=spec.timeout, retries=spec.retries)
    else:
        policy = LiteLLMPolicy(spec.name, api_base=spec.api_base, api_key=api_key,
                               timeout=spec.timeout, retries=spec.retries)
    return GatedPolicy(policy, spec.max_concurrency)


def run(request: RunRequest, policy) -> dict:
    from review_core.common import stable_id
    from review_core.intel import CodeIntel
    from review_core.workspace import Workspace

    from .orchestrator import review
    from .trajectory import EpisodeStore

    started = time.monotonic()
    config = ReviewConfig.model_validate(request.config)
    workspace = Workspace.create(
        request.repository, request.state_dir, request.repository_id, request.base_sha,
        request.head_sha, start_sha=request.start_sha, merge_request=request.merge_request,
        excluded_paths=request.excluded_paths)
    case_id = workspace.snapshot.id
    out_dir = request.state_dir / "reviews" / case_id
    model = request.model
    model_route = stable_id((model.protocol, model.name, model.api_base))
    result = review(CodeIntel(workspace), policy, config, run_id=f"{config.tier}-{model_route}",
                    case_id=case_id, out_dir=out_dir)
    store = EpisodeStore(out_dir / "episodes")
    return {
        "version": RESULT_VERSION,
        "tier": config.tier,
        "language": config.language,
        "findings": [_finding(comment, store) for comment in result.comments],
        "dropped": len(result.filtered or []),
        "usage": result.usage.model_dump(),
        "duration_s": round(time.monotonic() - started, 1),
        "errors": result.errors,
    }


def _finding(comment, store) -> dict:
    """A comment with the fields of the finding it came from."""
    source = {}
    episode = store.load(comment.provenance.get("episode_id", ""))
    if episode is not None:
        source = next((f for f in episode.findings
                       if f.get("id") == comment.provenance.get("finding_id")), {})
    final = comment.provenance.get("final", {})
    return {
        "path": comment.path,
        "side": "old" if comment.side == "base" else "new",
        "start_line": comment.start_line,
        "end_line": comment.end_line,
        "existing_code": source.get("existing_code"),
        "severity": comment.severity,
        "category": comment.category,
        "title": comment.title,
        "body": source.get("description") or comment.content,
        "condition": source.get("condition"),
        "suggestion": source.get("suggestion"),
        "also": [
            {**place, "side": "old" if place["side"] == "base" else "new"}
            for place in final.get("also", [])
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review-agent", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("run", help="review one merge request")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = RunRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
        result = run(request, make_policy(request.model, os.environ.get(API_KEY_ENV)))
        status = 0
    except Exception as exc:  # the host reads the error from the output file
        result = {"version": RESULT_VERSION, "error": f"{type(exc).__name__}: {exc}",
                  "traceback": traceback.format_exc(limit=6)}
        status = 1
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    return status


if __name__ == "__main__":
    sys.exit(main())
