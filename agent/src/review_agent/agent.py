"""The ReAct loop: one role, one episode, one model, tools from the environment.

Kept deliberately plain (cf. mini-swe-agent): request -> response -> tool observations,
repeated until finish, budget, context or step limits. Everything the model saw is
recorded in the Episode, so the same loop serves evaluation, replay and RL rollouts; the
model's calls are shown back as the environment dispatched them (env.step, normalize).

Limits end an episode gracefully: reminders before the step limit (milestones) and when
the token budget runs low, and wrap-up turns when the budget is used up or the context is
full. A budget wrap-up reads no more code, and its episode ends as "budget" however it
ends; findings reported before are always kept. Both budget events record what the meter
decided on (a shared case pool's state, see budget).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from review_core.common import stable_id
from review_core.tokens import TokenCounter

from . import prompts
from .context import ContextManager
from .policy import ModelRequest, Policy, PolicyError, Usage
from .trajectory import ContextEvent, Episode, Observation, now
from .versions import CONTEXT_VERSION


class LoopConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_window: int = Field(default=64000, ge=4000)
    mask_at: float = 0.6
    full_at: float = 0.85
    keep_recent: int = 6
    keep_recent_tokens: int = 8000
    max_steps: int = Field(default=60, ge=1)
    max_nudges: int = 2
    wrap_up_turns: int = 2
    max_output_tokens: int | None = None
    temperature: float | None = None
    # turns left at which the model is reminded to converge (60 steps: after 30, 45, 55,
    # 58 and 59 turns)
    milestones: list[int] = Field(default_factory=lambda: [30, 15, 5, 2, 1])
    # earlier reasoning in later requests: dropped, or kept as the chat template shows it
    reasoning_history: Literal["drop", "keep"] = "drop"

    @model_serializer(mode="wrap")
    def _dump(self, handler):
        data = handler(self)
        if self.reasoning_history == "drop":  # dumps stay those of configs before the field
            data.pop("reasoning_history", None)
        return data


def _text(message: dict) -> str:
    calls = message.get("tool_calls") or []
    return (message.get("content") or "") + "".join(
        call["function"]["name"] + call["function"].get("arguments", "") for call in calls
    )


def _estimate(counter: TokenCounter, request: list[dict], message: dict) -> Usage:
    return Usage(
        input_tokens=sum(counter.count(_text(m)) + 4 for m in request),
        output_tokens=counter.count(_text(message)),
    )


def _candidates(env) -> str:
    return env.candidates_line() if hasattr(env, "candidates_line") else ""


def run_episode(env, policy: Policy, config: LoopConfig, *, episode_id: str | None = None):
    if config.reasoning_history == "keep" and policy.describe().get("kind") == "responses":
        raise ValueError("reasoning_history keep needs a chat policy: the Responses API takes "
                         "earlier reasoning as reasoning items, not in the content")
    messages, info = env.reset()
    tools = env.tool_schemas()
    episode = Episode(
        id=episode_id or uuid.uuid4().hex,
        role=env.role,
        task=info.get("task", {}),
        policy=policy.describe(),
        prompt_version=env.prompt_version,
        tools_version=env.tools_version,
        context_version=CONTEXT_VERSION,
        tools=tools,
        budget_tokens=env.budget_tokens,
        context_window=config.context_window,
        reasoning_history=config.reasoning_history,
        started_at=now(),
    )
    context = ContextManager(
        messages,
        tools,
        window=config.context_window,
        mask_at=config.mask_at,
        full_at=config.full_at,
        keep_recent=config.keep_recent,
        keep_recent_tokens=config.keep_recent_tokens,
    )
    counter = context.counter
    pending: list[ContextEvent] = []
    nudges = 0
    wrap_up_left: int | None = None
    stop_reason = None
    termination = "max_steps"
    warned = False  # the budget-low reminder is shown once
    for index in range(config.max_steps):
        if wrap_up_left == 0:
            termination = stop_reason
            break
        left = config.max_steps - index
        if index and wrap_up_left is None:
            budget, reminder = env.budget.state(), None
            if budget == "out":
                reminder = prompts.budget_final(_candidates(env))
                detail = {"reason": "budget", **env.budget.detail()}
                pending.append(ContextEvent(kind="wrap_up", detail=detail))
                env.wrap_up()
                wrap_up_left, stop_reason = config.wrap_up_turns, "budget"
            elif budget == "low" and not warned and left > 2:  # else the last-turns milestone
                warned, meter = True, env.budget
                reminder = prompts.budget_low(meter.left, meter.turns_left(), _candidates(env))
                detail = {"tokens_left": meter.left, **meter.detail()}
                pending.append(ContextEvent(kind="milestone", detail=detail))
            elif left in config.milestones:
                reminder = prompts.milestone(left, config.max_steps, _candidates(env))
                pending.append(ContextEvent(kind="milestone", detail={"turns_left": left}))
            if reminder:
                context.append({"role": "user", "content": reminder})
        view, events, full = context.prepare(env.ledger)
        pending += events
        if full and wrap_up_left is None:
            context.append({"role": "user", "content": prompts.CONTEXT_WRAP_UP})
            pending.append(ContextEvent(kind="wrap_up", detail={"reason": "context"}))
            wrap_up_left, stop_reason = config.wrap_up_turns, "context"
            view = list(context.messages)
        request = ModelRequest(
            messages=tuple(view),
            tools=tuple(tools),
            max_output_tokens=config.max_output_tokens,
            temperature=config.temperature,
        )
        try:
            response = policy.complete(request)
        except PolicyError as exc:
            termination, episode.error = "error", str(exc)
            break
        if response.usage.total == 0:
            response = response.model_copy(
                update={"usage": _estimate(counter, view, response.message)}
            )
        step = episode.add_step(view, response, pending)
        pending = []
        env.charge(response.usage)
        if wrap_up_left is not None:
            wrap_up_left -= 1
        if not response.message.get("tool_calls"):
            context.append(step.message(config.reasoning_history))
            nudges += 1
            if nudges > config.max_nudges:
                termination = "no_action"
                break
            context.append({"role": "user", "content": prompts.NUDGE})
            pending.append(ContextEvent(kind="nudge"))
            continue
        nudges = 0
        try:
            observations, _, done, info = env.step(response.message)
        except Exception as exc:  # an environment bug ends this episode, not the review
            termination, episode.error = "error", f"{type(exc).__name__}: {exc}"
            break
        step.observations = [Observation(**record) for record in info["observations"]]
        step.canonical_calls = info.get("tool_calls")
        # Earlier reasoning is dropped or kept (reasoning_history); the calls are shown as
        # dispatched (normalize).
        context.append(step.message(config.reasoning_history))
        for observation in observations:
            context.append(observation)
        if done:
            termination = "finished"
            break
    else:
        termination = stop_reason or "max_steps"
    if stop_reason == "budget" and termination != "error":
        termination = "budget"
    episode.termination = termination
    episode.findings = [finding.model_dump(mode="json") for finding in env.findings]
    episode.candidates = [dict(c) for c in getattr(env, "candidates", [])]
    episode.ended_at = now()
    return episode


def episode_id_for(run_id: str, case: str, cluster: str, attempt: int = 0) -> str:
    return stable_id({"run": run_id, "case": case, "cluster": cluster, "attempt": attempt})[:24]
