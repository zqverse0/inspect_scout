"""从 Berth 读一个会话：`berth project <p> session show <id> --messages`（OpenAI chat 格式）→ Transcript。

会话解析归 Berth（各 Agent 的 sessions.json），这里只做格式映射。`BERTH_CLI` 可覆盖 berth 可执行文件。
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from ._ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ToolCall,
)
from ._transcript.types import Transcript


def chat_messages(openai_messages: list[dict[str, Any]]) -> list[ChatMessage]:
    """OpenAI chat 消息 → 消息对象；消息 id 为 m1、m2…（结果里的引用指回第几条）。"""
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
    for index, chat in enumerate(messages, start=1):
        chat.id = f"m{index}"
    return messages


def _arguments(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {"input": arguments}
    return parsed if isinstance(parsed, dict) else {"input": parsed}


def load_session(
    session_id: str, *, project: str = ".", agent: str | None = None
) -> Transcript:
    args = ["session", "show", session_id, "--messages"] + (
        ["--agent", agent] if agent else []
    )
    shown = _berth(project, args)
    return Transcript(
        transcript_id=session_id,
        source_type="berth",
        source_id=session_id,
        source_uri=shown.get("path"),
        task_set=shown.get("cwd"),
        agent=shown.get("agent"),
        messages=chat_messages(shown["messages"]),
        message_count=len(shown["messages"]),
    )


def _berth(project: str, args: list[str]) -> Any:
    binary = os.environ.get("BERTH_CLI", "berth")
    result = subprocess.run(
        [binary, "project", project, *args], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())
    return json.loads(result.stdout)
