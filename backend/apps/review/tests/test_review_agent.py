"""Review Agent 引擎：以独立进程运行 agent，以及引擎配置的读取和保存。"""
import json
import stat
import sys
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.review import pipeline
from apps.review.engines import ENGINES, engine_for
from apps.review.engines.review_agent import ReviewAgentEngine
from apps.review.models import ReviewEngineConfig


def finding(**extra):
    return {
        "path": "app.py", "side": "new", "start_line": 2, "end_line": 2,
        "existing_code": "result = 0", "severity": "major", "category": "defect",
        "title": "初值错误", "body": "求和从 0 开始会漏掉负数情况。", "condition": None,
        "also": [], **extra,
    }


@pytest.fixture
def fake_agent(tmp_path, settings):
    """可执行的假 Python：记录收到的请求和环境变量，再按预设写出结果。"""
    settings.REPOSITORY_BASE_PATH = str(tmp_path / "repositories")
    settings.REVIEW_AGENT_STATE_DIR = str(tmp_path / "agent-state")
    record = tmp_path / "agent-record.json"
    result = tmp_path / "agent-result.json"
    behaviour = tmp_path / "agent-behaviour"
    result.write_text(json.dumps({
        "version": "review-agent-result/v1", "findings": [finding()], "dropped": 3,
        "usage": {"input_tokens": 10, "output_tokens": 2}, "duration_s": 1.5, "errors": [],
    }, ensure_ascii=False))
    script = tmp_path / "agent-python"
    script.write_text(f"""#!{sys.executable}
import json, os, subprocess, sys, time
args = sys.argv[1:]
request = json.load(open(args[args.index("--request") + 1]))
output = args[args.index("--output") + 1]
json.dump({{"argv": args, "request": request, "env": dict(os.environ),
           "files": subprocess.run(["git", "-C", request["repository"], "cat-file", "-t",
                                     request["head_sha"]], capture_output=True, text=True).stdout.strip()}},
          open({str(record)!r}, "w"))
behaviour = open({str(behaviour)!r}).read() if os.path.exists({str(behaviour)!r}) else ""
if behaviour == "sleep":
    time.sleep(30)
if behaviour == "crash":
    sys.exit(3)
if behaviour == "error":
    json.dump({{"version": "review-agent-result/v1", "error": "ValueError: 模型返回格式错误"}}, open(output, "w"))
    sys.exit(1)
open(output, "w").write(open({str(result)!r}).read())
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    settings.REVIEW_AGENT_PYTHON = str(script)
    return SimpleNamespace(record=lambda: json.loads(record.read_text()), result=result,
                           behave=behaviour.write_text)


def use_agent(**options):
    ReviewEngineConfig.objects.create(engine="review_agent", options=options)


def run_review(review, payload):
    pipeline.run(review.pk, payload)
    review.refresh_from_db()
    return review


@pytest.mark.django_db
class TestPipeline:
    def test_runs_the_agent_on_the_mr_checkout(self, gitlab, llm, fake_agent, review_record,
                                               review_payload, origin, monkeypatch):
        llm()
        use_agent(tier="low", max_comments_low=7, max_concurrency=4)
        monkeypatch.setenv("SECRET_FROM_SERVER", "do-not-pass")
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message
        assert review.llm_provider == "review-agent"
        seen = fake_agent.record()
        request = seen["request"]
        assert seen["argv"][:2] == ["-m", "review_agent.run"]
        assert seen["files"] == "commit"  # the checkout holds the MR's head commit
        assert (request["base_sha"], request["head_sha"]) == (origin.base_sha, origin.head_sha)
        assert request["config"] == {"tier": "low", "language": "zh-CN",
                                     "postprocess": {"final_review": {"max_comments": 7}}}
        assert request["model"]["name"] == "deepseek/deepseek-chat"
        assert request["model"]["max_concurrency"] == 4
        assert "test-key" not in json.dumps(request)
        assert seen["env"]["REVIEW_AGENT_API_KEY"] == "test-key"
        assert "SECRET_FROM_SERVER" not in seen["env"]
        assert len(gitlab.inline_notes) == 1 and "初值错误" in gitlab.inline_notes[0]["body"]

    def test_condition_and_repeats_are_shown_in_the_comment(self, gitlab, llm, fake_agent,
                                                            review_record, review_payload):
        llm()
        use_agent()
        data = json.loads(fake_agent.result.read_text())
        data["findings"] = [finding(condition="列表含负数时", also=[
            {"path": "lib/sum.py", "side": "new", "start_line": 8, "end_line": 8}])]
        fake_agent.result.write_text(json.dumps(data, ensure_ascii=False))
        run_review(review_record, review_payload)
        body = gitlab.inline_notes[0]["body"]
        assert "**触发条件**：列表含负数时" in body
        assert "同样的问题还出现在：`lib/sum.py:8`" in body

    @pytest.mark.parametrize("behaviour,message", [
        ("error", "模型返回格式错误"), ("crash", "Review Agent 运行失败")])
    def test_agent_failures_fail_the_review(self, gitlab, llm, fake_agent, review_record,
                                            review_payload, behaviour, message):
        llm()
        use_agent()
        fake_agent.behave(behaviour)
        review = run_review(review_record, review_payload)
        assert review.status == "failed" and message in review.error_message
        assert gitlab.bodies == []

    def test_timeout_kills_the_agent(self, gitlab, llm, fake_agent, review_record,
                                     review_payload, monkeypatch):
        llm()
        use_agent(timeout=60)
        fake_agent.behave("sleep")
        monkeypatch.setattr(ReviewAgentEngine, "options", tuple(
            option if option.key != "timeout" else type(option)(**{**option.__dict__, "minimum": 1})
            for option in ReviewAgentEngine.options))
        ReviewEngineConfig.objects.update(options={"timeout": 1})
        review = run_review(review_record, review_payload)
        assert review.status == "failed" and "超时" in review.error_message

    def test_missing_runtime_is_reported(self, gitlab, llm, fake_agent, review_record,
                                         review_payload, settings, tmp_path):
        llm()
        use_agent()
        settings.REVIEW_AGENT_PYTHON = str(tmp_path / "missing" / "python")
        review = run_review(review_record, review_payload)
        assert review.status == "failed" and "未找到 Review Agent 的运行环境" in review.error_message


@pytest.mark.django_db
class TestEngineConfig:
    def test_without_a_saved_config_the_provider_decides(self, llm):
        assert engine_for(llm(provider="claude")).kind == "claude_code"
        assert engine_for(llm(provider="mock")).kind == "mock"

    def test_saved_engine_and_options_are_used(self, llm):
        use_agent(tier="xhigh")
        engine = engine_for(llm())
        assert engine.kind == "review_agent"
        assert engine.settings["tier"] == "xhigh" and engine.settings["max_comments_xhigh"] == 30

    def test_api_lists_engines_and_saves_a_choice(self, llm):
        llm()
        client = APIClient()
        data = client.get("/api/review/engine/").json()
        assert data["engine"] == "diff_llm" and data["configured"] is False
        agent = next(e for e in data["engines"] if e["kind"] == "review_agent")
        options = {o["key"]: o for o in agent["options"]}
        assert options["tier"]["choices"] == [["low", "快速"], ["high", "标准"], ["xhigh", "深入"]]
        assert options["max_comments_high"]["advanced"] is True
        assert not options["tier"]["advanced"]

        response = client.put("/api/review/engine/", {
            "engine": "review_agent", "options": {"tier": "low", "max_comments_low": "12"}},
            format="json")
        assert response.status_code == 200
        saved = response.json()
        assert saved["engine"] == "review_agent" and saved["configured"] is True
        assert saved["options"]["max_comments_low"] == 12
        assert ReviewEngineConfig.objects.count() == 1

    @pytest.mark.parametrize("body,message", [
        ({"engine": "codex"}, "不支持的审查引擎"),
        ({"engine": "review_agent", "options": {"tier": "ultra"}}, "不支持的取值"),
        ({"engine": "review_agent", "options": {"max_comments_high": 0}}, "不能小于 1"),
        ({"engine": "review_agent", "options": {"max_comments_high": 2.5}}, "需要整数"),
    ])
    def test_api_rejects_invalid_choices(self, llm, body, message):
        llm()
        response = APIClient().put("/api/review/engine/", body, format="json")
        assert response.status_code == 400 and message in response.json()["message"]
        assert not ReviewEngineConfig.objects.exists()

    def test_every_engine_describes_itself(self):
        for engine in ENGINES.values():
            described = engine.describe()
            assert described["label"] and engine.clean_options({}) is not None
