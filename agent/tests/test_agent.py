from __future__ import annotations

import copy
import json
import re

import pytest

from review_agent import tiers
from review_agent.agent import LoopConfig, run_episode
from review_agent.aggregate import AggregateConfig, dedupe, order, select
from review_agent.config import ReviewConfig
from review_agent.env import InvestigateEnv
from review_agent.orchestrator import review
from review_agent.policy import GatedPolicy, ModelRequest, ReplayPolicy, ScriptedPolicy, Usage
from review_agent.trajectory import Episode, sft_samples
from review_core.triage import Triage

EVIDENCE = re.compile(r"evidence ([0-9a-f]{12})")


@pytest.fixture(autouse=True)
def coverage_tiers(monkeypatch):
    """These tests cover the agent's mechanics with every concern reported and no final
    review; merge-blocking reporting and the final review are covered in test_product."""
    for name in ("low", "high"):
        preset = copy.deepcopy(tiers.TIERS[name])
        preset["investigate"].pop("reporting", None)
        preset.get("postprocess", {}).pop("final_review", None)
        monkeypatch.setitem(tiers.TIERS, name, preset)


def call(name, arguments, index=0):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"c{index}_{name}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def last_evidence(request):
    for message in reversed(request.messages):
        if message.get("role") == "tool":
            found = EVIDENCE.findall(message["content"])
            if found:
                return found[-1]
    return "000000000000"


def finding(evidence, **extra):
    return {
        "path": "api.py",
        "existing_code": '+L4     return fetch(id)["name"].upper()',
        "title": "api() crashes when get_user returns None",
        "description": "get_user now returns None for a None id; subscripting it raises.",
        "category": "defect",
        "severity": "major",
        "evidence": [evidence],
        **extra,
    }


@pytest.fixture
def planned(reviewed):
    _, workspace, intel = reviewed
    plan = Triage(intel).plan()
    return intel, plan


def standard_script(request):
    turn = sum(1 for m in request.messages if m["role"] == "assistant")
    if turn == 0:
        return call("read_diff", {"cluster": "C1"}, turn)
    if turn == 1:
        return call("report_finding", {"findings": [finding(last_evidence(request))]}, turn)
    return call("finish", {"summary": "reviewed C1"}, turn)


def test_episode_reports_anchored_finding_and_replays_identically(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", 50000)
    policy = ScriptedPolicy(standard_script, usage=lambda r, m: Usage(input_tokens=100))
    episode = run_episode(env, policy, LoopConfig(), episode_id="e1")
    assert episode.termination == "finished"
    assert len(episode.steps) == 3
    (found,) = episode.findings
    assert (found["path"], found["side"], found["start_line"], found["end_line"]) == (
        "api.py",
        "head",
        4,
        4,
    )
    assert found["in_diff"] and found["unit"] == "U1" and found["cluster"] == "C1"
    assert episode.usage.input_tokens == 300
    # The request is stored exactly: system + user, then each response and observation.
    first = episode.request_messages(episode.steps[0])
    assert [m["role"] for m in first] == ["system", "user"]
    # the budget is not shown until it runs low
    second = episode.request_messages(episode.steps[1])
    assert not any("budget" in (m.get("content") or "").lower() for m in second)
    # Replay against a fresh environment reproduces the episode exactly.
    replayed = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000),
        ReplayPolicy(episode),
        LoopConfig(),
        episode_id="e1",
    )
    original, again = episode.content(), replayed.content()
    original.pop("policy"), again.pop("policy")
    assert original == again
    # One SFT sample (the context only grew); every assistant turn trained once.
    (sample,) = sft_samples(episode)
    weights = [m["weight"] for m in sample["messages"] if m["role"] == "assistant"]
    assert weights == [1, 1, 1]
    assert sample["tools"] == episode.tools


def test_save_load_round_trip(planned, tmp_path):
    intel, plan = planned
    episode = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ScriptedPolicy(standard_script), LoopConfig()
    )
    loaded = Episode.load(episode.save(tmp_path))
    assert loaded.content() == episode.content()


