from __future__ import annotations

import json
import re

import pytest

from review_agent.agent import LoopConfig, run_episode
from review_agent.agent_tools import AGENT_TOOLS
from review_agent.env import InvestigateEnv
from review_agent.normalize import normalize
from review_agent.policy import ReplayPolicy, ScriptedPolicy
from review_agent.trajectory import sft_samples
from review_core.intel.tools import SPECS
from review_core.triage import Triage

EVIDENCE = re.compile(r"evidence ([0-9a-f]{12})")
MODELS = {name: spec[0] for name, spec in SPECS.items()} | {
    name: spec[0] for name, spec in AGENT_TOOLS.items()
}
FILES = ["api.py", "users.py", "tests/test_users.py"]


def tool_call(name, arguments, key="c0"):
    text = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {"id": key, "type": "function", "function": {"name": name, "arguments": text}}


def canonical(name, arguments, candidates=("K1",)):
    """(name, arguments) of the normalized call, or None when the call is left as it is."""
    original = tool_call(name, arguments)
    result = normalize(original, MODELS, set(candidates), lambda: FILES)
    if result is original:
        return None
    assert result["id"] == "c0" and result["type"] == "function"
    return result["function"]["name"], json.loads(result["function"]["arguments"])


def test_path_on_search_tools_becomes_path_glob():
    assert canonical("code_search", {"pattern": "x", "path": "api.py"}) == (
        "code_search", {"pattern": "x", "path_glob": "api.py"})
    assert canonical("find_definition", {"name": "f", "path": "tests"}) == (
        "find_definition", {"name": "f", "path_glob": "tests/**"})
    assert canonical("code_search", {"pattern": "x", "path": "tests/"})[1]["path_glob"] == "tests/**"
    assert canonical("structural_search", {"pattern": "f($A)", "language": "python",
                                           "path": "tests/*.py"})[1]["path_glob"] == "tests/*.py"
    for anywhere in ("*", ""):
        assert canonical("code_search", {"pattern": "x", "path": anywhere}) == (
            "code_search", {"pattern": "x"})
    # the same value given twice
    assert canonical("code_search", {"pattern": "x", "path": "api.py", "path_glob": "api.py"}) == (
        "code_search", {"pattern": "x", "path_glob": "api.py"})


def test_path_is_left_alone_when_unclear_or_valid():
    assert canonical("code_search", {"pattern": "x", "path": "nowhere.py"}) is None
    assert canonical("code_search", {"pattern": "x", "path": "api.py", "path_glob": "*.md"}) is None
    assert canonical("read_file", {"path": "api.py"}) is None  # takes path itself
    assert canonical("read_symbol", {"identifier": "api.py::api", "path": "api.py"}) is None
    assert canonical("code_search", {"pattern": "x", "path_glob": "tests/**"}) is None


def test_candidate_priorities_take_severity_words():
    add = [{"concern": "a", "priority": "critical"}, {"concern": "b", "priority": "nit"},
           {"concern": "c", "priority": None}, {"concern": "d", "priority": "media"},
           {"concern": "e", "priority": "High"}, {"concern": "f", "priority": "low"}, "g"]
    name, arguments = canonical("note_candidates", {"add": add})
    assert name == "note_candidates"
    assert arguments["add"] == [
        {"concern": "a", "priority": "high"}, {"concern": "b", "priority": "low"},
        {"concern": "c"}, {"concern": "d", "priority": "medium"},
        {"concern": "e", "priority": "high"}, {"concern": "f", "priority": "low"}, "g"]
    # sent as a JSON string: decoded along with the fix
    assert canonical("note_candidates", {"add": json.dumps([{"concern": "a", "priority": "major"}])}) == (
        "note_candidates", {"add": [{"concern": "a", "priority": "high"}]})


