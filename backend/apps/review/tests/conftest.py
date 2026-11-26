"""审查流程测试的共享替身：内存版 GitLab、真实本地 Git 仓库和假的 Claude CLI。"""
import json
import os
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from gitlab.exceptions import GitlabHttpError

from apps.llm.models import ClaudeCliConfig, GitLabConfig, LLMConfig
from apps.webhook.models import MergeRequestReview, Project

BASE_SOURCE = "def total(items):\n    return sum(items)\n"
HEAD_SOURCE = (
    "def total(items):\n"
    "    result = 0\n"
    "    for item in items:\n"
    "        result += item\n"
    "    return result\n"
)


def git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ["PATH"],
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    ).stdout.strip()


class FakeNotes:
    def __init__(self, mr):
        self.mr = mr

    def create(self, data):
        note = self.mr.add_note(data["body"])
        return SimpleNamespace(asdict=lambda: dict(note), **note)

    def update(self, note_id, data):
        for discussion in self.mr.discussion_store:
            for note in discussion["notes"]:
                if note["id"] == note_id:
                    note["body"] = data["body"]
                    self.mr.updated_notes.append(note_id)
                    return dict(note)
        raise KeyError(note_id)


class FakeDiscussions:
    def __init__(self, mr):
        self.mr = mr

    def list(self, **_kwargs):
        return [SimpleNamespace(attributes=d) for d in self.mr.discussion_store]

    def create(self, data):
        if self.mr.reject_positions:
            raise RuntimeError("line_code 无效")
        note = self.mr.add_note(data["body"], position=data["position"])
        return SimpleNamespace(attributes={"notes": [note]})


class FakeMergeRequest:
    def __init__(self, changes):
        self._changes = changes
        self.discussion_store = []
        self.updated_notes = []
        self.reject_positions = False
        self.next_note_id = 100
        # 草稿评论：supports_drafts=False 模拟没有草稿接口的旧版 GitLab
        self.supports_drafts = True
        self.drafts = []
        self.bulk_publishes = 0
        self.fail_bulk_publish_after = None
        self.notes = FakeNotes(self)
        self.discussions = FakeDiscussions(self)

    def changes(self, **_kwargs):
        return self._changes

    def add_note(self, body, position=None, author_id=99):
        self.next_note_id += 1
        note = {
            "id": self.next_note_id,
            "body": body,
            "system": False,
            "author": {"id": author_id},
            "position": position,
        }
        self.discussion_store.append({"id": str(note["id"]), "notes": [note]})
        return note

    def draft_api(self, method, path, data=None):
        if not self.supports_drafts:
            raise GitlabHttpError("404 Not Found", response_code=404)
        if method == "list":
            return [dict(draft) for draft in self.drafts]
        if method == "delete":
            draft_id = int(path.rsplit("/", 1)[1])
            self.drafts = [d for d in self.drafts if d["id"] != draft_id]
            return None
        if path.endswith("/bulk_publish"):
            self.bulk_publishes += 1
            for count, draft in enumerate(list(self.drafts)):
                if self.fail_bulk_publish_after == count:
                    raise GitlabHttpError("500 Internal Server Error", response_code=500)
                self.add_note(draft["note"], position=draft["position"])
                self.drafts.remove(draft)
            return None
        if self.reject_positions:
            raise GitlabHttpError("400 line_code 无效", response_code=400)
        self.next_note_id += 1
        draft = {"id": self.next_note_id, "note": data["note"], "position": data["position"]}
        self.drafts.append(draft)
        return dict(draft)

    @property
    def bodies(self):
        return [n["body"] for d in self.discussion_store for n in d["notes"]]

    @property
    def inline_notes(self):
        return [n for d in self.discussion_store for n in d["notes"] if n["position"]]

    @property
    def plain_notes(self):
        return [n for d in self.discussion_store for n in d["notes"] if not n["position"]]


@pytest.fixture
def origin(tmp_path):
    """server/org/test-project.git 带一个 MR：main 为基线，feature 为改动。"""
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-b", "main")
    (work / "app.py").write_text(BASE_SOURCE)
    git(work, "add", ".")
    git(work, "commit", "-m", "base")
    base_sha = git(work, "rev-parse", "HEAD")
    git(work, "checkout", "-b", "feature/new-thing")
    (work / "app.py").write_text(HEAD_SOURCE)
    git(work, "commit", "-am", "change")
    head_sha = git(work, "rev-parse", "HEAD")
    raw = git(work, "diff", f"{base_sha}..{head_sha}", "--", "app.py")
    diff = raw[raw.index("@@"):] + "\n"

    server = tmp_path / "server"
    bare = server / "org" / "test-project.git"
    bare.parent.mkdir(parents=True)
    git(tmp_path, "clone", "--bare", str(work), str(bare))
    git(bare, "update-ref", "refs/merge-requests/42/head", head_sha)
    return SimpleNamespace(
        server_url=f"file://{server}",
        bare=bare,
        work=work,
        base_sha=base_sha,
        head_sha=head_sha,
        changes=[{"old_path": "app.py", "new_path": "app.py", "diff": diff}],
    )


