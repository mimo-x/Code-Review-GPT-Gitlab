from __future__ import annotations

import pytest

from review_agent import checks
from review_agent.env import InvestigateEnv
from review_core.intel import CodeIntel
from review_core.triage import Triage
from review_core.workspace import Workspace

from test_agent import EVIDENCE, call


def test_misspelled_word():
    assert checks.misspelled_word("Typo: 'recieve' should be 'receive'") == "recieve"
    assert checks.misspelled_word("The comment misspells 'method' as 'mehod'.") == "mehod"
    assert checks.misspelled_word("'method' is misspelled as `mehod`") == "mehod"
    assert checks.misspelled_word("Typo in the comment") is None


def test_typo_check():
    head = "fn pay(encrypted_payload: String) {}\n// list payment mehod\n"
    base = "fn pay(encypted_payload: String) {}\n// list payment mehod\n"
    assert checks.typo_check("Unclear name 'pay'", head, base) is None
    assert checks.typo_check("Typo: 'mehod' should be 'method'", head, base) == ("ok", "mehod", None)
    # the pull request fixed it: the word is only in the old version
    fixed = "Typo: 'encypted_payload' should be 'encrypted_payload'"
    assert checks.typo_check(fixed, head, base)[0] == "fixed"
    # mis-copied spelling of a word only the old version has: still fixed by the pull request
    assert checks.typo_check("Typo: 'encpted_payload' should be 'encrypted_payload'", head, base) == (
        "fixed", "encpted_payload", "encypted_payload")
    # mis-copied spelling of a typo still in the new code: corrected
    assert checks.typo_check("Typo: 'mehtod' should be 'method'", head, base) == (
        "corrected", "mehtod", "mehod")
    assert checks.typo_check("Typo: 'colour' should be 'color'", head, base)[0] == "missing"


def test_clean_ids():
    ids = {"K1", "K2", "K3", "K9"}
    assert checks.clean_ids("K3: tryReadDoubles returns early", ids, "") == (
        "TryReadDoubles returns early", ["K3"])
    assert checks.clean_ids("K1 (high): the signature changed", ids, "")[0] == "The signature changed"
    assert checks.clean_ids("K1/K2: rename only updates one", ids, "")[1] == ["K1", "K2"]
    assert checks.clean_ids("Shared state is not reset (K9)", ids, "") == (
        "Shared state is not reset", ["K9"])
    # never: ids we did not issue, ids that are words in the code, or mentions mid-sentence
    assert checks.clean_ids("K7: something", ids, "")[1] == []
    assert checks.clean_ids("K2: uses K2 constant", ids, "const K2 = 4")[1] == []
    assert checks.clean_ids("the bug described in K1 exists", ids, "")[1] == []
    assert checks.clean_ids("K3", ids, "")[1] == []


def test_cut_field_leak():
    leaked = 'Returns early on an empty list.", "candidate": "K3", "evidence": ["2e02fb88"]'
    assert checks.cut_field_leak(leaked) == "Returns early on an empty list."
    assert checks.cut_field_leak('Use "a", not "b".') == 'Use "a", not "b".'


@pytest.fixture
def typo_env(repository, tmp_path):
    repository.write("pay.py", "def pay(encypted_payload):\n    # list payment mehod\n    return 1\n")
    base = repository.commit("base")
    repository.write("pay.py", "def pay(encrypted_payload):\n    # list payment mehod\n    return 2\n")
    head = repository.commit("head")
    workspace = Workspace.create(repository.path, tmp_path / "state", "test/typo", base, head)
    intel = CodeIntel(workspace)
    plan = Triage(intel).plan()
    env = InvestigateEnv(intel, plan, plan.clusters[0].handle, None)
    env.reset()
    (observation,), *_ = env.step(call("read_diff", {"cluster": plan.clusters[0].handle}))
    env.step(call("note_candidates", {"add": [{"concern": "typos"}]}))
    return env, EVIDENCE.findall(observation["content"])[-1]


