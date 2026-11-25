"""Review environments, shaped like rLLM's BaseEnv so they plug into RL trainers:

    env = InvestigateEnv.from_dict(task)      # a task is plain JSON data
    messages, info = env.reset()              # initial context
    observations, reward, done, info = env.step(assistant_message)

The environment owns tools, findings and the budget meter; the loop owns the model and
the context window. Rewards are 0 during the episode; graders score findings afterwards.
Each call is first put in its canonical form (normalize); intel tool calls are dispatched
here, the agent tools go to the finding ledger (ledger), with the coverage check (coverage)
and the budget meter (budget) as optional parts; the meter draws on the case pool when one
is given, and close() leaves it.
When the budget is used up the loop calls wrap_up: from then on no code is read, only the
agent tools (reporting, candidates, finish) run.
"""

from __future__ import annotations

import contextlib
import json
import threading

from pydantic import ValidationError

from review_core.intel.render import SHORT_ID
from review_core.intel.tools import SPECS, Tools, drop_empty

from . import prompts, repair
from .agent_tools import AGENT_TOOLS, validation_message
from .budget import BudgetMeter, CasePool
from .coverage import CoverageCheck
from .findings import Anchorer, Finding
from .ledger import FindingLedger
from .normalize import normalize
from .policy import Usage
from .schemas import tool_schema
from .versions import AGENT_TOOLS_VERSION, PROMPT_VERSION


class ReviewEnv:
    role = "base"
    # recorded on the episode by run_episode
    prompt_version = PROMPT_VERSION
    tools_version = AGENT_TOOLS_VERSION

    def reset(self) -> tuple[list[dict], dict]:
        raise NotImplementedError

    def step(self, action: dict) -> tuple[list[dict], float, bool, dict]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    @staticmethod
    def is_multithread_safe() -> bool:
        return False

    @classmethod
    def from_dict(cls, info: dict) -> ReviewEnv:
        raise NotImplementedError