def test_candidate_priorities_left_alone_when_valid_or_unknown():
    assert canonical("note_candidates", {"add": [{"concern": "a", "priority": "high"}]}) is None
    assert canonical("note_candidates", {"add": [{"concern": "a"}], "dismiss": ["K1: ok"]}) is None
    # one value that maps to nothing: the call stays as written (and fails as before)
    assert canonical("note_candidates", {"add": [{"concern": "a", "priority": "major"},
                                                 {"concern": "b", "priority": "urgent"}]}) is None
    for typo in ("me", "med", "hihg"):
        assert canonical("note_candidates", {"add": [{"concern": "a", "priority": typo}]}) is None


def test_withdrawing_a_candidate_dismisses_it():
    assert canonical("update_finding", {"id": "K1", "withdraw": True, "reason": "fine"}) == (
        "note_candidates", {"dismiss": ["K1: fine"]})
    assert canonical("update_finding", {"id": " K1", "dismiss": "true", "reason": "K1: fine"}) == (
        "note_candidates", {"dismiss": ["K1: fine"]})
    assert canonical("update_finding", {"id": "K1", "dismiss": "checked, fine"}) == (
        "note_candidates", {"dismiss": ["K1: checked, fine"]})
    assert canonical("update_finding", {"id": "K1", "withdraw": "true"}) == (
        "note_candidates", {"dismiss": ["K1"]})


def test_other_candidate_updates_are_left_alone():
    assert canonical("update_finding", {"id": "K2", "withdraw": True}) is None  # not noted
    assert canonical("update_finding", {"id": "K1", "title": "new"}) is None
    assert canonical("update_finding", {"id": "K1", "dismiss": "false", "reason": "x"}) is None
    assert canonical("update_finding", {"id": "F1", "withdraw": True}) is None


def test_read_diff_drops_the_cluster_beside_a_narrower_scope():
    assert canonical("read_diff", {"cluster": "C1", "path": "api.py"}) == (
        "read_diff", {"path": "api.py"})
    assert canonical("read_diff", {"cluster": "C1", "unit": "U1", "offset": 0}) == (
        "read_diff", {"unit": "U1", "offset": 0})
    assert canonical("read_diff", {"cluster": "C1", "path": ""}) is None  # valid as written
    assert canonical("read_diff", {"cluster": "C1"}) is None


def test_findings_string_closed_with_extra_brackets_is_parsed():
    items = [{"path": "api.py", "title": "t"}]
    assert canonical("report_finding", {"findings": json.dumps(items) + "}"}) == (
        "report_finding", {"findings": items})
    assert canonical("report_finding", {"findings": json.dumps(items) + "]}\n"}) == (
        "report_finding", {"findings": items})
    assert canonical("report_finding", {"findings": json.dumps(items)}) == (
        "report_finding", {"findings": items})  # plain JSON string: decoded
    broken = '[{"path": "a.py", "existing_code": "f(\\"")"}]'
    assert canonical("report_finding", {"findings": broken}) is None
    assert canonical("report_finding", {"findings": json.dumps(items) + ", {"}) is None
    # decoded, and still rejected at dispatch: findings must not be empty
    assert canonical("report_finding", {"findings": "[]"}) == ("report_finding", {"findings": []})


