"""Tests for the Berth source: a fake `berth` CLI stands in for the real one."""

import json
import sys
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool
from inspect_scout.sources import berth

SESSIONS = {
    "sessions": [
        {
            "agent": "codex",
            "session_id": "s1",
            "cwd": "/w",
            "group": "main",
            "group_name": "w",
            "origin": "berth",
            "path": "/s1.jsonl",
            "title": "fix",
            "updated_at": 1_700_000_000_000,
        },
        {"agent": "claude", "session_id": "gone", "cwd": "/w", "updated_at": 1},
    ]
}
SHOWN = {
    "messages": [
        {"role": "user", "content": "fix the bug"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "shell", "arguments": '{"cmd": "ls"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "a.rs"},
        {"role": "assistant", "content": "done"},
    ]
}

FAKE = """#!{python}
import json, sys
from pathlib import Path
here = Path(__file__).parent
args = sys.argv[1:]
with open(here / "calls.jsonl", "a") as calls:
    calls.write(json.dumps(args) + "\\n")
if args[2:4] == ["session", "ls"]:
    print((here / "sessions.json").read_text())
elif args[4] == "s1":
    print((here / "shown.json").read_text())
else:
    print(json.dumps({{"error": {{"kind": "not_found"}}}}))
    sys.exit(4)
"""


@pytest.mark.asyncio
async def test_berth_maps_sessions_and_skips_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sessions.json").write_text(json.dumps(SESSIONS))
    (tmp_path / "shown.json").write_text(json.dumps(SHOWN))
    fake = tmp_path / "berth"
    fake.write_text(FAKE.format(python=sys.executable))
    fake.chmod(0o755)
    monkeypatch.setenv("BERTH_CLI", str(fake))

    transcripts = [t async for t in berth(project="w", agent="codex", limit=5)]

    calls = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert calls[0] == [
        "project",
        "w",
        "session",
        "ls",
        "--json",
        "--limit",
        "5",
        "--agent",
        "codex",
    ]
    assert len(transcripts) == 1
    t = transcripts[0]
    assert (t.transcript_id, t.agent, t.task_set, t.task_id) == (
        "s1",
        "codex",
        "/w",
        "w",
    )
    assert t.metadata["title"] == "fix"
    assert [m.role for m in t.messages] == ["user", "assistant", "tool", "assistant"]
    assistant, tool = t.messages[1], t.messages[2]
    assert isinstance(assistant, ChatMessageAssistant) and assistant.tool_calls
    call = assistant.tool_calls[0]
    assert (call.id, call.function, call.arguments) == ("c1", "shell", {"cmd": "ls"})
    assert isinstance(tool, ChatMessageTool)
    assert (tool.tool_call_id, tool.function) == ("c1", "shell")