@pytest.fixture
def gitlab(monkeypatch, db, origin):
    mr = FakeMergeRequest({
        "changes": origin.changes,
        "diff_refs": {
            "base_sha": origin.base_sha,
            "start_sha": origin.base_sha,
            "head_sha": origin.head_sha,
        },
    })

    class FakeGitlab:
        def __init__(self, *_args, **_kwargs):
            project = SimpleNamespace(
                mergerequests=SimpleNamespace(get=lambda _iid: mr)
            )
            self.projects = SimpleNamespace(get=lambda _id: project)
            self.user = None

        def auth(self):
            self.user = SimpleNamespace(id=99)

        def http_list(self, path, **_kwargs):
            return mr.draft_api("list", path)

        def http_post(self, path, post_data=None, **_kwargs):
            return mr.draft_api("post", path, post_data)

        def http_delete(self, path, **_kwargs):
            return mr.draft_api("delete", path)

    monkeypatch.setattr("apps.review.services.gitlab.Gitlab", FakeGitlab)
    GitLabConfig.objects.create(
        server_url=origin.server_url, private_token="test-token", is_active=True
    )
    Project.objects.create(
        project_id=1,
        project_name="test-project",
        project_path="org/test-project",
        project_url="https://gitlab.example.com/org/test-project",
        namespace="org",
    )
    return mr


@pytest.fixture
def review_payload(webhook_payload):
    webhook_payload["project"]["path_with_namespace"] = "org/test-project"
    webhook_payload["project"].pop("http_url", None)
    return webhook_payload


@pytest.fixture
def webhook_payload():
    return {
        "object_kind": "merge_request",
        "project": {
            "id": 1,
            "name": "test-project",
            "path_with_namespace": "org/test-project",
            "web_url": "https://gitlab.example.com/org/test-project",
        },
        "object_attributes": {
            "iid": 42,
            "title": "feat: add new feature",
            "source_branch": "feature/new-thing",
            "target_branch": "main",
            "description": "A test MR",
            "url": "https://gitlab.example.com/org/test-project/-/merge_requests/42",
            "author": {"name": "test-dev"},
        },
    }


@pytest.fixture
def review_record(db):
    return MergeRequestReview.objects.create(
        project_id=1,
        project_name="test-project",
        merge_request_iid=42,
        merge_request_title="feat: add new feature",
        source_branch="feature/new-thing",
        target_branch="main",
        author_name="test-dev",
        author_email="dev@example.com",
        status="pending",
        request_id="test-request",
    )


@pytest.fixture
def llm(db):
    def configure(provider="deepseek", model="deepseek-chat"):
        return LLMConfig.objects.create(
            provider=provider, model=model, api_key="test-key", is_active=True
        )
    return configure


@pytest.fixture
def fake_claude(tmp_path, monkeypatch, settings):
    """可执行的假 claude：记录工作目录、当前源码和 stdin，再输出 JSON 结果。"""
    settings.REPOSITORY_BASE_PATH = str(tmp_path / "repositories")
    record = tmp_path / "claude-record.json"
    response = tmp_path / "claude-response.txt"
    response.write_text("审查完成，没有发现问题。")
    script = tmp_path / "fake-claude"
    script.write_text(f"""#!{sys.executable}
import json, os, stat, subprocess, sys
if "--help" in sys.argv or "--version" in sys.argv:
    print("fake claude 1.0")
    raise SystemExit(0)
stdin = sys.stdin.read() if stat.S_ISFIFO(os.fstat(0).st_mode) else ""
json.dump({{
    "cwd": os.getcwd(),
    "source": open("app.py").read(),
    "stdin": stdin,
    "argv": sys.argv[1:],
    "env": dict(os.environ),
    "git_config": open(os.path.join(subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True, check=True,
        env={{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}},
    ).stdout.strip(), "config")).read(),
}}, open({str(record)!r}, "w"))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
    "result": open({str(response)!r}).read(), "duration_ms": 10,
    "modelUsage": {{"claude-test": {{}}}}}}))
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    config = ClaudeCliConfig.objects.create(cli_path=str(script), timeout=30, is_active=True)
    return SimpleNamespace(
        path=script,
        config=config,
        response=response,
        record=lambda: json.loads(record.read_text()),
    )