class InvestigateEnv(ReviewEnv):
    role = "investigator"

    def __init__(
        self,
        intel,
        plan,
        cluster: str,
        budget_tokens: int | None,
        *,
        lock: threading.Lock | None = None,
        max_output_tokens: int = 6000,
        task: dict | None = None,
        examples: tuple | None = None,
        coverage: bool = False,
        seed_candidates: list[dict] | None = None,
        prompt: str = "standard",
        reporting: str = "coverage",
        language: str = "en",
        pool: CasePool | None = None,
    ):
        self.prompt = prompt  # the investigator variant (prompts.VARIANTS)
        self.reporting = reporting  # what it reports (prompts.MERGE_BLOCKING)
        self.language = language  # what language findings are written in
        self.examples = examples  # (ExampleIndex, mode) or None
        # coverage: every unit needs a candidate, a finding or a "reviewed" mark
        self.coverage = coverage
        # candidates from earlier sampling passes, recorded before the episode starts
        self.seed_candidates = seed_candidates or []
        self.intel = intel
        self.plan = plan
        self.cluster = plan.cluster(cluster)
        self.budget_tokens = budget_tokens
        self.pool = pool  # in place of budget_tokens: the case budget shared by its episodes
        self.lock = lock or contextlib.nullcontext()
        self.tools = Tools(intel, plan, max_output_tokens=max_output_tokens)
        self.anchorer = Anchorer(intel.workspace)
        self.task = task or {
            "snapshot_id": intel.workspace.snapshot.id,
            "plan_id": plan.id,
            "cluster": self.cluster.handle,
            "budget_tokens": budget_tokens,
        }
        self.reset_state()

    def close(self) -> None:
        if self.pool is not None:
            self.pool.leave(self.cluster.handle)

    @classmethod
    def from_dict(cls, info: dict) -> InvestigateEnv:
        from pathlib import Path

        from review_core.intel import CodeIntel
        from review_core.triage import Triage
        from review_core.workspace import Workspace

        intel = CodeIntel(Workspace.load(Path(info["state_dir"]), info["snapshot_id"]))
        plan = Triage(intel).load(info["plan_id"])
        return cls(intel, plan, info["cluster"], info["budget_tokens"], task=dict(info))

    # -- episode state ------------------------------------------------------------------

    def reset_state(self) -> None:
        self.units_read: set[str] = set()
        self.examples_shown: list = []
        if self.pool is not None:
            self.budget = self.pool.meter(self.cluster.handle)
        else:
            self.budget = BudgetMeter(self.budget_tokens)
        self.reporting_only = False  # after wrap_up: no intel tool runs
        self.done = False
        self.summary: dict | None = None
        self.step_index = 0
        self.paths: set[str] | None = None  # both revisions' files, read when needed
        with self.lock:
            units = {unit.id: unit for unit in self.intel.changed_symbols()}
        self.units = units
        handles = [self.plan.unit_handles[key] for key in self.cluster.unit_ids]
        self.book = FindingLedger(
            self.intel.workspace, self.plan, self.cluster, units, self.anchorer, self.lock,
            coverage=CoverageCheck(handles) if self.coverage else None,
        )
        self.book.seed(getattr(self, "seed_candidates", []))

    @property
    def prompt_version(self) -> str:
        return prompts.prompt_version(self.prompt, self.reporting, self.language)

    @property
    def findings(self) -> list[Finding]:
        return self.book.findings

    @property
    def candidates(self) -> list[dict]:
        return self.book.candidates

    def candidates_line(self) -> str:
        return self.book.candidates_line()

    def _agent_tools(self) -> dict:
        if self.book.coverage is None:
            return AGENT_TOOLS
        return self.book.coverage.tools(AGENT_TOOLS)

    def tool_models(self) -> dict:
        """The argument models of the tools tool_schemas offers, by name."""
        models = {name: spec[0] for name, spec in SPECS.items()}
        models |= {name: spec[0] for name, spec in self._agent_tools().items()}
        names = [schema["function"]["name"] for schema in self.tool_schemas()]
        return {name: models[name] for name in names}

    def _files(self) -> set[str]:
        if self.paths is None:
            with self.lock:
                workspace = self.intel.workspace
                self.paths = set(workspace.tree("head")) | set(workspace.tree("base"))
        return self.paths

    def tool_schemas(self) -> list[dict]:
        core = [
            tool_schema(name, model, description) for name, (model, _, _, description) in SPECS.items()
        ]
        return core + [
            tool_schema(name, model, description)
            for name, (model, description) in self._agent_tools().items()
        ]

    def reset(self) -> tuple[list[dict], dict]:
        self.reset_state()
        with self.lock:
            brief = self.intel_brief()
        first = prompts.first_message(brief, self.cluster.handle, self.prompt)
        if self.candidates:
            first = prompts.seeded_message(brief, self.cluster.handle, self.candidates_line())
        messages = [
            {"role": "system",
             "content": prompts.system_prompt(self.prompt, self.reporting, self.language)},
            {"role": "user", "content": first},
        ]
        return messages, {"task": self.task}

    def intel_brief(self) -> str:
        from review_core.triage.brief import render

        # the budget is not shown: the loop reminds the model when it runs low
        return render(self.plan, self.cluster.handle, self.units, show_budget=False)

    # -- budget meter (the loop's interface) --------------------------------------------

    def charge(self, usage: Usage) -> None:
        self.budget.charge(usage)

    def wrap_up(self) -> None:
        """The budget is used up: from now on no code is read."""
        self.reporting_only = True

    def ledger(self) -> str:
        """Deterministic progress note, added when old observations are masked."""
        handles = [self.plan.unit_handles[key] for key in self.cluster.unit_ids]
        unread = [handle for handle in handles if handle not in self.units_read]
        lines = ["Progress so far (earlier tool outputs were elided to save context):"]
        active = [finding for finding in self.findings if not finding.withdrawn]
        if active:
            lines.append("Findings reported:")
            lines += [f"  {f.id} {f.path}:{f.start_line} [{f.severity}] {f.title}" for f in active]
        else:
            lines.append("No findings reported yet.")
        lines.append(
            "Units whose diff you have not read: " + (", ".join(unread) if unread else "none")
        )
        lines.append(self.candidates_line())
        if self.book.coverage_line():
            lines.append(self.book.coverage_line())
        return "\n".join(lines)

    # -- step ---------------------------------------------------------------------------

    def step(self, action: dict) -> tuple[list[dict], float, bool, dict]:
        """info["tool_calls"]: the calls as dispatched, when normalize rewrote any."""
        observations, records, canonical = [], [], []
        calls = action.get("tool_calls") or []
        models = self.tool_models() if calls else {}
        for call in calls:
            if not self.done:
                ids = {candidate["id"] for candidate in self.candidates}
                call = normalize(call, models, ids, self._files)
            canonical.append(call)
            name = call["function"]["name"]
            raw = call["function"].get("arguments") or "{}"
            record = {"tool_call_id": call["id"], "name": name, "arguments": raw}
            self.book.repairs = []
            if self.done:
                text, error = "Ignored: the review was already finished.", "after finish"
            else:
                try:
                    arguments = repair.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(raw, str) and arguments != _strict(raw):
                        self.book.repairs.append("arguments: lenient JSON")
                    if name == "report_finding":
                        arguments = repair.report_arguments(arguments, self.book.repairs)
                    if not isinstance(arguments, dict):
                        raise ValueError("arguments must be a JSON object")
                    record["arguments"] = arguments
                    text, error, evidence_id = self._dispatch(name, arguments)
                    record["evidence_id"] = evidence_id
                except (ValueError, json.JSONDecodeError) as exc:
                    text, error = f"Error: tool arguments are not valid JSON ({exc}).", str(exc)
            record["error"] = error
            record["repairs"] = list(self.book.repairs)
            records.append(record)
            observations.append({"role": "tool", "tool_call_id": call["id"], "content": text})
        self.step_index += 1
        info = {"observations": records, "findings": len(self.findings)}
        if canonical != calls:
            info["tool_calls"] = canonical
        return observations, 0.0, self.done, info

    def _dispatch(self, name: str, arguments: dict):
        if self.reporting_only and name in SPECS:
            return (
                f"Not run: the budget is used up, so {name} and the other code tools are "
                "disabled. Report with report_finding and call finish.",
                "budget used up",
                None,
            )
        if name in SPECS:
            with self.lock:
                result = self.tools.call(name, **arguments)
            self.book.record_evidence(
                result.evidence_id[:SHORT_ID], result.evidence_id, result.text or ""
            )
            text = result.text
            if name == "read_diff":
                for item in result.items:
                    self.units_read.update(item.get("units") or ())
                if self.examples and not self.examples_shown and not result.error:
                    text = self._with_examples(text)
            return text, result.error, result.evidence_id
        agent_tools = self._agent_tools()
        if name not in agent_tools:
            available = ", ".join([*SPECS, *agent_tools])
            return f"Error: unknown tool {name!r}. Available: {available}.", "unknown tool", None
        model = agent_tools[name][0]
        if name == "report_finding":
            return self.book.report(arguments, self.step_index)
        for key in ("add", "dismiss", "dismissed", "unreviewed", "evidence", "reviewed"):
            if key in arguments:
                arguments[key] = repair.decoded(arguments[key], self.book.repairs, key)
        if name == "update_finding":
            for key, choices, aliases in (
                ("severity", repair.SEVERITIES, repair.SEVERITY_ALIASES),
                ("category", repair.CATEGORIES, repair.CATEGORY_ALIASES),
            ):
                if key in arguments:
                    arguments[key] = repair.enum_value(
                        arguments[key], choices, aliases, self.book.repairs, key
                    )
        if name == "note_candidates" and isinstance(arguments.get("add"), list):
            arguments["add"] = [
                {"concern": item} if isinstance(item, str) else item for item in arguments["add"]
            ]
        arguments = drop_empty(model, arguments)
        try:
            args = model.model_validate(arguments)
        except ValidationError as exc:
            message = validation_message(exc)
            return f"Error: invalid arguments for {name}: {message}", message, None
        if name == "note_candidates":
            return self.book.note(args)
        if name == "update_finding":
            return self.book.update(args, self.step_index)
        result = self.book.finish(args)
        if self.book.summary is not None:
            self.done = True
            self.summary = self.book.summary
        return result

    def _with_examples(self, text: str) -> str:
        from . import examples

        index, mode = self.examples
        units = [self.units[key] for key in self.cluster.unit_ids if key in self.units]
        seed = f"{self.task.get('snapshot_id', '')}:{self.cluster.handle}"
        cards = examples.for_units(index, units, mode=mode, seed=seed)
        self.examples_shown = [card["id"] for card in cards] or [None]
        if not cards:
            return text
        return f"{text}\n\n{examples.INTRO}\n\n{examples.render(cards)}"


def _strict(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