def test_invalid_actions_become_observations(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", 50000)
    env.reset()
    bad_json = {
        "role": "assistant",
        "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "read_diff", "arguments": "{"}}
        ],
    }
    (observation,), _, done, info = env.step(bad_json)
    assert "not valid JSON" in observation["content"] and not done
    (observation,), *_ = env.step(call("nope", {}))
    assert "unknown tool" in observation["content"]
    (observation,), *_ = env.step(call("report_finding", {"findings": [finding("deadbeef0000")]}))
    assert "rejected" in observation["content"] and not env.findings
    (observation,), *_ = env.step(call("read_diff", {"cluster": "C1"}))
    evidence = EVIDENCE.findall(observation["content"])[-1]
    missing = finding(evidence, existing_code="not in the code at all")
    (observation,), *_ = env.step(call("report_finding", {"findings": [missing]}))
    assert "was not found" in observation["content"]
    # A finding on removed code is rejected unless the removal itself is the problem.
    removed = finding(evidence, existing_code='-L4     return fetch(id)["name"]')
    (observation,), *_ = env.step(call("report_finding", {"findings": [removed]}))
    assert "removed code" in observation["content"] and not env.findings
    # A single finding passed flat is accepted; the base side is found for deleted lines.
    flat = finding(evidence, existing_code='-L4     return fetch(id)["name"]', about_removal=True)
    (observation,), *_ = env.step(call("report_finding", flat))
    assert "F1 recorded at api.py:L4 (base; in diff; U1)" in observation["content"]
    assert env.findings[0].about_removal
    (observation,), *_ = env.step(call("update_finding", {"id": "F1", "severity": "minor"}))
    assert env.findings[0].severity == "minor"
    (observation,), *_ = env.step(call("update_finding", {"id": "F1", "withdraw": True}))
    assert env.findings[0].withdrawn
    (observation,), *_ = env.step(call("update_finding", {"id": "F9"}))
    assert "no finding F9" in observation["content"]
    _, _, done, _ = env.step(call("finish", {"summary": "done"}))
    assert done
    (observation,), *_ = env.step(call("read_diff", {}))
    assert "already finished" in observation["content"]


def wander(request):
    turn = sum(1 for m in request.messages if m["role"] == "assistant")
    return call("read_file", {"path": "users.py"}, turn)


def test_budget_runs_low_then_wraps_up_with_reporting_only(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", 5000)
    policy = ScriptedPolicy(wander, usage=lambda r, m: Usage(input_tokens=400, output_tokens=100))
    episode = run_episode(env, policy, LoopConfig())
    assert episode.termination == "budget"
    # 500 tokens a turn: low after 7 turns (3 turns left), out after 9 (the 10th would pass)
    marks = [(s.index, e.kind, e.detail) for s in episode.steps for e in s.events
             if e.kind in ("milestone", "wrap_up")]
    assert marks == [(7, "milestone", {"tokens_left": 1500}), (9, "wrap_up", {"reason": "budget"})]
    assert len(episode.steps) == 9 + LoopConfig().wrap_up_turns
    low = episode.request_messages(episode.steps[7])[-1]["content"]
    assert "1500 tokens left" in low and "about 3 more turns" in low and "Stop exploring" in low
    final = episode.request_messages(episode.steps[9])[-1]["content"]
    assert "budget is used up" in final and "report_finding" in final
    # reading code is refused in the wrap-up
    refused = [o for s in episode.steps[9:] for o in s.observations]
    assert refused and all(o.error == "budget used up" for o in refused)
    # with a large budget, 80% comes first
    env = InvestigateEnv(intel, plan, "C1", 50000)
    episode = run_episode(env, policy, LoopConfig(max_steps=90, milestones=[]))
    (low,) = [(s.index, e.detail) for s in episode.steps for e in s.events if e.kind == "milestone"]
    assert low == (80, {"tokens_left": 10000})


def test_budget_wrap_up_keeps_findings_and_ends_as_budget(planned):
    intel, plan = planned

    def script(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn == 0:
            return call("read_diff", {"cluster": "C1"}, turn)
        if "budget is used up" not in request.messages[-1].get("content") or "":
            return call("read_file", {"path": "users.py"}, turn)
        message = call("report_finding", {"findings": [finding(last_evidence(request))]}, turn)
        message["tool_calls"] += call("finish", {"summary": "out of budget"}, turn + 1)["tool_calls"]
        return message

    env = InvestigateEnv(intel, plan, "C1", 2000)
    policy = ScriptedPolicy(script, usage=lambda r, m: Usage(input_tokens=400, output_tokens=100))
    episode = run_episode(env, policy, LoopConfig())
    # the finish came in the wrap-up, so the budget ended the episode
    assert episode.termination == "budget" and len(episode.steps) == 4
    assert len(episode.findings) == 1 and env.summary["summary"] == "out of budget"


def test_budget_never_ends_an_episode_without_its_wrap_up(planned):
    intel, plan = planned
    # one turn takes the whole budget: no warning, the wrap-up comes at once
    policy = ScriptedPolicy(wander, usage=lambda r, m: Usage(input_tokens=6000))
    episode = run_episode(InvestigateEnv(intel, plan, "C1", 5000), policy, LoopConfig())
    kinds = [e.kind for s in episode.steps for e in s.events if e.kind != "mask"]
    assert kinds == ["wrap_up"] and episode.termination == "budget"
    assert len(episode.steps) == 1 + LoopConfig().wrap_up_turns
    # silence (no tool calls) in the wrap-up still ends as budget
    quiet = ScriptedPolicy(lambda r: {"role": "assistant", "content": "hm"} if any(
        "budget is used up" in (m.get("content") or "") for m in r.messages) else wander(r),
        usage=lambda r, m: Usage(input_tokens=6000))
    episode = run_episode(InvestigateEnv(intel, plan, "C1", 5000), quiet, LoopConfig())
    assert episode.termination == "budget"


def test_no_action_nudges_then_stops(planned):
    intel, plan = planned
    policy = ScriptedPolicy(lambda r: {"role": "assistant", "content": "thinking"})
    episode = run_episode(InvestigateEnv(intel, plan, "C1", 50000), policy, LoopConfig())
    assert episode.termination == "no_action"
    assert len(episode.steps) == LoopConfig().max_nudges + 1


def test_masking_keeps_decisions_and_splits_training_samples(repository, tmp_path):
    from review_core.intel import CodeIntel
    from review_core.workspace import Workspace

    body = "".join(f"def helper_{i}(value):\n    return value + {i}\n\n" for i in range(120))
    repository.write("big.py", body)
    base = repository.commit()
    repository.write("big.py", body.replace("return value + 7\n", "return value - 7\n"))
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    plan = Triage(intel).plan()

    def reader(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn < 8:
            start = 1 + 40 * turn
            return call(
                "read_file", {"path": "big.py", "start_line": start, "end_line": start + 39}, turn
            )
        if turn == 8:
            item = {
                "path": "big.py",
                "existing_code": "return value - 7",
                "title": "helper_7 now subtracts",
                "description": "The sign flipped.",
                "category": "defect",
                "severity": "major",
                "evidence": [last_evidence(request)],
            }
            return call("report_finding", {"findings": [item]}, turn)
        return call("finish", {"summary": "done"}, turn)

    config = LoopConfig(context_window=8000, mask_at=0.6, full_at=0.95, keep_recent=2)
    env = InvestigateEnv(intel, plan, "C1", 10**6)
    episode = run_episode(env, ScriptedPolicy(reader), config)
    assert episode.termination == "finished", episode.termination
    assert episode.findings[0]["start_line"] == 23 and episode.findings[0]["in_diff"]
    masks = [e for s in episode.steps for e in s.events if e.kind == "mask"]
    assert masks
    later = episode.request_messages(episode.steps[-1])
    assert any("elided to save context" in (m.get("content") or "") for m in later)
    # one progress note at a time, the latest
    for step in episode.steps:
        request = episode.request_messages(step)
        notes = [m for m in request if (m.get("content") or "").startswith("Progress so far")]
        assert len(notes) <= 1
    assert any("Progress so far" in (m.get("content") or "") for m in later)
    # Reading decisions are never rewritten by masking.
    assistants = [m for m in later if m["role"] == "assistant"]
    assert assistants == [s.response for s in episode.steps[:-1]]
    samples = sft_samples(episode)
    assert len(samples) == len(masks) + 1
    trained = sum(m.get("weight", 0) for s in samples for m in s["messages"])
    assert trained == len(episode.steps)


class Words:
    def count(self, text):
        return len(text.split())


def context(**options):
    from review_agent.context import ContextManager

    settings = {"window": 1000, "mask_at": 0.1, "full_at": 0.9, "keep_recent": 2,
                "min_masked_tokens": 20, "counter": Words()}
    start = [{"role": "system", "content": "system"}, {"role": "user", "content": "task"}]
    return ContextManager(start, [], **{**settings, **options})


def turn(manager, number, *calls):
    """One assistant message with calls (name, arguments, output), then their outputs."""
    message = {"role": "assistant", "content": None, "tool_calls": [
        call(name, arguments, f"{number}_{position}")["tool_calls"][0]
        for position, (name, arguments, _) in enumerate(calls)]}
    manager.append(message)
    for tool_call, (_, _, output) in zip(message["tool_calls"], calls, strict=True):
        manager.append({"role": "tool", "tool_call_id": tool_call["id"], "content": output})
    return message


def numbered_notes():
    counter = iter(range(100))
    return lambda: f"Progress so far {next(counter)}"


def consistent(manager):
    assert manager._sizes == [manager._size(m) for m in manager.messages]
    assert len(manager._keys) == len(manager.messages) == len(set(manager._keys))
    assert manager._keys == sorted(manager._keys)


def test_context_replaces_its_progress_note_and_keeps_its_bookkeeping():
    manager = context()
    ledger = numbered_notes()
    masks = []
    for number in range(8):
        turn(manager, number, ("read_file", {"path": f"f{number}.py"}, "line " * 60))
        if number == 3:
            manager.append({"role": "user", "content": "reminder"})
        view, events, _ = manager.prepare(ledger)
        masks += [(view, e.detail) for e in events if e.kind == "mask"]
        consistent(manager)
    assert len(masks) == 6
    for view, detail in masks:
        notes = [m for m in view if (m["content"] or "").startswith("Progress so far")]
        assert notes == [view[-1]]
        assert detail["messages"] and detail["calls"] == []
        for index in detail["messages"]:  # positions in the context the event produced
            assert view[index]["role"] == "tool"
            assert view[index]["content"].startswith("[earlier read_file output elided")
    assert view[-1]["content"] == "Progress so far 5"
    assert [m["content"] for m in view].count("reminder") == 1
    outputs = [m for m in manager.messages if m["role"] == "tool"]
    assert all("elided" in m["content"] for m in outputs[:-2])
    assert not any("elided" in m["content"] for m in outputs[-2:])
    assert manager.tokens == manager.tools_tokens + sum(manager._sizes)


def arguments_of(view):
    return [json.loads(c["function"]["arguments"]) for m in view for c in m.get("tool_calls") or []]


def test_context_stubs_stale_report_note_and_failed_calls_only_outside_the_window():
    manager = context(keep_recent=3, keep_recent_tokens=10**6)
    big = "line " * 60
    report = {"findings": [finding("0123456789ab")]}
    original = [
        turn(manager, 0, ("report_finding", report, "F1 recorded at api.py:L4 (head).\n"
                          "F2 recorded at api.py:L9 (head).")),
        turn(manager, 1, ("note_candidates", {"add": [{"concern": "x"}]}, "Candidates: 1 open")),
        turn(manager, 2, ("read_file", {"path": "x.py"}, "Error: no file x.py")),
        turn(manager, 3, ("report_finding", report, "finding rejected: invalid arguments")),
        turn(manager, 4, ("report_finding", report, "finding 1 rejected: no evidence\n"
                          "F3 recorded at api.py:L4 (head)."),
             ("read_file", {"path": "a.py"}, big)),
        turn(manager, 5, ("read_file", {"path": "b.py"}, big)),
        turn(manager, 6, ("report_finding", report, "F4 recorded at api.py:L4 (head).")),
        turn(manager, 7, ("code_search", {"query": 1}, "code_search\nERROR: Invalid tool "
                          "arguments: query: not a string")),
    ]
    before = json.loads(json.dumps(original))
    view, events, _ = manager.prepare(numbered_notes())
    consistent(manager)
    stub = {"elided": "failed call"}
    assert arguments_of(view) == [
        {"elided": "reported F1, F2; see the progress note"},
        {"elided": "candidates noted; see the progress note"},
        stub, stub,
        {"elided": "reported F3; see the progress note"}, {"path": "a.py"},  # per call
        {"path": "b.py"}, report, {"query": 1},  # in the window
    ]
    outputs = [m["content"] for m in view if m["role"] == "tool"]
    # failed outputs are stubbed however short; a short successful one is not masked
    assert outputs[:5] == ["F1 recorded at api.py:L4 (head).\nF2 recorded at api.py:L9 (head).",
                           "Candidates: 1 open", "[earlier failed read_file call elided]",
                           "[earlier failed report_finding call elided]",
                           "finding 1 rejected: no evidence\nF3 recorded at api.py:L4 (head)."]
    assert outputs[5].startswith("[earlier read_file output elided")
    assert outputs[6:] == [big, "F4 recorded at api.py:L4 (head).",
                           "code_search\nERROR: Invalid tool arguments: query: not a string"]
    (mask,) = [e.detail for e in events if e.kind == "mask"]
    assert [view[i]["tool_calls"][0]["function"]["name"] for i in mask["calls"]] == [
        "report_finding", "note_candidates", "read_file", "report_finding", "report_finding"]
    assert original == before  # the recorded responses are not touched
    stale = [m for m in view if m["role"] == "assistant"][:5]
    # later masks change only what newly left the window
    for number in range(8, 11):
        turn(manager, number, ("read_file", {"path": f"f{number}.py"}, "line"))
    view, events, _ = manager.prepare(numbered_notes())
    consistent(manager)
    assert [m for m in view if m["role"] == "assistant"][:5] == stale
    assert arguments_of(view)[7:9] == [{"elided": "reported F4; see the progress note"}, stub]
    assert [m["content"] for m in view if m["role"] == "tool"][7:9] == [
        "F4 recorded at api.py:L4 (head).", "[earlier failed code_search call elided]"]


def test_context_window_is_bounded_by_tokens_and_keeps_the_latest_output():
    def kept(sizes, **options):
        manager = context(min_masked_tokens=1, **options)
        for number, words in enumerate(sizes):
            turn(manager, number, ("read_file", {"path": "a.py"}, "x " * words))
        manager.prepare(numbered_notes())
        outputs = [m["content"] for m in manager.messages if m["role"] == "tool"]
        return [len(text.split()) for text in outputs if "elided" not in text]

    # tool outputs count 4 tokens more than their words
    assert kept([30, 30, 30, 50, 300], keep_recent=6, keep_recent_tokens=100) == [300]
    assert kept([30, 30, 30, 20], keep_recent=6, keep_recent_tokens=100) == [30, 30, 20]
    assert kept([30, 30, 30, 20], keep_recent=2, keep_recent_tokens=10**6) == [30, 20]
    assert LoopConfig().keep_recent_tokens == 8000


def test_context_is_untouched_below_the_mask_threshold():
    manager = context(window=10**6)
    appended = [turn(manager, 0, ("report_finding", {}, "Error: findings must be a list")),
                turn(manager, 1, ("note_candidates", {}, "Candidates: none"))]
    snapshot = json.loads(json.dumps(manager.messages))

    def ledger():
        raise AssertionError("no note below the threshold")

    view, events, full = manager.prepare(ledger)
    assert view == snapshot and events == [] and not full
    assert [m for m in view if m["role"] == "assistant"] == appended


def test_episodes_record_their_context_version(planned):
    from review_agent.versions import CONTEXT_VERSION, recorded

    intel, plan = planned
    episode = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ScriptedPolicy(standard_script), LoopConfig()
    )
    assert episode.context_version == CONTEXT_VERSION == recorded()["context"] == "context-v2"
    (sample,) = sft_samples(episode)
    assert sample["metadata"]["context_version"] == "context-v2"
    # records from before context-v2 lack the field
    older = episode.model_dump(mode="json")
    del older["context_version"]
    assert Episode.model_validate(older).context_version == "context-v1"


def test_orchestrated_review_aggregates_and_dedups(planned, tmp_path):
    intel, _ = planned

    def twice(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn == 0:
            return call("read_diff", {"cluster": "C1"}, turn)
        if turn in (1, 2):
            return call("report_finding", {"findings": [finding(last_evidence(request))]}, turn)
        return call("finish", {"summary": "done"}, turn)

    result = review(
        intel,
        ScriptedPolicy(twice),
        ReviewConfig(),
        run_id="r",
        case_id="case",
        out_dir=tmp_path,
    )
    (comment,) = result.comments
    assert comment.start_line == 4 and len(comment.duplicates) == 1
    assert comment.content.startswith("api() crashes")
    assert (tmp_path / "episodes" / f"{result.episodes[0].id}.json").is_file()
    nits = select(
        [(1, Episode.load(tmp_path / "episodes" / f"{result.episodes[0].id}.json"))],
        AggregateConfig(min_severity="critical"),
    )
    assert nits == []


def test_reasoning_is_recorded_but_not_sent_back(planned):
    intel, plan = planned

    def thinker(request):
        message = standard_script(request)
        return {**message, "reasoning_content": "let me think"}

    episode = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ScriptedPolicy(thinker), LoopConfig()
    )
    assert all(step.response["reasoning_content"] == "let me think" for step in episode.steps)
    later = episode.request_messages(episode.steps[-1])
    assert all("reasoning_content" not in m for m in later if m["role"] == "assistant")
    (sample,) = sft_samples(episode)
    assert sample["messages"][-1]["reasoning_content"] == "let me think"



def _thinking(request):
    """standard_script with reasoning on every turn but the report, and text on the first."""
    message = standard_script(request)
    turn = sum(1 for m in request.messages if m["role"] == "assistant")
    if turn == 1:
        return message
    return {**message, "content": "reading" if turn == 0 else None,
            "reasoning_content": f"thought {turn}"}


def _shown(episode, step):
    return [m for m in episode.request_messages(episode.steps[step]) if m["role"] == "assistant"]


def test_earlier_reasoning_is_dropped_by_default(planned):
    intel, plan = planned
    episode = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ScriptedPolicy(_thinking), LoopConfig()
    )
    assert episode.reasoning_history == "drop"
    first, report = _shown(episode, 2)
    assert first["content"] == "reading" and "reasoning_content" not in first
    assert report == episode.steps[1].message()
    # default dumps are those from before the setting
    assert "reasoning_history" not in episode.model_dump(mode="json")
    assert "reasoning_history" not in ReviewConfig().model_dump(mode="json")["investigate"]["loop"]


def test_kept_reasoning_is_shown_in_the_content_and_trained_as_shown(planned):
    intel, plan = planned
    config = LoopConfig(reasoning_history="keep")
    episode = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ScriptedPolicy(_thinking), config
    )
    assert episode.reasoning_history == "keep"
    first, report = _shown(episode, 2)
    assert first["content"] == "<think>\nthought 0\n</think>\n\nreading"
    assert "reasoning_content" not in first and first["tool_calls"]
    assert report == episode.steps[1].message("drop")  # a turn without reasoning: as dropped
    # the context only grew: one sample, its turns trained exactly as later requests show them
    (sample,) = sft_samples(episode)
    trained = [m for m in sample["messages"] if m.get("weight") == 1]
    assert len(trained) == len(episode.steps) == 3
    assert [{k: v for k, v in m.items() if k != "weight"} for m in trained[:2]] == [first, report]
    assert trained[2]["content"] == "<think>\nthought 2\n</think>\n\n"
    assert not any("reasoning_content" in m for m in sample["messages"])
    assert sample["metadata"]["reasoning_history"] == "keep"
    # recorded, and older records without the field were drop episodes
    data = episode.model_dump(mode="json")
    assert Episode.model_validate(data).reasoning_history == "keep"
    del data["reasoning_history"]
    assert Episode.model_validate(data).reasoning_history == "drop"
    assert "reasoning_history" not in sft_samples(Episode.model_validate(data))[0]["metadata"]
    # a replay in the same mode sends the same requests
    replayed = run_episode(
        InvestigateEnv(intel, plan, "C1", 50000), ReplayPolicy(episode), config
    )
    assert [s.request_hash for s in replayed.steps] == [s.request_hash for s in episode.steps]


def test_kept_reasoning_reaches_candidate_sampling_and_needs_a_chat_policy(planned, tmp_path):
    from review_agent.policy import ResponsesPolicy

    intel, plan = planned

    def script(request):
        if not any(t["function"]["name"] == "finish" for t in request.tools):  # listing pass
            turn = sum(1 for m in request.messages if m["role"] == "assistant")
            if turn == 0:
                return {**call("read_diff", {"cluster": "C1"}), "reasoning_content": "list"}
            return call("note_candidates", {"candidates": [
                {"concern": "None result", "priority": "high"}]}, turn)
        return _thinking(request)

    config = ReviewConfig.model_validate({"investigate": {
        "loop": {"reasoning_history": "keep"}, "ideation": {"samples": 1}}})
    assert config.model_dump(mode="json")["investigate"]["loop"]["reasoning_history"] == "keep"
    review(intel, ScriptedPolicy(script), config, run_id="r", case_id="case", out_dir=tmp_path)
    episodes = [Episode.load(p) for p in sorted((tmp_path / "episodes").glob("*.json"))]
    assert {e.role for e in episodes} == {"investigator", "ideation"}
    for episode in episodes:
        assert episode.reasoning_history == "keep"
        assert _shown(episode, 1)[0]["content"].startswith("<think>\n")
    responses = ResponsesPolicy("m", api_base="http://localhost", api_key="k")
    with pytest.raises(ValueError, match="chat policy"):
        run_episode(InvestigateEnv(intel, plan, "C1", None), responses,
                    LoopConfig(reasoning_history="keep"))


def test_responses_wire_format_round_trips_tool_calls():
    from review_agent.policy import to_responses

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        call("read_file", {"path": "a.py"}),
        {"role": "tool", "tool_call_id": "c0_read_file", "content": "text"},
    ]
    tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]
    instructions, items, converted = to_responses(messages, tools)
    assert instructions == "sys"
    assert items[1] == {
        "type": "function_call",
        "call_id": "c0_read_file",
        "name": "read_file",
        "arguments": '{"path": "a.py"}',
    }
    assert items[2]["type"] == "function_call_output" and items[2]["output"] == "text"
    assert converted[0]["name"] == "read_file" and "function" not in converted[0]