def report(env, evidence, code, title):
    item = {"path": "pay.py", "existing_code": code, "title": title, "description": title + ".",
            "category": "maintainability", "severity": "nit", "evidence": [evidence]}
    (observation,), _, _, info = env.step(call("report_finding", {"findings": [item]}))
    return observation["content"], info["observations"][0]["repairs"]


def test_env_rules(typo_env):
    env, evidence = typo_env
    text, _ = report(env, evidence, "def pay(encypted_payload):",
                     "Typo: 'encypted_payload' should be 'encrypted_payload'")
    assert "removed code" in text and not env.findings
    text, _ = report(env, evidence, "def pay(encrypted_payload):",
                     "Typo: 'encypted_payload' should be 'encrypted_payload'")
    assert "already fixed" in text and not env.findings
    text, repairs = report(env, evidence, "# list payment mehod",
                           "K1: Typo 'mehtod' should be 'method'")
    assert "F1 recorded" in text
    finding = env.findings[0]
    assert finding.title == "Typo 'mehod' should be 'method'"
    assert any("corrected to 'mehod'" in r for r in repairs)
    assert any("removed candidate ids K1" in r for r in repairs)
    assert env.candidates[0]["status"] == "reported"


def test_examples_retrieval_and_env(tmp_path, typo_env):
    import json
    from pathlib import Path

    from review_agent import examples

    source = tmp_path / "comments.jsonl"
    rows = []
    for i, (path, hunk, body, cat) in enumerate([
        ("a/pay.py", "+    # list payment mehod", "Typo in the comment: mehod should be method.", "Maintainability"),
        ("a/x.py", "+    if value is None: return", "This returns None silently; callers expect a list.", "Defect"),
        ("b/y.py", "+    for item in items: total += price(item)", "price() is called in a loop; cache it.", "Performance"),
        ("c/z.go", "+    return err", "Wrap the error with context before returning it.", "Defect"),
        ("bench/q.py", "+    x = 1", "This is in a benchmark repository and must be excluded.", "Defect"),
    ]):
        rows.append({"id": i, "repo": path.split("/")[0] + "/repo", "path": path, "diff_hunk": hunk,
                     "body": body, "in_reply_to_id": None, "speaker_role": "reviewer",
                     "classification": {"actionable": True, "kind": "issue", "category": cat}})
    source.write_text("\n".join(json.dumps(r) for r in rows))
    target = tmp_path / "cards.jsonl"
    assert examples.build(source, target, {"bench/repo"}) == 4
    index = examples.ExampleIndex.load(target)
    found = index.search("pay.py", "-    # list payment mehod\n+    # list payment method", k=2)
    assert found[0]["body"].startswith("Typo") and len({c["kind"] for c in found}) == len(found)
    assert all(c["language"] == "Python" for c in found)
    assert index.search("main.go", "+    return err", k=3)[0]["language"] == "Go"
    # the environment shows the examples once, with the first diff
    env, _ = typo_env
    env.examples = (index, "retrieved")
    env.examples_shown = []
    (observation,), *_ = env.step({"role": "assistant", "content": None, "tool_calls": [
        {"id": "x", "type": "function", "function": {"name": "read_diff", "arguments": "{}"}}]})
    assert examples.INTRO in observation["content"] and "Example 1 (Python" in observation["content"]
    (observation,), *_ = env.step({"role": "assistant", "content": None, "tool_calls": [
        {"id": "y", "type": "function", "function": {"name": "read_diff", "arguments": "{}"}}]})
    assert examples.INTRO not in observation["content"]


def test_coverage_and_ideation(planned_two=None):
    from review_agent.ideation import merge

    merged = merge([
        [{"concern": "None id crashes api()", "unit": "U1", "priority": "medium"},
         {"concern": "docstring of get_user is stale", "unit": "U2", "priority": "low"}],
        [{"concern": "api() crashes for None id", "unit": "U1", "priority": "high"},
         {"concern": "test does not cover the empty name", "unit": "U3", "priority": "low"}],
    ])
    assert merged[0]["concern"] == "None id crashes api()" and merged[0]["votes"] == 2
    assert merged[0]["priority"] == "high" and len(merged) == 3
