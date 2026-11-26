"""用真实的 python-gitlab 客户端对接本地 HTTP 桩，核对发布请求的形状。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from apps.llm.models import GitLabConfig
from apps.review.services import DraftNotesUnsupported, GitlabService

MR_PATH = "/api/v4/projects/1/merge_requests/42"


@pytest.fixture
def gitlab_stub():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _reply(self, payload, status=200):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw)

        def do_GET(self):
            path = self.path.split("?")[0]
            calls.append(("GET", self.path, None))
            if path == "/api/v4/user":
                self._reply({"id": 99, "username": "bot"})
            elif path == "/api/v4/projects/1":
                self._reply({"id": 1})
            elif path == MR_PATH:
                self._reply({"id": 500, "iid": 42, "project_id": 1})
            elif path == f"{MR_PATH}/discussions":
                self._reply([{"id": "d1", "notes": [{"id": 7, "body": "x", "author": {"id": 99}}]}])
            elif path == f"{MR_PATH}/draft_notes":
                self._reply([{"id": 3, "note": "草稿"}])
            elif path == f"{MR_PATH}/versions":
                self._reply([{
                    "id": 3, "base_commit_sha": "b", "start_commit_sha": "s", "head_commit_sha": "h",
                }])
            else:
                self._reply({"message": "not found"}, 404)

        def do_POST(self):
            body = self._body()
            calls.append(("POST", self.path, body))
            if self.path.endswith("/bulk_publish"):
                self.send_response(204)
                self.end_headers()
            elif self.path.endswith("/draft_notes"):
                self._reply({"id": 4, "note": body.get("note")}, 201)
            else:
                self._reply({"id": "d2", "notes": [{"id": 8, "body": body.get("body")}]}, 201)

        def do_DELETE(self):
            calls.append(("DELETE", self.path, None))
            self.send_response(204)
            self.end_headers()

        def do_PUT(self):
            body = self._body()
            calls.append(("PUT", self.path, body))
            self._reply({"id": 7, "body": body.get("body")})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", calls
    server.shutdown()


@pytest.mark.django_db
def test_real_client_sends_the_expected_requests(gitlab_stub):
    url, calls = gitlab_stub
    GitLabConfig.objects.create(server_url=url, private_token="test-token", is_active=True)
    service = GitlabService(request_id="t")
    position = {
        "position_type": "text", "base_sha": "b", "start_sha": "s", "head_sha": "h",
        "old_path": "a.py", "new_path": "a.py", "new_line": 3,
    }

    assert service.current_user_id == 99
    assert service.list_merge_request_discussions(1, 42)[0]["notes"][0]["id"] == 7
    assert service.get_latest_diff_refs(1, 42) == {
        "base_sha": "b", "start_sha": "s", "head_sha": "h",
    }
    service.create_merge_request_discussion(1, 42, "行内评论", position)
    service.update_merge_request_note(1, 42, 7, "新总结")

    post = next(c for c in calls if c[0] == "POST")
    assert post[1] == f"{MR_PATH}/discussions"
    assert post[2] == {"body": "行内评论", "position": position}
    put = next(c for c in calls if c[0] == "PUT")
    assert put[1] == f"{MR_PATH}/notes/7" and put[2] == {"body": "新总结"}


@pytest.mark.django_db
def test_real_client_sends_the_draft_note_requests(gitlab_stub):
    url, calls = gitlab_stub
    GitLabConfig.objects.create(server_url=url, private_token="test-token", is_active=True)
    service = GitlabService(request_id="t")
    position = {"position_type": "text", "base_sha": "b", "start_sha": "s", "head_sha": "h",
                "old_path": "a.py", "new_path": "a.py", "new_line": 3}

    assert service.list_draft_notes(1, 42) == [{"id": 3, "note": "草稿"}]
    service.delete_draft_note(1, 42, 3)
    service.create_draft_note(1, 42, "行内评论", position)
    service.publish_draft_notes(1, 42)
    with pytest.raises(DraftNotesUnsupported):
        service.list_draft_notes(2, 42)

    writes = [(method, path, body) for method, path, body in calls if method != "GET"]
    assert writes == [
        ("DELETE", f"{MR_PATH}/draft_notes/3", None),
        ("POST", f"{MR_PATH}/draft_notes", {"note": "行内评论", "position": position}),
        ("POST", f"{MR_PATH}/draft_notes/bulk_publish", {}),
    ]
