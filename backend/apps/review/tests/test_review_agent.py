"""Review Agent 引擎：以独立进程运行 agent，以及引擎配置的读取和保存。"""
import json
import stat
import sys
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.api_auth.authentication import ApiUser, redis_client
from apps.llm.models import LLMProvider
from apps.review import pipeline
from apps.review.engines import ENGINES, engine_for
from apps.review.engines.review_agent import ReviewAgentEngine
from apps.review.models import ReviewEngineConfig
from apps.review.rendering.markers import parse_summary_marker
from apps.webhook.models import Project

from .conftest import git


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
    def test_mock_does_not_require_an_active_model(self, gitlab, review_record, review_payload):
        ReviewEngineConfig.objects.create(engine="mock")
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message
        assert review.is_mock and review.llm_provider == "mock"
        assert review.notification_sent and any("Mock" in body for body in gitlab.bodies)

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

    def test_uses_the_selected_provider_and_default_concurrency(
        self, gitlab, llm, fake_agent, review_record, review_payload
    ):
        model = llm(model="auto/review-model")
        model.model_provider = LLMProvider.objects.create(
            name="Gateway", provider="openai", api_base="http://127.0.0.1:3425/v1",
            api_key="provider-test-key", timeout=45,
        )
        model.save(update_fields=["model_provider"])
        use_agent(tier="low")
        review = run_review(review_record, review_payload)

        assert review.status == "completed", review.error_message
        seen = fake_agent.record()
        assert seen["env"]["REVIEW_AGENT_API_KEY"] == "provider-test-key"
        assert seen["request"]["model"] == {
            "name": "openai/auto/review-model", "api_base": "http://127.0.0.1:3425/v1",
            "timeout": 45, "max_concurrency": 5,
        }

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

    def test_applies_project_rules_to_the_full_local_diff(
        self, gitlab, llm, fake_agent, review_record, review_payload, origin
    ):
        llm()
        use_agent()
        Project.objects.update(exclude_file_types='[".sql"]', ignore_file_patterns='["generated/*"]')
        (origin.work / "schema.sql").write_text("select 1;\n")
        generated = origin.work / "generated"
        generated.mkdir()
        (generated / "types.py").write_text("value = 1\n")
        git(origin.work, "add", ".")
        git(origin.work, "commit", "-m", "Add generated types and schema")
        git(origin.work, "push", str(origin.bare), "HEAD:refs/merge-requests/42/head")
        gitlab._changes["diff_refs"]["head_sha"] = git(origin.work, "rev-parse", "HEAD")
        gitlab._changes["overflow"] = True
        gitlab._changes["changes"] = [{"old_path": "schema.sql", "new_path": "schema.sql", "diff": ""}]
        data = json.loads(fake_agent.result.read_text())
        data["findings"].append(finding(path="generated/types.py", title="排除文件上的问题"))
        fake_agent.result.write_text(json.dumps(data))

        review = run_review(review_record, review_payload)

        assert review.status == "completed", review.error_message
        assert review.files_reviewed_list == ["app.py"] and review.total_files == 1
        assert fake_agent.record()["request"]["excluded_paths"] == ["generated/types.py", "schema.sql"]
        summary = gitlab.plain_notes[0]["body"]
        assert "缺少差异位置的问题会列在总结中" in summary and "初值错误" in summary
        assert "排除文件上的问题" not in summary and gitlab.inline_notes == []

    def test_truncated_diff_with_only_excluded_local_files_skips_agent(
        self, gitlab, llm, fake_agent, review_record, review_payload
    ):
        llm()
        use_agent()
        Project.objects.update(exclude_file_types='[".py"]')
        gitlab._changes["overflow"] = True
        fake_agent.behave("crash")

        review = run_review(review_record, review_payload)

        assert review.status == "completed" and review.total_files == 0
        assert "未进行审查" in review.review_content and gitlab.bodies == []

    def test_partial_results_are_published_but_review_fails(
        self, gitlab, llm, fake_agent, review_record, review_payload
    ):
        llm()
        use_agent()
        data = json.loads(fake_agent.result.read_text())
        data["errors"] = ["C2: private provider detail"]
        fake_agent.result.write_text(json.dumps(data))

        review = run_review(review_record, review_payload)

        assert review.status == "failed" and review.completed_at is None
        assert review.error_message == "审查未完成，1 项调查失败"
        assert review.notification_sent and len(gitlab.inline_notes) == 1
        for summary in (review.review_content, gitlab.plain_notes[0]["body"]):
            assert "审查未完成" in summary and "1 项调查失败" in summary and "初值错误" in summary
            assert "private provider detail" not in summary

    def test_failed_investigation_does_not_discard_previous_summary_findings(
        self, gitlab, llm, fake_agent, review_record, review_payload
    ):
        llm()
        use_agent()
        data = json.loads(fake_agent.result.read_text())
        data["findings"] = [finding(path="calls.py")]
        fake_agent.result.write_text(json.dumps(data))
        assert run_review(review_record, review_payload).status == "completed"
        previous = parse_summary_marker(gitlab.plain_notes[0]["body"])[1]
        assert len(previous) == 1

        data.update(errors=["C1: timeout"], findings=[])
        fake_agent.result.write_text(json.dumps(data))
        review = run_review(review_record, review_payload)
        summary = gitlab.plain_notes[0]["body"]
        assert review.status == "failed" and review.completed_at is None
        assert "审查未完成" in summary and "未再报告" not in summary
        assert parse_summary_marker(summary)[1] == previous

        data["errors"] = []
        fake_agent.result.write_text(json.dumps(data))
        review = run_review(review_record, review_payload)
        assert review.status == "completed" and review.completed_at is not None
        assert review.error_message is None and "未再报告" in gitlab.plain_notes[0]["body"]

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

    @pytest.mark.parametrize("tier", ["high", "xhigh"])
    def test_saved_engine_and_options_are_used(self, llm, tier):
        use_agent(tier=tier)
        engine = engine_for(llm())
        assert engine.kind == "review_agent"
        assert engine.settings["tier"] == tier and engine.settings["max_comments_xhigh"] == 30

    def test_api_lists_engines_and_saves_a_choice(self, llm):
        llm()
        client = APIClient()
        client.force_authenticate(user=ApiUser("test-admin"))
        data = client.get("/api/review/engine/").json()
        assert data["engine"] == "diff_llm" and data["configured"] is False
        agent = data["engines"][0]
        assert agent["kind"] == "review_agent"
        assert data["engines"][1]["label"] == "单次模型审查"
        options = {o["key"]: o for o in agent["options"]}
        assert options["tier"]["choices"] == [["low", "日常"], ["high", "加强"], ["xhigh", "专家"]]
        assert options["tier"]["default"] == "low"
        assert options["max_comments_high"]["advanced"] is True
        assert options["max_concurrency"]["default"] == 5
        assert not options["tier"]["advanced"]

        response = client.put("/api/review/engine/", {
            "engine": "review_agent", "options": {"max_comments_low": "12"}},
            format="json")
        assert response.status_code == 200
        saved = response.json()
        assert saved["engine"] == "review_agent" and saved["configured"] is True
        assert saved["options"]["tier"] == "low"
        assert saved["options"]["max_comments_low"] == 12
        assert saved["options"]["max_concurrency"] == 5
        assert ReviewEngineConfig.objects.count() == 1

    @pytest.mark.parametrize("body,message", [
        (["review_agent"], "配置必须是对象"),
        ({"engine": "codex"}, "不支持的审查引擎"),
        ({"engine": ["review_agent"]}, "不支持的审查引擎"),
        ({"engine": "review_agent", "options": {"tier": "ultra"}}, "不支持的取值"),
        ({"engine": "review_agent", "options": {"tier": ["low"]}}, "不支持的取值"),
        ({"engine": "review_agent", "options": {"max_comments_high": 0}}, "不能小于 1"),
        ({"engine": "review_agent", "options": {"max_comments_high": 2.5}}, "需要整数"),
    ])
    def test_api_rejects_invalid_choices(self, llm, body, message):
        llm()
        client = APIClient()
        client.force_authenticate(user=ApiUser("test-admin"))
        response = client.put("/api/review/engine/", body, format="json")
        assert response.status_code == 400 and message in response.json()["message"]
        assert not ReviewEngineConfig.objects.exists()

    def test_engine_configuration_requires_a_dashboard_session(self, monkeypatch):
        monkeypatch.setattr(redis_client, "get_token", lambda token: "test-admin" if token == "valid-session" else None)
        client = APIClient()
        url = "/api/review/engine/"
        config = {"engine": "review_agent", "options": {"tier": "high"}}
        assert client.get(url).status_code == 401
        assert client.put(url, config, format="json").status_code == 401
        client.cookies["auth_token"] = "valid-session"
        assert client.get(url).status_code == 200
        assert client.put(url, config, format="json").status_code == 403
        assert not ReviewEngineConfig.objects.exists()
        result = client.put(url, config, format="json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert result.status_code == 200 and result.json()["options"]["tier"] == "high"

    def test_every_engine_describes_itself(self):
        for engine in ENGINES.values():
            described = engine.describe()
            assert described["label"] and engine.clean_options({}) is not None