def test_models_that_fill_every_field_are_understood(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", 50000)
    env.reset()
    # GPT-style: every optional field present but empty.
    args = {"offset": 0, "path": "", "paths": [], "unit": "", "cluster": "C1", "line_offset": 0}
    (observation,), *_ = env.step(call("read_diff", args))
    assert "Invalid tool arguments" not in observation["content"]
    evidence = EVIDENCE.findall(observation["content"])[-1]
    (observation,), *_ = env.step(call("read_symbol", {"identifier": "users.py:get_user"}))
    assert "def get_user" in observation["content"]
    item = finding(evidence, suggestion="", line_hint=0)
    (observation,), *_ = env.step(call("report_finding", {"findings": [item]}))
    assert "F1 recorded" in observation["content"], observation["content"]


def test_snippet_mixing_diff_sides_anchors_partially(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", 50000)
    env.reset()
    (observation,), *_ = env.step(call("read_diff", {"cluster": "C1"}))
    evidence = EVIDENCE.findall(observation["content"])[-1]
    mixed = '-L4     return fetch(id)["name"]\n+L4     return fetch(id)["name"].upper()\nextra()'
    (observation,), *_ = env.step(
        call("report_finding", {"findings": [finding(evidence, existing_code=mixed)]})
    )
    assert "F1 recorded at api.py:L4 (head; in diff; U1)" in observation["content"]
    assert env.findings[0].anchor.startswith("diff-partial")


def test_unmetered_episode_shows_no_budget_and_never_wraps_up(planned):
    intel, plan = planned

    def wander(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn < 6:
            return call("read_file", {"path": "users.py"}, turn)
        return call("finish", {"summary": "done", "dismissed": ["users.py rename: correct"]}, turn)

    env = InvestigateEnv(intel, plan, "C1", None)
    policy = ScriptedPolicy(wander, usage=lambda r, m: Usage(input_tokens=400, output_tokens=100))
    episode = run_episode(env, policy, LoopConfig())
    assert episode.termination == "finished" and episode.budget_tokens is None
    assert not [e for s in episode.steps for e in s.events if e.kind == "wrap_up"]
    messages = episode.request_messages(episode.steps[-1])
    assert not any("budget" in (m.get("content") or "").lower() for m in messages)
    assert env.summary["dismissed"] == ["users.py rename: correct"]


def test_review_pools_the_case_budget_in_high_and_can_run_uncapped_or_split(planned, tmp_path):
    intel, plan = planned
    policy = ScriptedPolicy(standard_script, usage=lambda r, m: Usage(input_tokens=100))
    result = review(intel, policy, ReviewConfig(), run_id="r", case_id="case", out_dir=tmp_path)
    # high shares 5M tokens as a pool: no episode budget, the pool is on the case record
    assert all(episode.budget_tokens is None for episode in result.episodes)
    used = sum(episode.usage.total for episode in result.episodes)
    assert result.budget_pool == {"limit": 5_000_000, "used": used, "resumed": 0}
    episode = Episode.load(tmp_path / "episodes" / f"{result.episodes[0].id}.json")
    assert episode.task["budget_pool"] == 5_000_000
    # resumed: the finished episodes are loaded, not re-run, and spent from the pool first
    silent = ScriptedPolicy(lambda r: pytest.fail("a cached episode ran again"))
    again = review(intel, silent, ReviewConfig(), run_id="r", case_id="case", out_dir=tmp_path)
    assert again.episodes == result.episodes and not again.errors
    assert again.budget_pool == {"limit": 5_000_000, "used": used, "resumed": used}
    uncapped = ReviewConfig.model_validate({"investigate": {"budget": {"case_tokens": None}}})
    result = review(intel, policy, uncapped, run_id="r2", case_id="case", out_dir=tmp_path)
    assert all(episode.budget_tokens is None for episode in result.episodes)
    assert result.budget_pool is None and "budget_pool" not in result.model_dump()
    split = ReviewConfig.model_validate({"investigate": {"budget": {"sharing": "split"}}})
    result = review(intel, policy, split, run_id="r3", case_id="case", out_dir=tmp_path)
    # split, a single cluster gets all of it
    assert [episode.budget_tokens for episode in result.episodes] == [5_000_000]
    assert result.budget_pool is None
    assert result.versions == {
        "review": "review-v1", "prompt": "investigator-v5", "low_prompt": "investigator-low-v1",
        "merge_blocking": "merge-blocking-v1", "final_review": "final-review-v1",
        "budget_prompt": "budget-v2",
        "intel_tools": "tools-v3",
        "agent_tools": "tools-v3+investigator-v7", "ideation_prompt": "ideation-v1",
        "ideation_tools": "tools-v3+ideation-v3", "filter_prompt": "postfilter-v1",
        "context": "context-v2", "episode_schema": "episode-v2"}


def test_pooled_episode_warns_and_wraps_up_on_the_pool_and_records_its_state(planned):
    from review_agent.budget import CasePool

    intel, plan = planned
    pool = CasePool(10_000)
    pool.precharge(2000)  # episodes loaded on resume
    other = pool.meter("C9")  # another running episode
    other.charge(Usage(input_tokens=1000))
    env = InvestigateEnv(intel, plan, "C1", None, pool=pool)
    policy = ScriptedPolicy(wander, usage=lambda r, m: Usage(input_tokens=400, output_tokens=100))
    episode = run_episode(env, policy, LoopConfig())
    assert episode.termination == "budget" and episode.budget_tokens is None
    # 3000 used before, 500 a turn; a round of both episodes costs 1500: low after 5 turns
    # (5500 + 3 x 1500 reaches 10k), out after 13 (9500 + this episode's next 500)
    marks = [(s.index, e.kind, e.detail) for s in episode.steps for e in s.events
             if e.kind in ("milestone", "wrap_up")]
    assert marks == [
        (5, "milestone", {"tokens_left": 2250, "pool": {
            "limit": 10_000, "used": 5500, "running": 2, "round": 1500, "episode_used": 2500}}),
        (13, "wrap_up", {"reason": "budget", "pool": {
            "limit": 10_000, "used": 9500, "running": 2, "round": 1500, "episode_used": 6500}}),
    ]
    # what is left is the pool's remainder shared by the running episodes
    low = episode.request_messages(episode.steps[5])[-1]["content"]
    assert "2250 tokens left" in low and "about 4 more turns" in low
    assert pool.used == 3000 + episode.usage.total
    env.close()
    assert pool.running == {"C9": 1000}


def test_low_tier_runs_its_own_prompt_with_the_same_tools(planned, tmp_path):
    from review_agent import prompts

    intel, plan = planned
    policy = ScriptedPolicy(standard_script, usage=lambda r, m: Usage(input_tokens=100))
    result = review(intel, policy, ReviewConfig(tier="low"), run_id="low", case_id="case",
                    out_dir=tmp_path)
    assert result.config.tier == "low" and result.comments
    (path,) = (tmp_path / "episodes").glob("*.json")
    episode = json.loads(path.read_text())
    assert episode["prompt_version"] == "investigator-low-v1"
    assert episode["budget_tokens"] == 600_000
    first = episode["messages"][episode["steps"][0]["request"][0]]
    assert first["content"] == prompts.SYSTEM_LOW
    assert episode["tools"] == InvestigateEnv(intel, plan, "C1", None).tool_schemas()


def test_conditional_risk_is_recorded_and_rendered(planned, tmp_path):
    intel, plan = planned

    def script(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn == 0:
            return call("read_diff", {"cluster": "C1"}, turn)
        if turn == 1:
            risk = finding(last_evidence(request), condition="get_user returns None.")
            return call("report_finding", {"findings": [risk]}, turn)
        return call("finish", {"summary": "reviewed C1"}, turn)

    result = review(
        intel, ScriptedPolicy(script), ReviewConfig(), run_id="r", case_id="c", out_dir=tmp_path
    )
    (comment,) = result.comments
    assert comment.content.startswith(
        "api() crashes when get_user returns None\n\nRisk (when get_user returns None)."
    )
    (episode,) = result.episodes
    saved = Episode.load(tmp_path / "episodes" / f"{episode.id}.json")
    assert saved.findings[0]["condition"] == "get_user returns None."


def test_responses_reasoning_is_recorded():
    from types import SimpleNamespace as NS

    from review_agent.policy import ResponsesPolicy

    final = NS(
        output=[
            NS(type="reasoning", content=None, summary=[NS(text="check the None path")]),
            NS(type="function_call", call_id="c1", name="read_diff", arguments="{}"),
        ],
        usage=NS(input_tokens=10, output_tokens=5, input_tokens_details=None),
        status="completed",
        model="m",
    )
    policy = ResponsesPolicy("m", api_base="http://localhost", api_key="k")
    message = policy._response(final, 0.1).message
    assert message["reasoning_content"] == "check the None path"
    streamed = ResponsesPolicy._response(policy, NS(**{**vars(final), "output": []}), 0.1, "x")
    assert streamed.message["reasoning_content"] == "x"


def _read(env):
    (observation,), *_ = env.step(call("read_diff", {"cluster": "C1"}))
    return EVIDENCE.findall(observation["content"])[-1]


def test_small_model_argument_slips_are_repaired(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    evidence = _read(env)
    item = finding(evidence, severity="High", category="bug")
    item["evidence"] = json.dumps([evidence])  # an array sent as a JSON string
    (observation,), _, _, info = env.step(call("report_finding", {"findings": json.dumps([item])}))
    assert "F1 recorded" in observation["content"], observation["content"]
    repairs = info["observations"][0]["repairs"]
    # the findings array is decoded by normalize (the canonical call carries it); the
    # evidence array inside an item is repaired at dispatch
    assert "findings: decoded from a JSON string" not in repairs
    assert json.loads(info["tool_calls"][0]["function"]["arguments"])["findings"] == [item]
    assert "evidence: decoded from a JSON string" in repairs
    assert (env.findings[0].severity, env.findings[0].category) == ("major", "defect")


def test_missing_fields_are_filled_from_the_others(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    _read(env)
    no_evidence = finding("")
    no_evidence["evidence"] = []
    (observation,), *_ = env.step(call("report_finding", {"findings": [no_evidence]}))
    assert "F1 recorded" in observation["content"] and "cited for you" in observation["content"]
    no_code = finding("", line_hint=4)
    no_code.pop("existing_code")
    (observation,), *_ = env.step(call("report_finding", {"findings": [no_code]}))
    assert "F2 recorded at api.py:L4 (head" in observation["content"], observation["content"]
    no_path = finding("")
    no_path.pop("path")
    (observation,), *_ = env.step(call("report_finding", {"findings": [no_path]}))
    assert "F3 recorded at api.py:L4" in observation["content"], observation["content"]


def test_numbered_lines_anchor_where_the_text_really_is(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    evidence = _read(env)
    code = "+L2     if id is None:\n+L3   return Nothing\n+L4   return {name}"
    item = finding(evidence, path="users.py", existing_code=code)
    (observation,), *_ = env.step(call("report_finding", {"findings": [item]}))
    assert "recorded at users.py:L2 " in observation["content"], observation["content"]
    assert env.findings[0].anchor.startswith("numbered")


def test_bracket_anchor_rejected_and_repeated_failures_get_a_template(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    evidence = _read(env)
    (observation,), *_ = env.step(
        call("report_finding", {"findings": [finding(evidence, existing_code=")")]})
    )
    assert "only brackets" in observation["content"]
    assert "Several report_finding calls failed" not in observation["content"]
    (observation,), *_ = env.step(
        call("report_finding", {"findings": [finding(evidence, existing_code="nowhere(x)")]})
    )
    assert "Several report_finding calls failed" in observation["content"]
    (observation,), *_ = env.step(call("report_finding", {"findings": [finding(evidence)]}))
    assert "F1 recorded" in observation["content"] and env.book.report_streak == 0


def test_candidates_are_remembered_and_checked_at_finish(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    evidence = _read(env)
    add = {"add": ["api() may crash on None", {"concern": "test name", "priority": "low"}]}
    (observation,), *_ = env.step(call("note_candidates", add))
    assert "Added K1, K2" in observation["content"]
    assert "Open candidates (2 of 2)" in env.ledger()
    (observation,), *_ = env.step(call("note_candidates", {"add": ["API() may crash on None"]}))
    assert "1 already noted" in observation["content"] and len(env.candidates) == 2
    item = finding(evidence, candidate="K1")
    env.step(call("report_finding", {"findings": [item]}))
    (observation,), _, done, _ = env.step(call("finish", {"summary": "done"}))
    assert not done and "K2" in observation["content"]
    _, _, done, _ = env.step(call("finish", {"summary": "done", "dismissed": ["K2: fine"]}))
    statuses = [c["status"] for c in env.summary["candidates"]]
    assert done and statuses == ["reported", "dismissed"]


def test_turn_milestones_remind_the_model_to_converge(planned):
    intel, plan = planned

    def wander(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        return call("read_file", {"path": "users.py"}, turn)

    config = LoopConfig(max_steps=6, milestones=[3, 1])
    episode = run_episode(InvestigateEnv(intel, plan, "C1", None), ScriptedPolicy(wander), config)
    assert episode.termination == "max_steps" and len(episode.steps) == 6
    marks = [
        e.detail["turns_left"] for s in episode.steps for e in s.events if e.kind == "milestone"
    ]
    assert marks == [3, 1]
    last = episode.request_messages(episode.steps[-1])
    assert "last turn" in last[-1]["content"]


def test_same_line_different_issues_are_not_merged():
    class Ep:
        id = "e"

        def __init__(self, findings):
            self.findings = findings

    def item(index, title):
        return {
            "id": f"F{index}",
            "path": "a.py",
            "side": "head",
            "start_line": 3,
            "end_line": 3,
            "in_diff": True,
            "title": title,
            "description": "d",
            "category": "defect",
            "severity": "major",
            "existing_code": "    total = add(x)",
            "withdrawn": False,
        }

    findings = [
        item(1, "add() result overflows for large x"),
        item(2, "variable name total shadows builtin"),
        item(3, "add() result overflows on large x values"),
    ]
    comments = dedupe(order(select([(0, Ep(findings))], AggregateConfig())), AggregateConfig())
    assert [c.title for c in comments] == [findings[0]["title"], findings[1]["title"]]


def test_coverage_and_seeded_candidates(planned):
    from review_agent.ideation import IdeationEnv

    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None, coverage=True,
                         seed_candidates=[{"concern": "None id crashes", "unit": "U1", "priority": "high"}])
    messages, _ = env.reset()
    assert "K1 [high] U1 None id crashes" in messages[1]["content"]
    schema = next(s for s in env.tool_schemas() if s["function"]["name"] == "note_candidates")
    assert "reviewed" in json.dumps(schema)
    handles = [plan.unit_handles[key] for key in env.cluster.unit_ids]
    others = [h for h in handles if h != "U1"]
    if others:
        (observation,), *_ = env.step(call("finish", {"summary": "done", "dismissed": ["K1: fine"]}))
        assert "have no candidate, finding or reviewed mark" in observation["content"]
        (observation,), *_ = env.step(call("note_candidates", {"reviewed": others}))
        assert "every unit has a candidate" in observation["content"]
    _, _, done, _ = env.step(call("finish", {"summary": "done", "dismissed": ["K1: fine"]}))
    assert done
    # a listing pass ends at its first note_candidates call
    listing = IdeationEnv(intel, plan, "C1", None)
    listing.reset()
    (observation,), _, done, _ = listing.step(call("report_finding", {"findings": []}))
    assert not done
    (observation,), _, done, _ = listing.step(call("note_candidates", {"add": [{"concern": "x", "unit": "U1"}]}))
    assert done and listing.candidates[0]["concern"] == "x"


def test_review_with_candidate_sampling(planned, tmp_path):
    from review_agent import prompts

    intel, plan = planned

    def script(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if request.messages[0]["content"] == prompts.IDEATION_SYSTEM:
            if turn == 0:
                return call("read_diff", {"cluster": "C1"}, turn)
            return call("note_candidates", {"add": [{"concern": "api() crashes on None", "unit": "U1"}]}, turn)
        if turn == 0:
            assert "already recorded" in request.messages[1]["content"]
        return standard_script(request)

    policy = ScriptedPolicy(script, usage=lambda r, m: Usage(input_tokens=10))
    config = ReviewConfig.model_validate({"investigate": {"ideation": {"samples": 2}}})
    result = review(intel, policy, config, run_id="r", case_id="case", out_dir=tmp_path)
    clusters = len(plan.clusters)
    # two listing passes (2 steps each) plus the investigation per cluster: read, report,
    # finish (refused once: the seeded candidate is still open), finish
    assert result.usage.input_tokens == clusters * (2 * 2 + 4) * 10
    assert len(list((tmp_path / "episodes").glob("*.json"))) == clusters * 3
    from review_agent.versions import IDEATION_PROMPT_VERSION, PROMPT_VERSION
    versions = sorted(json.loads(f.read_text())["prompt_version"]
                      for f in (tmp_path / "episodes").glob("*.json"))
    assert versions == sorted([IDEATION_PROMPT_VERSION] * (2 * clusters) + [PROMPT_VERSION] * clusters)


def test_review_config_is_grouped_by_stage_and_strict():
    import pytest
    from pydantic import ValidationError

    config = ReviewConfig.model_validate({
        "investigate": {"loop": {"context_window": 32000}, "coverage": True,
                        "examples": {"path": "cards.jsonl"}, "budget": {"case_tokens": 300000}},
        "postprocess": {"postfilter": {}}})
    assert config.investigate.loop.context_window == 32000 and config.investigate.coverage
    assert config.investigate.examples.mode == "retrieved"
    for stale in ({"loop": {}}, {"coverage": True}, {"investigate": {"fact_checks": True}},
                  {"investigate": {"budget": {"enabled": True}}},
                  {"run": {"concurrency": 4}},
                  {"investigate": {"loop": {"context_windw": 1}}},
                  {"postprocess": {"aggregate": {"require_in_diff": False}}},
                  {"postprocess": {"postfilter": {"falsify": False}}}):
        with pytest.raises(ValidationError):
            ReviewConfig.model_validate(stale)


def test_gate_bounds_requests_in_flight_across_threads():
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    lock, state = threading.Lock(), {"now": 0, "peak": 0}

    def slow(request):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.02)
        with lock:
            state["now"] -= 1
        return {"role": "assistant", "content": "ok"}

    inner = ScriptedPolicy(slow, name="m")
    gate = GatedPolicy(inner, 3)
    assert gate.name == "m" and gate.describe() == inner.describe()
    request = ModelRequest(messages=({"role": "user", "content": "x"},))
    with ThreadPoolExecutor(max_workers=12) as pool:
        replies = list(pool.map(lambda _: gate.complete(request), range(24)))
    assert [r.message["content"] for r in replies] == ["ok"] * 24
    assert state["peak"] == 3
    with pytest.raises(ValueError):
        GatedPolicy(inner, 0)
