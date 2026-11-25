"""Working memory for one episode.

L0  every tool output is already capped and paged by review_core (Tools).
L1  the environment keeps a structured ledger (findings, units read, budget); whenever
    older observations are masked, a fresh note from it replaces the previous one at the
    end of the context, so progress is never lost and notes never pile up.
L2  observation masking: when the context passes a threshold, tool outputs outside the
    recent window (at most keep_recent outputs and keep_recent_tokens in all; the latest is
    always kept) are replaced by one-line stubs naming the tool and evidence id. Calls of
    those outputs keep their arguments, except where the note repeats them (report_finding,
    note_candidates) or they failed: these get a JSON stub, a failed call's output too
    however short. This is deterministic, keeps every reading decision intact, and is what
    Lindenbauer et al. (2025, "The Complexity Trap") found to match LLM summarization at
    lower cost.
L3  (not in round 1) LLM compaction as a last resort; until then a full context makes the
    loop ask the model to report and finish.

Masking is applied in batches and is permanent within the episode, so the context only
changes at those points: the prefix stays stable for caching, and training samples split
exactly there (see trajectory.sft_samples).
"""

from __future__ import annotations

import itertools
import json
import re

from review_core.tokens import TokenCounter

from .trajectory import ContextEvent

EVIDENCE = re.compile(r"evidence ([0-9a-f]{12})")
RECORDED = re.compile(r"^(F\d+) recorded at ", re.MULTILINE)
FAILED = re.compile(r"\A(?:Error|ERROR|finding(?: \d+)? rejected)|ERROR: Invalid tool arguments")


