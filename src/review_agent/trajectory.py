"""Episode records: exactly what the model saw and did, step by step.

A step stores its request as a list of message hashes into the episode's message table,
so a long episode is not stored quadratically, and the request is reproduced exactly
(including masked observations) when replaying or exporting training data.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_serializer

from review_core.common import stable_id

from .policy import Usage, request_hash
from .versions import SCHEMA_VERSION

# Response fields recorded for training and never sent back as such (see Step.message).
PRIVATE_KEYS = frozenset({"reasoning_content"})
Termination = Literal["finished", "budget", "context", "max_steps", "no_action", "error"]


class ContextEvent(BaseModel):
    kind: Literal["mask", "state", "nudge", "wrap_up", "milestone"]
    detail: dict = Field(default_factory=dict)


class Observation(BaseModel):
    tool_call_id: str
    name: str
    arguments: dict | str
    error: str | None = None
    evidence_id: str | None = None
    # deterministic fixes applied to the arguments before they were used (see repair)
    repairs: list[str] = Field(default_factory=list)


class Step(BaseModel):
    index: int
    request_hash: str
    request: list[str]
    response: dict  # what the model produced, as it came (replays serve it)
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    model: str | None = None
    latency_s: float = 0.0
    observations: list[Observation] = Field(default_factory=list)
    # Context changes made before this step's request (masking, state notes, nudges).
    events: list[ContextEvent] = Field(default_factory=list)
    # the response's tool calls as dispatched, when normalize rewrote any (else None)
    canonical_calls: list[dict] | None = None

    def message(self, reasoning: Literal["drop", "keep", "private"] = "drop") -> dict:
        """The response as later requests show it, with the canonical calls. reasoning: as
        the episode's reasoning_history (keep: in the content, as the chat template renders
        earlier turns), or private: as recorded, in its own field."""
        message = {k: v for k, v in self.response.items()
                   if reasoning == "private" or k not in PRIVATE_KEYS}
        thought = self.response.get("reasoning_content")
        if reasoning == "keep" and thought:
            content = message.get("content") or ""
            message["content"] = f"<think>\n{thought}\n</think>\n\n{content}"
        if self.canonical_calls is not None:
            message["tool_calls"] = self.canonical_calls
        return message


class Episode(BaseModel):
    schema_version: str = SCHEMA_VERSION
    id: str
    role: str
    task: dict
    policy: dict
    prompt_version: str
    tools_version: str
    # the loop's context management (versions.CONTEXT_VERSION); older records lack it
    context_version: str = "context-v1"
    tools: list[dict]
    budget_tokens: int | None  # None: unmetered, or the case pool (task budget_pool)
    context_window: int
    # what later requests showed of earlier reasoning (LoopConfig); older records lack it
    reasoning_history: Literal["drop", "keep"] = "drop"
    messages: dict[str, dict] = Field(default_factory=dict)
    steps: list[Step] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)  # the environment's candidate list
    termination: Termination | None = None
    error: str | None = None
    usage: Usage = Field(default_factory=Usage)
    started_at: str = ""
    ended_at: str = ""
    # Filled offline by a grader (e.g. AACR judge hits per finding); see review_bench.
    grades: list[dict] = Field(default_factory=list)
    reward: float | None = None

    @model_serializer(mode="wrap")
    def _dump(self, handler):
        data = handler(self)
        if self.reasoning_history == "drop":  # records stay those from before the field
            data.pop("reasoning_history", None)
        return data

    @property
    def tools_hash(self) -> str:
        return stable_id(self.tools)

    def intern(self, message: dict) -> str:
        key = stable_id(message)
        self.messages.setdefault(key, message)
        return key

    def add_step(self, request: list[dict], response, events: list[ContextEvent]) -> Step:
        step = Step(
            index=len(self.steps),
            request_hash=request_hash(request, self.tools),
            request=[self.intern(message) for message in request],
            response=response.message,
            usage=response.usage,
            finish_reason=response.finish_reason,
            model=response.model,
            latency_s=response.latency_s,
            events=list(events),
        )
        self.intern(response.message)
        self.steps.append(step)
        self.usage = self.usage + response.usage
        return step

    def request_messages(self, step: Step) -> list[dict]:
        return [self.messages[key] for key in step.request]

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.id}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(self.model_dump_json(), encoding="utf-8")
        temporary.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> Episode:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def content(self) -> dict:
        """The episode without wall-clock fields, for determinism checks."""
        data = self.model_dump(mode="json", exclude={"started_at", "ended_at"})
        for step in data["steps"]:
            step.pop("latency_s", None)
        return data


class EpisodeStore:
    """Episodes kept by their deterministic id, so a resumed run loads a finished episode
    instead of paying for it again. Episodes that ended in an error are not kept (they are
    retried). directory None: nothing is loaded or kept."""

    def __init__(self, directory: Path | None):
        self.directory = directory

    def load(self, identifier: str) -> Episode | None:
        if self.directory is None:
            return None
        path = self.directory / f"{identifier}.json"
        return Episode.load(path) if path.is_file() else None

    def save(self, episode: Episode) -> None:
        if self.directory is not None and episode.termination != "error":
            episode.save(self.directory)

    def load_or_run(self, identifier: str, run: Callable[[], Episode]) -> Episode:
        episode = self.load(identifier)
        if episode is None:
            episode = run()
            self.save(episode)
        return episode


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sft_samples(episode: Episode, metadata: dict | None = None) -> list[dict]:
    """OpenAI fine-tuning format; one sample per run of steps whose context only grew.

    Masking rewrites earlier observations, so the context of a later step is not an
    extension of an earlier one; a new sample starts there. Assistant turns produced in a
    sample's own steps get weight 1, assistant turns it merely inherits get weight 0, so
    each model decision is trained exactly once, on exactly the context it was made in.
    Kept reasoning is trained as later requests show it, so training and inference agree.
    """
    shown = episode.reasoning_history
    trained = "private" if shown == "drop" else shown
    samples = []
    start = 0
    steps = episode.steps
    for index, step in enumerate(steps):
        # What later requests contain: the response as the episode showed it.
        full = [*step.request, episode.intern(step.message(shown))]
        following = steps[index + 1] if index + 1 < len(steps) else None
        if following is not None and following.request[: len(full)] == full:
            continue
        # Each step's own turn is trained with what the model produced, its calls canonical.
        produced = {len(item.request): item.message(trained) for item in steps[start : index + 1]}
        messages = []
        for position, key in enumerate(full):
            message = dict(produced.get(position) or episode.messages[key])
            if message.get("role") == "assistant":
                message["weight"] = 1 if position in produced else 0
            messages.append(message)
        samples.append(
            {
                "messages": messages,
                "tools": episode.tools,
                "metadata": {
                    "episode_id": episode.id,
                    "steps": [start, index],
                    "role": episode.role,
                    "prompt_version": episode.prompt_version,
                    "tools_version": episode.tools_version,
                    "context_version": episode.context_version,
                    "policy": episode.policy.get("model"),
                    "termination": episode.termination,
                    "reward": episode.reward,
                    **({"reasoning_history": shown} if shown != "drop" else {}),
                    **(metadata or {}),
                },
            }
        )
        start = index + 1
    return samples


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count