def test_array_arguments_sent_as_json_strings_are_decoded_for_every_tool():
    items = [{"path": "api.py", "title": "t", "evidence": ["abc"]}]
    cases = [
        ("report_finding", {"findings": json.dumps(items)}, {"findings": items}),
        ("report_finding", {"findings": "  " + json.dumps(items, indent=2) + "\n"},
         {"findings": items}),
        ("read_diff", {"paths": json.dumps(["api.py", "users.py"])},
         {"paths": ["api.py", "users.py"]}),
        ("finish", {"summary": "s", "unreviewed": '["U2"]', "dismissed": '["K1: fine"]'},
         {"summary": "s", "unreviewed": ["U2"], "dismissed": ["K1: fine"]}),
        ("update_finding", {"id": "F1", "evidence": '["abc", "def"]'},
         {"id": "F1", "evidence": ["abc", "def"]}),
        ("note_candidates", {"add": '[{"concern": "a"}]', "dismiss": '["K1: ok"]'},
         {"add": [{"concern": "a"}], "dismiss": ["K1: ok"]}),
        # lenient JSON as repair reads it: a raw newline inside a string
        ("report_finding", {"findings": '[{"path": "a.py", "existing_code": "x\ny"}]'},
         {"findings": [{"path": "a.py", "existing_code": "x\ny"}]}),
    ]
    for name, arguments, expected in cases:
        assert canonical(name, arguments) == (name, expected), name
    # decoded beside another rewrite of the same call
    assert canonical("read_diff", {"cluster": "C1", "paths": '["api.py"]'}) == (
        "read_diff", {"paths": ["api.py"]})
    assert canonical("note_candidates", {"add": '[{"concern": "a", "priority": "nit"}]',
                                         "dismiss": '["K1: ok"]'}) == (
        "note_candidates", {"add": [{"concern": "a", "priority": "low"}], "dismiss": ["K1: ok"]})


def test_strings_that_are_not_json_of_the_expected_type_are_left_alone():
    for name, arguments in [
        ("report_finding", {"findings": "api.py: get_user may return None"}),
        ("report_finding", {"findings": '[{"path": "a.py", "title": "t"'}),  # unterminated
        ("report_finding", {"findings": '{"path": "a.py"}'}),  # an object, not an array
        ("read_diff", {"paths": "api.py"}),
        ("read_diff", {"paths": "[api.py]"}),  # bracketed, not JSON
        ("finish", {"summary": "[done]"}),  # a string field: never decoded
        ("finish", {"summary": '["s"]'}),
        ("code_search", {"pattern": "[a-z]+", "path_glob": "*.py"}),
    ]:
        assert canonical(name, arguments) is None, (name, arguments)