class ContextManager:
    def __init__(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        window: int,
        mask_at: float = 0.6,
        full_at: float = 0.85,
        keep_recent: int = 6,
        keep_recent_tokens: int = 8000,
        min_masked_tokens: int = 80,
        counter: TokenCounter | None = None,
    ):
        if not 0 < mask_at < full_at <= 1:
            raise ValueError("Context thresholds need 0 < mask_at < full_at <= 1")
        self.messages = list(messages)
        self.window = window
        self.mask_at = mask_at
        self.full_at = full_at
        self.keep_recent = keep_recent
        self.keep_recent_tokens = keep_recent_tokens
        self.min_masked_tokens = min_masked_tokens
        self.counter = counter or TokenCounter("cl100k_base")
        self.tools_tokens = self.counter.count(json.dumps(tools, ensure_ascii=False))
        self.names: dict[str, str] = {}  # tool_call_id -> tool name
        # Message state is keyed by the order of appending, not by position: positions
        # shift when the progress note is replaced.
        self._order = itertools.count()
        self._keys: list[int] = [next(self._order) for _ in self.messages]
        self._sizes: list[int] = [self._size(message) for message in self.messages]
        self.masked: set[int] = set()  # outputs replaced by stubs
        self.failed: set[int] = set()  # outputs of failed calls
        # output -> (its assistant message, the call's position there, its stub arguments)
        self.stale: dict[int, tuple[int, int, str]] = {}
        self.note: int | None = None  # the progress note

    def _size(self, message: dict) -> int:
        size = 4 + self.counter.count(message.get("content") or "")
        for call in message.get("tool_calls") or []:
            function = call["function"]
            size += 8 + self.counter.count(function["name"] + function.get("arguments", ""))
        return size

    @property
    def tokens(self) -> int:
        return self.tools_tokens + sum(self._sizes)

    def append(self, message: dict) -> None:
        for call in message.get("tool_calls") or []:
            self.names[call["id"]] = call["function"]["name"]
        key = next(self._order)
        if message.get("role") == "tool":
            self._classify(key, message)
        self.messages.append(message)
        self._keys.append(key)
        self._sizes.append(self._size(message))

    def _classify(self, key: int, message: dict) -> None:
        """How the call of a new output is stubbed once the output leaves the window; the
        finding ids are taken now, before the output is masked."""
        call_id = message.get("tool_call_id")
        name = self.names.get(call_id)
        text = message.get("content") or ""
        reported = RECORDED.findall(text) if name == "report_finding" else []
        if reported:
            stub = {"elided": f"reported {', '.join(reported)}; see the progress note"}
        elif FAILED.search(text):
            self.failed.add(key)
            stub = {"elided": "failed call"}
        elif name == "note_candidates":
            stub = {"elided": "candidates noted; see the progress note"}
        else:
            return
        for owner, previous in zip(reversed(self._keys), reversed(self.messages), strict=True):
            ids = [call["id"] for call in previous.get("tool_calls") or []]
            if call_id in ids:
                self.stale[key] = (owner, ids.index(call_id), json.dumps(stub))
                return

    def prepare(self, ledger) -> tuple[list[dict], list[ContextEvent], bool]:
        """The request context for the next call; masks if needed. Returns (messages,
        events, full) where full means masking could not bring it under full_at. A mask
        event's positions (masked outputs, assistant messages with stubbed calls) are those
        in the returned context, i.e. in the request of the step it precedes."""
        events: list[ContextEvent] = []
        if self.tokens > self.mask_at * self.window:
            before = self.tokens
            masked = self._mask()
            if masked:
                self.append({"role": "user", "content": ledger()})
                self.note = self._keys[-1]
                outputs, calls = masked
                events.append(
                    ContextEvent(
                        kind="mask",
                        detail={
                            "messages": outputs,
                            "calls": calls,
                            "tokens_before": before,
                            "after": self.tokens,
                        },
                    )
                )
                events.append(ContextEvent(kind="state", detail={"tokens": self._sizes[-1]}))
        return list(self.messages), events, self.tokens > self.full_at * self.window

    def _recent(self, outputs: list[int]) -> set[int]:
        """Positions of the kept window: the latest outputs, at most keep_recent of them and
        keep_recent_tokens in all; the latest is always kept."""
        kept: set[int] = set()
        total = 0
        for index in reversed(outputs):
            total += self._sizes[index]
            if kept and (len(kept) >= self.keep_recent or total > self.keep_recent_tokens):
                break
            kept.add(index)
        return kept

    def _mask(self) -> tuple[list[int], list[int]] | None:
        """Masks what left the window and drops the previous note; None if nothing changed."""
        outputs = [i for i, message in enumerate(self.messages) if message.get("role") == "tool"]
        recent = self._recent(outputs)
        old = [i for i in outputs if i not in recent]
        masked = [
            self._keys[i]
            for i in old
            if self._keys[i] not in self.masked
            and (self._keys[i] in self.failed or self._sizes[i] >= self.min_masked_tokens)
        ]
        calls: dict[int, dict[int, str]] = {}
        for key in (self._keys[i] for i in old if self._keys[i] in self.stale):
            owner, number, arguments = self.stale.pop(key)
            calls.setdefault(owner, {})[number] = arguments
        if not masked and not calls:
            return None
        if self.note is not None:
            index = self._keys.index(self.note)
            del self.messages[index], self._sizes[index], self._keys[index]
        position = {key: index for index, key in enumerate(self._keys)}
        for key in masked:
            index = position[key]
            self._replace(index, {**self.messages[index], "content": self._stub(key, index)})
            self.masked.add(key)
        for owner, stubs in calls.items():
            index = position[owner]
            message = self.messages[index]
            tool_calls = [
                {**call, "function": {**call["function"], "arguments": stubs[number]}}
                if number in stubs
                else call
                for number, call in enumerate(message["tool_calls"])
            ]
            self._replace(index, {**message, "tool_calls": tool_calls})
        return sorted(position[key] for key in masked), sorted(position[key] for key in calls)

    def _stub(self, key: int, index: int) -> str:
        message = self.messages[index]
        name = self.names.get(message.get("tool_call_id"), "tool")
        if key in self.failed:
            return f"[earlier failed {name} call elided]"
        found = EVIDENCE.findall(message.get("content") or "")
        reference = f"; evidence {found[-1]}" if found else ""
        return (
            f"[earlier {name} output elided to save context{reference}; "
            "call the tool again if you need it]"
        )

    def _replace(self, index: int, message: dict) -> None:
        self.messages[index] = message
        self._sizes[index] = self._size(message)
