"""review-agent run: one merge request from a JSON request, as a host platform runs it."""
from __future__ import annotations

import json

import pytest
from test_agent import call, standard_script

from review_agent import run as runner
from review_agent.policy import GatedPolicy, LiteLLMPolicy, ResponsesPolicy, ScriptedPolicy


def script(request):
    system = request.messages[0]["content"]
    if "last reviewer" in system:
        return call("select_comments", {"keep": [{"id": "c1", "severity": "critical"}]})
    assert "Simplified Chinese" in system and "go straight to the author" in system
    return standard_script(request)


def request_data(reviewed, tmp_path, **extra):
    repository, workspace, _ = reviewed
    snapshot = workspace.snapshot
    return {
        "repository": str(repository.path), "repository_id": "test/project",
        "base_sha": snapshot.base_sha, "head_sha": snapshot.head_sha,
        "state_dir": str(tmp_path / "agent-state"),
        "config": {"tier": "high", "language": "zh-CN"},
        "model": {"name": "openai/test-model", "api_base": "http://127.0.0.1:1/v1"}, **extra,
    }


def test_run_returns_the_findings_to_post(reviewed, tmp_path):
    request = runner.RunRequest.model_validate(request_data(reviewed, tmp_path))
    result = runner.run(request, ScriptedPolicy(script))
    assert result["version"] == runner.RESULT_VERSION and not result["errors"]
    assert (result["tier"], result["language"]) == ("high", "zh-CN")
    (found,) = result["findings"]
    assert (found["path"], found["side"], found["start_line"]) == ("api.py", "new", 4)
    assert found["severity"] == "critical"  # settled by the final review
    assert found["body"] == "get_user now returns None for a None id; subscripting it raises."
    assert 'fetch(id)["name"].upper()' in found["existing_code"]
    assert found["also"] == [] and found["condition"] is None
    assert result["usage"]["input_tokens"] >= 0 and result["duration_s"] >= 0


def test_run_excludes_paths_before_investigating(reviewed, tmp_path):
    excluded = ["api.py", "users.py", "tests/test_users.py"]
    calls = []

    def record(request):
        calls.append(request)
        return script(request)

    unrestricted = runner.RunRequest.model_validate(request_data(reviewed, tmp_path))
    assert runner.run(unrestricted, ScriptedPolicy(record))["findings"]
    assert calls
    calls.clear()
    scoped = unrestricted.model_copy(update={"excluded_paths": tuple(excluded)})
    result = runner.run(scoped, ScriptedPolicy(record))
    assert not result["findings"] and not result["errors"] and not calls


def test_failed_investigation_can_resume(reviewed, tmp_path):
    request = runner.RunRequest.model_validate(request_data(reviewed, tmp_path))

    def unavailable(_):
        raise RuntimeError("temporary failure")

    first = runner.run(request, ScriptedPolicy(unavailable))
    assert first["errors"] and not first["findings"]
    recovered = runner.run(request, ScriptedPolicy(script))
    assert recovered["findings"] and not recovered["errors"]
    cached = runner.run(request, ScriptedPolicy(unavailable))
    assert cached["findings"] == recovered["findings"] and not cached["errors"]


@pytest.mark.parametrize("change", [
    {"name": "openai/another-model"},
    {"protocol": "responses"},
    {"api_base": "http://127.0.0.1:2/v1"},
])
def test_changing_model_route_runs_a_fresh_review(reviewed, tmp_path, change):
    original = runner.RunRequest.model_validate(request_data(reviewed, tmp_path))
    first_policy = ScriptedPolicy(script)
    first = runner.run(original, first_policy)
    assert first["findings"] and not first["errors"] and first_policy.calls > 0

    changed = original.model_copy(update={"model": original.model.model_copy(update=change)})
    changed_policy = ScriptedPolicy(script)
    fresh = runner.run(changed, changed_policy)
    assert fresh["findings"] and not fresh["errors"] and changed_policy.calls > 0

    for request, expected in ((original, first), (changed, fresh)):
        cached_policy = ScriptedPolicy(script)
        cached = runner.run(request, cached_policy)
        assert cached["findings"] == expected["findings"] and not cached["errors"]
        assert cached_policy.calls == 0


def test_main_writes_the_result_or_the_error(reviewed, tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    output = tmp_path / "result.json"
    request.write_text(json.dumps(request_data(reviewed, tmp_path)))
    monkeypatch.setenv(runner.API_KEY_ENV, "secret-key")
    seen = {}

    def policy(spec, key):
        seen["key"] = key
        return ScriptedPolicy(script)

    monkeypatch.setattr(runner, "make_policy", policy)
    assert runner.main(["run", "--request", str(request), "--output", str(output)]) == 0
    assert seen["key"] == "secret-key"
    text = output.read_text()
    assert len(json.loads(text)["findings"]) == 1 and "secret-key" not in text

    request.write_text(json.dumps(request_data(reviewed, tmp_path, unknown=1)))
    assert runner.main(["run", "--request", str(request), "--output", str(output)]) == 1
    assert "ValidationError" in json.loads(output.read_text())["error"]


def test_make_policy():
    chat = runner.make_policy(runner.ModelSpec(name="openai/m", max_concurrency=3), "k")
    assert isinstance(chat, GatedPolicy) and chat.limit == 3
    assert isinstance(chat.policy, LiteLLMPolicy)
    responses = runner.make_policy(
        runner.ModelSpec(name="m", protocol="responses", api_base="http://x/v1"), "k")
    assert isinstance(responses.policy, ResponsesPolicy)
