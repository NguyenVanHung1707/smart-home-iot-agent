"""Local HomeMind agent harness with bounded multi-turn tool interaction."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.homeassistant_protocol import (
    HomeAssistantCall,
    HomeAssistantProtocolError,
    parse_homeassistant_call,
)
from src.agents.local_tool_protocol import parse_local_tool_calls
from src.agents.system_prompt import build_system_prompt
from src.agents.tool_routing import is_absolute_calendar_schedule, is_prompt_injection_attempt, tool_needed
from src.agents.tools.runtime import CONTROL_TOOL_NAMES


class ChatModel(Protocol):
    """Protocol representing a chat language model."""

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        """Invoke the chat model asynchronously with a sequence of messages."""
        ...


ToolExecutor = Callable[[HomeAssistantCall], ToolMessage]
NativeToolExecutor = Callable[[dict[str, Any]], ToolMessage]


class LocalAgentHarness:
    """Bounded multi-turn agent harness for local LLMs with tool execution.

    Supports native LangChain tool calls, Home Assistant fenced protocol blocks,
    and structured JSON payloads. Provides informative error feedback to the
    model upon protocol failures to allow natural reasoning and recovery,
    while enforcing strict cycle detection and loop limits.
    """

    def __init__(self, max_tool_call_iterations: int = 3, system_prompt_profile: str | None = None, generic_tool_protocol_enabled: bool = False, tool_retrieval_enabled: bool = False) -> None:
        """Initialize the harness with a maximum number of tool execution turns.

        Args:
            max_tool_call_iterations: Maximum ReAct loop iterations allowed.
        """
        self.max_tool_call_iterations = max(1, max_tool_call_iterations)
        self.system_prompt_profile = system_prompt_profile
        self.generic_tool_protocol_enabled = generic_tool_protocol_enabled
        self.tool_retrieval_enabled = tool_retrieval_enabled

    async def ainvoke(
        self,
        messages: Sequence[BaseMessage],
        *,
        model: ChatModel,
        execute_tool: ToolExecutor,
        execute_native_tool: NativeToolExecutor | None = None,
    ) -> list[BaseMessage]:
        """Run the conversation loop until the model provides a final answer or reaches limits.

        Args:
            messages: Input conversation messages.
            model: Chat model instance.
            execute_tool: Callable to execute a parsed HomeAssistantCall.

        Returns:
            List of generated BaseMessages (AIMessages and ToolMessages).
        """
        history = list(messages)
        if not history or not isinstance(history[0], SystemMessage):
            prompt_query = next((str(message.content) for message in reversed(history) if isinstance(message, HumanMessage)), None)
            history.insert(0, SystemMessage(content=build_system_prompt(profile=self.system_prompt_profile, query=prompt_query if self.tool_retrieval_enabled else None)))

        generated: list[BaseMessage] = []
        seen_calls: set[tuple[str, str, str]] = set()
        local_protocol_profile = self.system_prompt_profile in {"local_tool_first", "qwen_tool_first"}
        user_text = next((str(message.content) for message in reversed(history) if isinstance(message, HumanMessage)), "")
        injection_attempt = is_prompt_injection_attempt(user_text)
        absolute_calendar_schedule = is_absolute_calendar_schedule(user_text)

        def injection_refusal() -> AIMessage:
            return AIMessage(
                content=(
                    "Xin lỗi, tôi không thể bỏ qua quy tắc an toàn hoặc thực hiện yêu cầu này. "
                    "Tôi chỉ có thể hỗ trợ các thao tác nhà thông minh an toàn, hợp lệ."
                )
            )

        def unsupported_schedule_refusal() -> AIMessage:
            return AIMessage(
                content=(
                    "HomeMind chưa hỗ trợ đặt lịch theo ngày hoặc giờ cụ thể qua chat. "
                    "Bạn có thể tạo lịch trong Homing Hub hoặc dùng hẹn giờ đếm ngược như ‘sau 30 phút’."
                )
            )

        for _ in range(self.max_tool_call_iterations):
            response = await model.ainvoke(history)
            history.append(response)
            generated.append(response)

            # 1. Handle native LangChain tool calls if present
            raw_tool_calls: list[dict[str, Any]] = getattr(response, "tool_calls", []) or []
            if raw_tool_calls:
                if injection_attempt:
                    refusal = injection_refusal()
                    history.append(refusal)
                    generated.append(refusal)
                    break
                had_execution = False
                for tool_call in raw_tool_calls:
                    tool_id = tool_call.get("id", "native-tool-call")
                    name = tool_call.get("name", "unknown")
                    args = tool_call.get("args", {})
                    device_id = str(args.get("device_id", args.get("room", "unknown")))
                    action = str(args.get("action", name))
                    value = args.get("value")
                    call_key = (
                        device_id,
                        action,
                        json.dumps(value, sort_keys=True) if isinstance(value, dict) else repr(value),
                    )

                    if call_key in seen_calls:
                        tool_result = ToolMessage(
                            name=name,
                            tool_call_id=tool_id,
                            content=json.dumps(
                                {
                                    "status": "failed",
                                    "message": "Duplicate tool call detected. Please provide the final response.",
                                }
                            ),
                        )
                    elif execute_native_tool is not None:
                        # Native calls retain their selected runtime tool and arguments.
                        # Do not coerce read-only calls into the Home Assistant control
                        # protocol, which only represents device commands.
                        had_execution = True
                        tool_result = execute_native_tool(tool_call)
                    else:
                        seen_calls.add(call_key)
                        had_execution = True
                        ha_call = HomeAssistantCall(
                            device_id=args.get("device_id", "unknown"),
                            action=args.get("action", "set"),
                            value=value if isinstance(value, dict) else None,
                        )
                        tool_result = execute_tool(ha_call)

                    history.append(tool_result)
                    generated.append(tool_result)

                if not had_execution:
                    break
                continue

            # 2. Handle fenced code blocks or JSON tool calls in text content
            content = response.content if isinstance(response.content, str) else str(response.content)
            try:
                local_calls = parse_local_tool_calls(content) if self.generic_tool_protocol_enabled else None
                call = parse_homeassistant_call(content)
            except HomeAssistantProtocolError as error:
                # Provide informative feedback to conversation history so LLM can recover
                feedback = ToolMessage(
                    name="protocol_error",
                    tool_call_id="protocol-error",
                    content=json.dumps(
                        {
                            "status": "invalid_request",
                            "error": error.reason,
                            "instruction": f"Tool protocol error: {error.reason}. Please fix the tool call format or answer the user directly.",
                        }
                    ),
                )
                history.append(feedback)
                generated.append(feedback)
                continue

            if local_calls is not None:
                if execute_native_tool is None:
                    raise HomeAssistantProtocolError("generic local calls require a registered tool executor")
                if injection_attempt:
                    refusal = injection_refusal()
                    history.append(refusal)
                    generated.append(refusal)
                    break
                if absolute_calendar_schedule and any(call["name"] == "set_device_timer" for call in local_calls):
                    refusal = unsupported_schedule_refusal()
                    history.append(refusal)
                    generated.append(refusal)
                    break
                if any(
                    (call["name"] in CONTROL_TOOL_NAMES or call["name"] == "control_smart_device")
                    and call["name"] != "set_device_timer"
                    for call in local_calls
                ) and not tool_needed(user_text):
                    feedback = ToolMessage(
                        name="protocol_error",
                        tool_call_id="protocol-gate",
                        content=json.dumps({"status": "invalid_request", "instruction": "Control calls require a clear imperative."}),
                    )
                    history.append(feedback)
                    generated.append(feedback)
                    continue
                for tool_call in local_calls:
                    call_key = (tool_call["name"], "generic", json.dumps(tool_call["args"], sort_keys=True))
                    if call_key in seen_calls:
                        history.append(ToolMessage(name=tool_call["name"], tool_call_id=tool_call["id"], content='{"status":"failed","message":"Duplicate tool call detected."}'))
                        generated.append(history[-1])
                        continue
                    seen_calls.add(call_key)
                    tool_result = execute_native_tool(tool_call)
                    history.append(tool_result)
                    generated.append(tool_result)
                continue

            if call is None:
                # Model produced text response without tool calls -> conversation turn complete
                break

            if injection_attempt:
                refusal = injection_refusal()
                history.append(refusal)
                generated.append(refusal)
                break

            if local_protocol_profile and user_text and not tool_needed(user_text):
                feedback = ToolMessage(
                    name="protocol_error",
                    tool_call_id="protocol-gate",
                    content=json.dumps({"status": "invalid_request", "instruction": "Do not use a tool for this request."}),
                )
                history.append(feedback)
                generated.append(feedback)
                continue

            call_key = (call.device_id, call.action, repr(call.value))
            if call_key in seen_calls:
                # Cycle detected: pop duplicate tool request and break loop
                generated.pop()
                break

            seen_calls.add(call_key)
            tool_result = execute_tool(call)
            history.append(tool_result)
            generated.append(tool_result)

        return generated
