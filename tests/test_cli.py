from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from review_core.cli import main
from review_core.intel.tools import Tools


def test_cli_snapshot_tool_triage_and_plan(reviewed, tmp_path, capsys):
    _, workspace, _ = reviewed
    shared = ["--state-dir", str(tmp_path / "state")]
    arguments = ["tool", "--snapshot", workspace.snapshot.id, "outline"]
    assert main([*shared, *arguments, "--arguments", '{"path":"users.py"}']) == 0
    tool = json.loads(capsys.readouterr().out)
    assert tool["items"][0]["name"] == "get_user"
    assert main([*shared, "triage", "--snapshot", workspace.snapshot.id]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["clusters"] and plan["coverage"]["reviewed_units"]
    assert main([*shared, "plan", "--snapshot", workspace.snapshot.id, "--id", plan["id"]]) == 0
    assert json.loads(capsys.readouterr().out) == plan
    assert main([*shared, "plan", "--snapshot", workspace.snapshot.id, "--id", "missing"]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_rejects_invalid_triage_config(reviewed, tmp_path, capsys):
    _, workspace, _ = reviewed
    config = tmp_path / "config.json"
    config.write_text('{"floor_tokens": 10, "cap_tokens": 5}')
    shared = ["--state-dir", str(tmp_path / "state")]
    assert main([*shared, "triage", "--snapshot", workspace.snapshot.id, "--config", str(config)])
    assert "floor_tokens" in json.loads(capsys.readouterr().err)["error"]


def test_installed_console_entrypoint():
    executable = Path(sys.executable).parent / "review-core"
    result = subprocess.run([str(executable), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "snapshot" in result.stdout


def test_tool_schema_inputs_reject_unknown_fields(reviewed):
    tools = Tools(reviewed[2])
    result = tools.call("outline", path="users.py", execute_shell="anything")
    assert result.error.startswith("Invalid tool arguments: execute_shell")
    assert all(
        schema["function"]["parameters"]["additionalProperties"] is False
        for schema in tools.schemas()
    )
