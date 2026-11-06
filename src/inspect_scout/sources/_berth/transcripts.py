"""Berth transcript import."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from logging import getLogger
from typing import TYPE_CHECKING, Any, AsyncIterator

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
)
from inspect_ai.tool import ToolCall

if TYPE_CHECKING:
    from inspect_scout import Transcript

logger = getLogger(__name__)

BERTH_SOURCE_TYPE = "berth"


async def berth(
    project: str = ".",
    agent: str | None = None,
    group: str | None = None,
    limit: int | None = None,
) -> AsyncIterator["Transcript"]:
    """Read transcripts from a Berth project's agent sessions.

    Args:
        project: Berth project (name, id or path). Defaults to the current directory.
        agent: Only sessions of this Berth tool id (e.g. `claude`, `codex`).
        group: Only sessions of this group (group name or directory name).
        limit: Maximum number of sessions, most recently active first.
    """
    from inspect_scout import Transcript

    args = ["session", "ls", "--json", "--limit", str(limit or 1_000_000)]
    if agent:
        args += ["--agent", agent]
    if group:
        args += ["--group", group]
    for session in _berth(project, args)["sessions"]:
        session_id = session["session_id"]
        try:
            shown = _berth(
                project,
                [
                    "session",
                    "show",
                    session_id,
                    "--agent",
                    session["agent"],
                    "--messages",
                ],
            )
        except RuntimeError as error:
            logger.warning("skipping Berth session %s: %s", session_id, error)
            continue
        if not shown["messages"]:
            continue
        messages = _chat_messages(shown["messages"])
        yield Transcript(
            transcript_id=session_id,
            source_type=BERTH_SOURCE_TYPE,
            source_id=session_id,
            source_uri=session.get("path"),
            date=_iso(session.get("updated_at")),
            task_set=session.get("cwd"),
            task_id=session.get("group_name") or session.get("group"),
            agent=session["agent"],
            message_count=len(messages),
            messages=messages,
            metadata={
                key: session.get(key)
                for key in ("cwd", "group", "group_name", "origin", "title")
            },
        )


def _chat_messages(openai_messages: list[dict[str, Any]]) -> list[ChatMessage]:
    """Berth's OpenAI-format messages to Inspect messages (no `openai` package needed)."""
    messages: list[ChatMessage] = []
    names: dict[str, str] = {}
    for message in openai_messages:
        content = message.get("content") or ""
        if message["role"] == "user":
            messages.append(ChatMessageUser(content=content))
        elif message["role"] == "assistant":
            calls = [
                ToolCall(
                    id=call.get("id") or f"call-{len(messages)}-{index}",
                    function=call["function"]["name"],
                    arguments=_arguments(call["function"]["arguments"]),
                )
                for index, call in enumerate(message.get("tool_calls") or [])
            ]
            names.update((call.id, call.function) for call in calls)
            messages.append(
                ChatMessageAssistant(content=content, tool_calls=calls or None)
            )
        elif message["role"] == "tool":
            call_id = message.get("tool_call_id")
            messages.append(
                ChatMessageTool(
                    content=content,
                    tool_call_id=call_id,
                    function=names.get(call_id or ""),
                )
            )
    return messages


def _arguments(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {"input": arguments}
    return parsed if isinstance(parsed, dict) else {"input": parsed}


def _berth(project: str, args: list[str]) -> Any:
    """Run the Berth CLI (`BERTH_CLI` overrides the binary) and parse its JSON output."""
    binary = os.environ.get("BERTH_CLI", "berth")
    result = subprocess.run(
        [binary, "project", project, *args], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())
    return json.loads(result.stdout)


def _iso(updated_at_ms: int | None) -> str | None:
    if updated_at_ms is None:
        return None
    return datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc).isoformat()