def test_json_string_findings_are_recorded_and_text_findings_still_rejected(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    paths = tool_call("read_diff", {"paths": json.dumps(["users.py"])}, "a")
    (observation,), _, _, info = env.step(message(paths))
    assert info["observations"][0]["error"] is None
    assert info["tool_calls"][0]["function"]["arguments"] == json.dumps({"paths": ["users.py"]})
    evidence = EVIDENCE.findall(observation["content"])[-1]
    item = {"path": "users.py", "title": "get_user returns None", "category": "defect",
            "description": "Callers subscript the result.", "severity": "major",
            "existing_code": "    if id is None:\n        return None", "evidence": [evidence]}
    report = tool_call("report_finding", {"findings": json.dumps([item])}, "b")
    (observation,), _, _, info = env.step(message(report))
    assert "F1 recorded at users.py" in observation["content"]
    (record,) = info["observations"]
    assert record["error"] is None and isinstance(record["arguments"]["findings"], list)
    assert "findings: decoded from a JSON string" not in record["repairs"]  # canonical now
    assert json.loads(info["tool_calls"][0]["function"]["arguments"])["findings"] == [item]
    text = tool_call("report_finding", {"findings": "users.py returns None"}, "c")
    (observation,), _, _, info = env.step(message(text))
    assert observation["content"] == (
        "Error: invalid arguments for report_finding: findings must be a non-empty array of "
        "finding objects.")
    assert info["observations"][0]["error"] == "findings: not a list"
    assert "tool_calls" not in info
    assert len(env.findings) == 1


def test_tool_names_with_parser_markup():
    dismiss = json.dumps(["K1: fine"])
    assert canonical("<note_candidates", {"dismiss": dismiss}) == (
        "note_candidates", {"dismiss": ["K1: fine"]})
    assert canonical("<note_candidates", {"dismiss": ["K1: fine"]}) == (
        "note_candidates", {"dismiss": ["K1: fine"]})
    assert canonical("code_search<parameter=path_glob", {"pattern": "x", "path_glob": "*.py"}) == (
        "code_search", {"pattern": "x", "path_glob": "*.py"})
    # the markup names a parameter whose value the parser lost
    assert canonical("code_search<parameter=path_glob", {"pattern": "x"}) is None
    assert canonical("code_search<parameter=pattern", {}) is None  # not a valid call
    assert canonical("find_reference\n<parameter=identifier", {"identifier": "a"}) is None
    assert canonical("dismiss", {}) is None


def test_valid_calls_are_returned_as_they_are():
    calls = [
        ("read_diff", {"cluster": "C1"}), ("read_file", {"path": "api.py", "start_line": 2}),
        ("code_search", {"pattern": "x", "path_glob": "*.py"}),
        ("note_candidates", {"add": [{"concern": "a", "priority": "low"}]}),
        ("update_finding", {"id": "F1", "withdraw": True}),
        ("report_finding", {"findings": [{"path": "api.py"}]}), ("finish", {"summary": "s"}),
    ]
    for name, arguments in calls:
        assert canonical(name, arguments) is None, name
    raw = tool_call("read_diff", "{")  # not JSON: dispatch reports it
    assert normalize(raw, MODELS, set(), lambda: FILES) is raw


@pytest.fixture
def planned(reviewed):
    _, _, intel = reviewed
    return intel, Triage(intel).plan()


def message(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def evidence_in(request):
    for item in reversed(request.messages):
        found = EVIDENCE.findall(item.get("content") or "") if item.get("role") == "tool" else []
        if found:
            return found[-1]
    return "000000000000"


def script(request):
    turn = sum(1 for m in request.messages if m["role"] == "assistant")
    if turn == 0:
        return message(tool_call("read_diff", {"cluster": "C1"}, "a"))
    if turn == 1:
        add = {"add": [{"concern": "api() crashes on None", "priority": "major"}]}
        return message(tool_call("note_candidates", add, "b"),
                       tool_call("code_search", {"pattern": "fetch", "path": "tests"}, "c"))
    if turn == 2:
        withdraw = {"id": "K1", "withdraw": True, "reason": "users.py handles None"}
        return {**message(tool_call("update_finding", withdraw, "d")), "reasoning_content": "hm"}
    return message(tool_call("finish", {"summary": "reviewed C1"}, "e"))


def test_episode_shows_and_trains_the_canonical_calls_and_keeps_the_raw_ones(planned):
    intel, plan = planned
    episode = run_episode(InvestigateEnv(intel, plan, "C1", None), ScriptedPolicy(script),
                          LoopConfig(), episode_id="n1")
    assert episode.termination == "finished"
    first, second, third, last = episode.steps
    assert first.canonical_calls is None and last.canonical_calls is None
    # the model's own calls stay the response; the canonical ones are recorded beside them
    assert second.response["tool_calls"][1]["function"]["arguments"] == json.dumps(
        {"pattern": "fetch", "path": "tests"})
    assert [c["function"] for c in second.canonical_calls] == [
        {"name": "note_candidates",
         "arguments": json.dumps({"add": [{"concern": "api() crashes on None", "priority": "high"}]})},
        {"name": "code_search", "arguments": json.dumps({"pattern": "fetch", "path_glob": "tests/**"})},
    ]
    assert third.response["tool_calls"][0]["function"]["name"] == "update_finding"
    assert third.canonical_calls[0]["function"] == {
        "name": "note_candidates", "arguments": json.dumps({"dismiss": ["K1: users.py handles None"]})}
    assert [o.error for s in episode.steps for o in s.observations] == [None] * 5
    assert [o.name for o in third.observations] == ["note_candidates"]
    assert episode.candidates[0]["status"] == "dismissed"
    assert episode.candidates[0]["priority"] == "high"
    # later requests show the canonical calls, without reasoning
    shown = [m for m in episode.request_messages(last) if m["role"] == "assistant"]
    assert shown == [first.response, second.message(), third.message()]
    assert shown[1]["tool_calls"] == second.canonical_calls
    assert "reasoning_content" not in shown[2]
    # training data teaches them, with the reasoning, each turn once
    (sample,) = sft_samples(episode)
    trained = [m for m in sample["messages"] if m["role"] == "assistant"]
    assert [m["weight"] for m in trained] == [1, 1, 1, 1]
    assert trained[1]["tool_calls"] == second.canonical_calls
    assert trained[2]["tool_calls"] == third.canonical_calls
    assert trained[2]["reasoning_content"] == "hm"
    assert sample["metadata"]["tools_version"] == "tools-v3+investigator-v7"
    # a replay serves the raw responses and normalizes them again: the same episode
    replayed = run_episode(InvestigateEnv(intel, plan, "C1", None), ReplayPolicy(episode),
                           LoopConfig(), episode_id="n1")
    original, again = episode.content(), replayed.content()
    original.pop("policy"), again.pop("policy")
    assert original == again


def test_valid_calls_reach_the_context_as_the_model_wrote_them(planned):
    intel, plan = planned

    def valid(request):
        turn = sum(1 for m in request.messages if m["role"] == "assistant")
        if turn == 0:
            return message(tool_call("read_diff", {"cluster": "C1"}, "a"))
        if turn == 1:
            add = {"add": [{"concern": "api() crashes on None", "priority": "high"}]}
            search = {"pattern": "fetch", "path_glob": "tests/**", "path": ""}
            return message(tool_call("note_candidates", add, "b"),
                           tool_call("code_search", search, "c"))
        return message(tool_call("finish", {"summary": "done", "dismissed": ["K1: fine"]}, "d"))

    episode = run_episode(InvestigateEnv(intel, plan, "C1", None), ScriptedPolicy(valid),
                          LoopConfig())
    assert episode.termination == "finished"
    assert all(step.canonical_calls is None for step in episode.steps)
    shown = [m for m in episode.request_messages(episode.steps[-1]) if m["role"] == "assistant"]
    assert shown == [step.response for step in episode.steps[:-1]]
    (sample,) = sft_samples(episode)
    trained = [m for m in sample["messages"] if m["role"] == "assistant"]
    assert [{k: v for k, v in m.items() if k != "weight"} for m in trained] == [
        step.response for step in episode.steps]


def test_other_uses_of_a_candidate_id_say_how_to_dismiss(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    env.step(message(tool_call("note_candidates", {"add": ["api() crashes on None"]})))
    (observation,), _, _, info = env.step(
        message(tool_call("update_finding", {"id": "K1", "title": "renamed"})))
    assert "K1 is a candidate, not a finding" in observation["content"]
    assert 'note_candidates(dismiss=["K1: reason"])' in observation["content"]
    assert info["observations"][0]["error"] == "candidate id" and "tool_calls" not in info
    (observation,), *_ = env.step(message(tool_call("update_finding", {"id": "K7", "withdraw": True})))
    assert "K7 is a candidate, not a finding" in observation["content"]
    assert env.candidates[0]["status"] == "open"


def test_existing_code_with_read_file_prefixes_anchors_and_invented_code_does_not(planned):
    intel, plan = planned
    env = InvestigateEnv(intel, plan, "C1", None)
    env.reset()
    (observation,), *_ = env.step(message(tool_call("read_file", {"path": "users.py"})))
    evidence = EVIDENCE.findall(observation["content"])[-1]
    assert "* L2     if id is None:" in observation["content"]
    item = {"path": "users.py", "title": "get_user returns None", "category": "defect",
            "description": "Callers subscript the result.", "severity": "major",
            "evidence": [evidence]}
    copied = "* L2     if id is None:\n* L3         return None"
    (observation,), *_ = env.step(
        message(tool_call("report_finding", {"findings": [{**item, "existing_code": copied}]})))
    assert "F1 recorded at users.py:L2-3 (head; in diff" in observation["content"]
    invented = "* L2     if user is missing:\n* L3         raise Missing(id)"
    (observation,), *_ = env.step(
        message(tool_call("report_finding", {"findings": [{**item, "existing_code": invented}]})))
    assert "existing_code was not found in users.py" in observation["content"]
    assert len(env.findings) == 1
