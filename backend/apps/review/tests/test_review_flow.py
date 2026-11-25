"""固定三条审查路径对外的行为：状态流转、路径选择、失败处理和回写。"""
from unittest.mock import patch

import pytest

from apps.llm.models import LLMConfig, WebhookEventRule
from apps.webhook.models import Project, ProjectWebhookEventPrompt
from .conftest import HEAD_SOURCE


def run_review(review, payload, rule=None):
    from apps.review import pipeline

    pipeline.run(review.pk, payload, rule)
    review.refresh_from_db()
    return review


def completion(text):
    return {"choices": [{"message": {"content": text}}]}


@pytest.mark.django_db
class TestMockPath:
    def test_completes_without_calling_a_model(self, gitlab, llm, review_record, review_payload):
        llm(provider="mock", model="mock")
        with patch("unionllm.unionchat") as unionchat:
            review = run_review(review_record, review_payload)
        unionchat.assert_not_called()
        assert review.status == "completed"
        assert review.is_mock is True
        assert (review.llm_provider, review.llm_model) == ("mock", "mock")
        assert review.total_files == 1
        assert review.review_content
        assert review.notification_sent is True
        assert gitlab.bodies


@pytest.mark.django_db
class TestApiPath:
    def test_sends_diff_and_mr_to_the_configured_model(
        self, gitlab, llm, review_record, review_payload
    ):
        llm()
        with patch("unionllm.unionchat", return_value=completion("审查结果正文")) as unionchat:
            review = run_review(review_record, review_payload)
        kwargs = unionchat.call_args.kwargs
        prompt = kwargs["messages"][0]["content"]
        assert kwargs["model"] == "deepseek/deepseek-chat"
        assert "feat: add new feature" in prompt
        assert "+    result = 0" in prompt
        assert review.status == "completed"
        assert review.is_mock is False
        assert (review.llm_provider, review.llm_model) == ("deepseek", "deepseek-chat")
        assert "审查结果正文" in review.review_content
        assert any("审查结果正文" in body for body in gitlab.bodies)

    def test_falls_back_to_litellm(self, gitlab, llm, review_record, review_payload):
        llm()
        message = type("M", (), {"content": "回退结果"})
        response = type("R", (), {"choices": [type("C", (), {"message": message})]})
        with patch("unionllm.unionchat", side_effect=RuntimeError("down")), patch(
            "litellm.completion", return_value=response
        ):
            review = run_review(review_record, review_payload)
        assert review.status == "completed"
        assert "回退结果" in review.review_content

    def test_fails_when_every_client_fails(self, gitlab, llm, review_record, review_payload):
        llm()
        with patch("unionllm.unionchat", side_effect=RuntimeError("down")), patch(
            "litellm.completion", side_effect=RuntimeError("down")
        ):
            review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "均调用失败" in review.error_message
        assert not gitlab.bodies

    def test_uses_the_project_prompt_of_the_matched_rule(
        self, gitlab, llm, review_record, review_payload
    ):
        llm()
        rule = WebhookEventRule.objects.create(
            name="mr-open", event_type="merge_request", match_rules={}, is_active=True
        )
        ProjectWebhookEventPrompt.objects.create(
            project=Project.objects.get(project_id=1),
            event_rule=rule,
            custom_prompt="只看 {title} 的安全问题",
            use_custom=True,
        )
        with patch("unionllm.unionchat", return_value=completion("结果")) as unionchat:
            run_review(review_record, review_payload, rule)
        prompt = unionchat.call_args.kwargs["messages"][0]["content"]
        assert "只看 feat: add new feature 的安全问题" in prompt
        # 自定义要求只替换审查重点，diff 和输出格式仍由平台追加
        assert "+    result = 0" in prompt
        assert '"findings"' in prompt
        assert "你是一位资深代码审查专家" not in prompt


@pytest.mark.django_db
class TestClaudePath:
    def test_runs_in_a_checkout_of_the_mr(
        self, gitlab, llm, fake_claude, review_record, review_payload
    ):
        llm(provider="claude", model="claude")
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message
        assert review.llm_provider == "claude-cli"
        record = fake_claude.record()
        assert record["source"] == HEAD_SOURCE
        assert "+    result = 0" in record["stdin"]
        assert record["argv"][:3] == ["-p", "--output-format", "json"]
        assert record["argv"][3:7] == ["--setting-sources", "user", "--strict-mcp-config", "--disallowedTools"]
        assert "Bash" in record["argv"][7] and "Edit" in record["argv"][7]
        assert "test-token" not in record["git_config"]
        assert any("审查完成" in body for body in gitlab.bodies)

    def test_fails_when_the_repository_is_unavailable(
        self, gitlab, llm, fake_claude, review_record, review_payload, origin
    ):
        llm(provider="claude", model="claude")
        review_payload["project"]["path_with_namespace"] = "org/missing"
        review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "仓库" in review.error_message

    def test_cli_gets_only_the_environment_it_needs(
        self, gitlab, llm, fake_claude, review_record, review_payload, monkeypatch
    ):
        import os
        monkeypatch.setenv("DJANGO_SECRET_KEY", "server-secret")
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.internal:3128")
        llm(provider="claude", model="claude")
        fake_claude.config.anthropic_auth_token = "claude-token"
        fake_claude.config.save()
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message
        env = fake_claude.record()["env"]
        assert "DJANGO_SECRET_KEY" not in env and "REDIS_URL" not in env
        assert env["ANTHROPIC_AUTH_TOKEN"] == "claude-token"
        assert env["HTTPS_PROXY"] == "http://proxy.internal:3128"
        assert env["HOME"] != os.path.expanduser("~")
        assert not os.path.exists(env["HOME"])

    def test_relative_cli_path_is_resolved_before_entering_the_checkout(
        self, gitlab, llm, fake_claude, review_record, review_payload
    ):
        import os
        llm(provider="claude", model="claude")
        fake_claude.config.cli_path = os.path.relpath(fake_claude.path)
        fake_claude.config.save()
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message

    def test_empty_cli_result_is_a_failure(
        self, gitlab, llm, fake_claude, review_record, review_payload
    ):
        llm(provider="claude", model="claude")
        fake_claude.response.write_text("  ")
        review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "没有返回审查内容" in review.error_message
        assert not gitlab.bodies

    def test_fails_when_the_cli_is_missing(
        self, gitlab, llm, fake_claude, review_record, review_payload
    ):
        llm(provider="claude", model="claude")
        fake_claude.config.cli_path = "/nonexistent/claude"
        fake_claude.config.save()
        review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "not found" in review.error_message.lower()
        assert not gitlab.bodies


@pytest.mark.django_db
class TestPayload:
    def test_null_fields_in_the_payload_do_not_break_the_review(
        self, gitlab, llm, review_record, review_payload
    ):
        llm(provider="mock", model="mock")
        review_payload["object_attributes"]["author"] = None
        review_payload["object_attributes"]["title"] = None
        review = run_review(review_record, review_payload)
        assert review.status == "completed", review.error_message


@pytest.mark.django_db
class TestFailureHandling:
    def test_without_an_active_model(self, gitlab, review_record, review_payload):
        LLMConfig.objects.all().delete()
        review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "未找到有效的 LLM 配置" in review.error_message

    def test_without_changes(self, gitlab, llm, review_record, review_payload):
        llm()
        gitlab._changes = None
        review = run_review(review_record, review_payload)
        assert review.status == "failed"
        assert "未找到MR变更信息" in review.error_message
