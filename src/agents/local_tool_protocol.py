"""Strict generalized fenced local tool-call envelope (selection only)."""

from __future__ import annotations

import json
import re
from typing import Any

from src.agents.homeassistant_protocol import HomeAssistantProtocolError
from src.agents.tools.runtime import get_runtime_tools

_FENCE = re.compile(r"```tool_calls\n(?P<payload>.*?)\n```", re.DOTALL)
_MARKER = "```tool_calls"


def parse_local_tool_calls(content: str) -> list[dict[str, Any]] | None:
    """Validate one complete envelope; never execute or resolve a tool call."""
    trimmed = content.strip()
    match = _FENCE.fullmatch(trimmed)
    if match is None:
        if _MARKER in trimmed:
            raise HomeAssistantProtocolError("tool_calls block must be entire output")
        return None
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError as error:
        raise HomeAssistantProtocolError("malformed tool_calls payload") from error
    if not isinstance(payload, dict) or set(payload) != {"calls"} or not isinstance(payload["calls"], list):
        raise HomeAssistantProtocolError("tool_calls payload requires only calls array")
    calls = payload["calls"]
    if not 1 <= len(calls) <= 5:
        raise HomeAssistantProtocolError("tool_calls requires 1 to 5 calls")
    tools = {tool.name: tool for tool in get_runtime_tools()}
    selected: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict) or set(call) != {"name", "args"}:
            raise HomeAssistantProtocolError("each tool call requires only name and args")
        name, args = call["name"], call["args"]
        if not isinstance(name, str) or not isinstance(args, dict) or name not in tools:
            raise HomeAssistantProtocolError("unknown tool or invalid arguments")
        try:
            validated = tools[name].args_schema.model_validate(args).model_dump(exclude_none=False)
        except Exception as error:
            raise HomeAssistantProtocolError("tool arguments violate runtime schema") from error
        selected.append({"name": name, "args": validated, "id": f"local-tool-{index}"})
    return selected


def local_tool_protocol_example() -> str:
    """Canonical shape only; names and schemas remain supplied by runtime prompt."""
    return '```tool_calls\n{"calls":[{"name":"<runtime-tool-name>","args":{}}]}\n```'
