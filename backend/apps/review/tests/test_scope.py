"""审查范围：被排除的文件不进入审查，但引擎仍能读取完整工作区。"""
import json
from unittest.mock import patch

import pytest

from apps.review import pipeline
from apps.review.diff_index import DiffIndex
from apps.review.engines.base import Finding
from apps.review.postprocess import finalize_findings
from apps.review.scope import ReviewScope
from apps.webhook.models import Project

SQL_CHANGE = {
    "old_path": "db/schema.sql", "new_path": "db/schema.sql",
    "diff": "@@ -0,0 +1 @@\n+drop table orders;\n",
}


def run(review, payload):
    pipeline.run(review.pk, payload)
    review.refresh_from_db()
    return review


def output(*findings):
    text = json.dumps({"summary": "总结", "overview": "概览", "findings": list(findings)}, ensure_ascii=False)
    return {"choices": [{"message": {"content": f"```json\n{text}\n```"}}]}


def project(**rules):
    item = Project.objects.filter(project_id=1).first() or Project(
        project_id=1, project_name="p", project_path="org/p",
        project_url="https://gitlab.example.com/org/p", namespace="org",
    )
    item.exclude_file_types_list = rules.get("exclude", [])
    item.ignore_file_patterns_list = rules.get("ignore", [])
    item.save()
    return item


@pytest.mark.parametrize("pattern,path,allowed", [
    (".md", "docs/guide.md", False),
    (".md", "src/parse.mdl.py", True),
    (".github", ".github/workflows/ci.py", False),
    ("vendor/", "third/vendor/lib.py", False),
    ("vendor/*", "vendor/a/b.py", False),
    ("*_pb2.py", "api/user_pb2.py", False),
    ("*_pb2.py", "api/user.py", True),
])
def test_ignore_patterns(pattern, path, allowed):
    assert ReviewScope(ignore_patterns=(pattern,)).allows(path) is allowed


def test_empty_rules_do_not_exclude_everything(db, settings):
    settings.EXCLUDE_FILE_TYPES = [""]
    settings.IGNORE_FILE_TYPES = [" "]
    assert ReviewScope.for_project(1).allows("app.py")


@pytest.mark.django_db
def test_project_rules_override_global_rules(settings):
    settings.EXCLUDE_FILE_TYPES = [".py"]
    settings.IGNORE_FILE_TYPES = []
    project(exclude=[".sql"])
    scope = ReviewScope.for_project(1)
    assert scope.allows("app.py")
    assert not scope.allows("a.sql")


def test_default_settings_keep_source_code_in_scope(settings):
    scope = ReviewScope(tuple(settings.EXCLUDE_FILE_TYPES), tuple(settings.IGNORE_FILE_TYPES))
    assert all(scope.allows(path) for path in ("a.py", "a.go", "a.java", "a.vue", "a.cpp"))


def test_findings_on_excluded_files_are_dropped_but_renames_stay():
    rename = {"old_path": "old.sql", "new_path": "new.py", "diff": "@@ -1 +1 @@\n-a\n+b\n"}
    scope = ReviewScope(exclude_types=(".sql",))
    kept = finalize_findings([
        Finding(path="db/schema.sql", title="排除文件"),
        Finding(path="old.sql", title="重命名旧路径", side="old", start_line=1, end_line=1),
    ], DiffIndex([rename]), scope)
    assert [finding.title for finding in kept] == ["重命名旧路径"]


@pytest.mark.django_db
class TestPipelineScope:
    def test_excluded_files_are_not_sent_or_reported(self, gitlab, llm, review_record, review_payload):
        llm()
        project(exclude=[".sql"])
        gitlab._changes["changes"] = [*gitlab._changes["changes"], SQL_CHANGE]
        finding = {"path": "db/schema.sql", "severity": "critical", "title": "不应出现", "body": "x"}
        with patch("unionllm.unionchat", return_value=output(finding)) as call:
            review = run(review_record, review_payload)
        prompt = call.call_args.kwargs["messages"][0]["content"]
        assert "drop table" not in prompt
        assert review.status == "completed"
        assert review.files_reviewed_list == ["app.py"]
        assert not any("不应出现" in body for body in gitlab.bodies)

    def test_all_excluded_skips_the_engine(self, gitlab, llm, review_record, review_payload):
        llm()
        project(exclude=[".sql"])
        gitlab._changes["changes"] = [SQL_CHANGE]
        with patch("unionllm.unionchat") as call:
            review = run(review_record, review_payload)
        call.assert_not_called()
        assert review.status == "completed"
        assert "排除范围" in review.review_content
        assert gitlab.bodies == []

    def test_worktree_engine_keeps_full_context(
        self, gitlab, llm, review_record, review_payload, fake_claude, origin
    ):
        llm(provider="claude", model="claude")
        project(ignore=["app_config.py"])
        gitlab._changes["changes"] = [
            *gitlab._changes["changes"],
            {"old_path": "app_config.py", "new_path": "app_config.py",
             "diff": "@@ -0,0 +1 @@\n+SECRET_FLAG = 1\n"},
        ]
        review = run(review_record, review_payload)
        assert review.status == "completed"
        record = fake_claude.record()
        assert "app_config.py" in record["stdin"]
        assert "不要针对它们报告问题" in record["stdin"]
        assert "SECRET_FLAG" not in record["stdin"]
        assert record["source"]


def test_prefix_alias_cannot_bypass_an_exclusion():
    included = {"old_path": "private.py", "new_path": "private.py", "diff": "@@ -1 +1 @@\n-a\n+b\n"}
    scope = ReviewScope(ignore_patterns=("b/private.py",))
    kept = finalize_findings([Finding(path="b/private.py", title="被排除的文件", end_line=1)],
                             DiffIndex([included]), scope)
    assert kept == []
