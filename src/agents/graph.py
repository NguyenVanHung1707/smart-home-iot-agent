"""LangGraph agent with ReAct pattern for Homing Hub.

Two operational modes:
  1. **ReAct** (LLM_ENABLED=true): LLM decides which tools to call,
     observes results, and continues reasoning until it has a final answer.
  2. **Deterministic fallback** (LLM_ENABLED=false): keyword-based routing
     via ``fallback_node`` — no LLM calls at all.

The compiled ``agent`` at module level is the singleton used by API routes.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agents.homeassistant_protocol import (
    HomeAssistantProtocolError,
    execute_homeassistant_call,
    parse_homeassistant_call,
)
from src.agents.local_protocol_grammar import LOCAL_HOMEASSISTANT_GRAMMAR, LOCAL_TOOL_CALLS_GRAMMAR
from src.agents.local_tool_protocol import parse_local_tool_calls
from src.agents.nodes.typed_stages import (
    clarify,
    execute,
    interpret,
    load_context,
    persist_trace,
    policy,
    resolve,
    respond,
    validate,
    verify,
)
from src.agents.rollout import select_agent
from src.agents.state import AgentState, InterpretationStatus, TypedAgentState
from src.agents.system_prompt import build_system_prompt
from src.agents.tool_routing import (
    is_absolute_calendar_schedule,
    is_prompt_injection_attempt,
    tool_needed,
)
from src.agents.tools import CONTROL_TOOL_NAMES, TOOLS
from src.config import get_settings
from src.services.natural_language_control import (
    handle_natural_home_request,
    informational_remainder,
    should_handle_natural_home_request,
)

logger = logging.getLogger(__name__)

# Maximum ReAct iterations (agent → tools → agent → …) to prevent runaway.
_MAX_ITERATIONS = 5
_MAX_DEVICE_COMMANDS = 5
_DEVICE_COMMAND_LIMIT_RESPONSE = (
    "Mình chưa thực hiện các lệnh bổ sung vì một lượt chỉ được thay đổi tối đa "
    f"{_MAX_DEVICE_COMMANDS} thiết bị. Bạn vui lòng chia nhỏ yêu cầu."
)
_PROTOCOL_ERROR_RESPONSE = (
    "Phản hồi điều khiển không hợp lệ nên mình chưa thay đổi thiết bị. Bạn vui lòng diễn đạt lại yêu cầu."
)
_PROMPT_INJECTION_RESPONSE = (
    "Xin lỗi, mình không thể bỏ qua quy tắc an toàn hoặc thực hiện yêu cầu này. "
    "Mình chỉ có thể hỗ trợ các thao tác nhà thông minh an toàn, hợp lệ."
)
_UNSUPPORTED_SCHEDULE_RESPONSE = (
    "HomeMind chưa hỗ trợ đặt lịch theo ngày hoặc giờ cụ thể qua chat. "
    "Bạn có thể dùng hẹn giờ đếm ngược như ‘sau 30 phút’."
)
_tool_node = ToolNode(TOOLS)


def _control_result_response(messages: list) -> str | None:
    """Build a factual response from Hub-confirmed control tool results."""
    results: list[dict] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or (
            message.name not in CONTROL_TOOL_NAMES and message.name != "control_smart_device"
        ):
            continue
        try:
            result = json.loads(str(message.content))
        except (json.JSONDecodeError, TypeError):
            result = {
                "status": "failed",
                "device_id": "thiết bị",
                "message": "Hub trả về kết quả không hợp lệ.",
            }
        if not isinstance(result, dict):
            result = {
                "status": "failed",
                "device_id": "thiết bị",
                "message": "Hub trả về kết quả không hợp lệ.",
            }
        results.append(result)
    if not results:
        return None

    successful: list[str] = []
    failed: list[str] = []
    action_labels = {
        "on": "Đã bật",
        "off": "Đã tắt",
        "toggle": "Đã đổi trạng thái",
        "set": "Đã cập nhật",
        "lock": "Đã khóa",
    }
    for result in results:
        if result.get("status") == "success" and isinstance(result.get("device"), dict):
            device_name = result["device"].get("name") or result["device"].get("id") or "thiết bị"
            action_label = action_labels.get(result.get("action"), "Đã cập nhật")
            successful.append(f"{action_label} {device_name}")
        else:
            device_id = str(result.get("device_id", "thiết bị"))
            message = str(result.get("message", "chưa nhận được xác nhận"))
            failed.append(f"{device_id}: {message}")

    parts: list[str] = []
    if successful:
        parts.append("; ".join(successful) + ".")
    if failed:
        parts.append("Chưa thực hiện: " + "; ".join(failed) + ".")
    return " ".join(parts)


# ── Helper ───────────────────────────────────────────────────────────────────


def _get_llm():
    """Return the configured model without binding tools."""
    from src.services.llm import get_llm

    return get_llm()


def _prompt_profile_for_transport(transport: str, generic_enabled: bool = False) -> str:
    if transport == "native":
        return "native_tools"
    return "local_tool_first" if generic_enabled else "default"


def _get_bound_llm(transport: str | None = None):
    """Return an LLM instance with tools bound (lazy import to avoid import
    errors when ``langchain_openai`` is not installed and LLM is disabled)."""
    resolved_transport = transport or get_settings().llm_tool_transport
    return _get_llm().bind_tools(TOOLS) if resolved_transport == "native" else _get_llm()


def _bind_local_protocol_grammar(llm, *, transport: str, query: str, enabled: bool = False, generic_enabled: bool = False):
    """Optionally pass llama.cpp grammar per request; never affect native turns."""
    if not enabled or transport != "homeassistant_protocol" or not tool_needed(query) or not hasattr(llm, "bind"):
        return llm, False
    try:
        grammar = LOCAL_TOOL_CALLS_GRAMMAR if generic_enabled else LOCAL_HOMEASSISTANT_GRAMMAR
        return llm.bind(extra_body={"grammar": grammar}), True
    except Exception:
        return llm, False


# ── Nodes ────────────────────────────────────────────────────────────────────


async def agent_node(state: AgentState) -> dict:
    """Core ReAct node — sends messages to LLM with tools bound.

    Injects the system prompt on the first turn so the LLM always has
    persona and device context.
    """
    messages = list(state.get("messages", []))
    mode = state.get("data_mode")
    settings = get_settings()
    transport = settings.llm_tool_transport
    query = state.get("query", "") or next(
        (str(message.content) for message in reversed(messages) if isinstance(message, HumanMessage)), ""
    )
    query = str(query)
    injection_attempt = is_prompt_injection_attempt(query)
    absolute_calendar_schedule = is_absolute_calendar_schedule(query)

    # Inject system prompt at the front if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        prompt_query = state.get("query", "") if settings.llm_local_tool_retrieval_enabled else None
        messages.insert(0, SystemMessage(content=build_system_prompt(mode=mode, profile=_prompt_profile_for_transport(transport, settings.llm_local_generic_tool_protocol_enabled), query=prompt_query)))

    model = _get_llm()
    try:
        llm = _get_bound_llm(transport) if hasattr(model, "bind_tools") else model
    except TypeError:
        llm = _get_bound_llm() if hasattr(model, "bind_tools") else model
    llm, grammar_bound = _bind_local_protocol_grammar(
        llm,
        transport=transport,
        query=query,
        enabled=settings.llm_local_generic_tool_grammar_enabled if settings.llm_local_generic_tool_protocol_enabled else settings.llm_local_protocol_grammar_enabled,
        generic_enabled=settings.llm_local_generic_tool_protocol_enabled,
    )
    try:
        response: AIMessage = await llm.ainvoke(messages)
    except Exception:
        if not grammar_bound:
            raise
        try:
            response = await _get_bound_llm(transport).ainvoke(messages)
        except TypeError:
            response = await _get_bound_llm().ainvoke(messages)

    content = response.content if isinstance(response.content, str) else str(response.content)
    if injection_attempt:
        return {"messages": [AIMessage(content=_PROMPT_INJECTION_RESPONSE)]}
    try:
        local_calls = parse_local_tool_calls(content) if settings.llm_local_generic_tool_protocol_enabled else None
        legacy_call = parse_homeassistant_call(content)
    except HomeAssistantProtocolError:
        return {"messages": [AIMessage(content=_PROTOCOL_ERROR_RESPONSE)]}
    if local_calls is not None:
        if absolute_calendar_schedule and any(call["name"] == "set_device_timer" for call in local_calls):
            return {"messages": [AIMessage(content=_UNSUPPORTED_SCHEDULE_RESPONSE)]}
        control_calls = sum(call["name"] in CONTROL_TOOL_NAMES or call["name"] == "control_smart_device" for call in local_calls)
        if control_calls and not tool_needed(query):
            return {"messages": [AIMessage(content=_PROTOCOL_ERROR_RESPONSE)]}
        if state.get("device_command_count", 0) + control_calls > _MAX_DEVICE_COMMANDS:
            return {"messages": [AIMessage(content=_DEVICE_COMMAND_LIMIT_RESPONSE)]}
        return {"messages": [AIMessage(content="", tool_calls=local_calls)]}
    if legacy_call is not None:
        if transport == "homeassistant_protocol" and query and not tool_needed(query):
            return {"messages": [AIMessage(content=_PROTOCOL_ERROR_RESPONSE)]}
        return {"messages": [AIMessage(content=""), execute_homeassistant_call(legacy_call)]}

    tool_calls = getattr(response, "tool_calls", []) or []
    requested_device_commands = sum(call.get("name") in CONTROL_TOOL_NAMES for call in tool_calls)
    used_device_commands = state.get("device_command_count", 0)
    if tool_calls and state.get("tool_iterations", 0) >= _MAX_ITERATIONS:
        response = AIMessage(
            content="Mình đã dừng vì đạt giới hạn số vòng xử lý an toàn. Bạn vui lòng gửi yêu cầu ngắn gọn hơn."
        )
    elif used_device_commands + requested_device_commands > _MAX_DEVICE_COMMANDS:
        response = AIMessage(content=_DEVICE_COMMAND_LIMIT_RESPONSE)
    return {"messages": [response]}


async def respond_node(state: AgentState) -> dict:
    """Extract the final answer without replacing independent model content."""
    model_messages = [message for message in state["messages"] if isinstance(message, AIMessage)]
    raw_content = model_messages[-1].content if model_messages else ""
    content = raw_content if isinstance(raw_content, str) else str(raw_content)
    if control_response := _control_result_response(state["messages"]):
        combined = " ".join(part for part in (control_response, content.strip()) if part)
        return {"response": combined, "fallback_required": False}

    # Never turn an empty model response into an unverified success claim.
    if not content.strip():
        return {
            "response": "Mình chưa tạo được phản hồi đáng tin cậy. Bạn vui lòng thử lại nhé.",
            "fallback_required": True,
        }

    return {"response": content, "fallback_required": False}


async def fallback_node(state: AgentState) -> dict:
    """Deterministic fallback when LLM is disabled.

    Re-uses the legacy keyword-matching logic from the original
    ``analyze_node`` + ``respond_node`` pipeline.
    """
    from src.agents.nodes.example_node import analyze_node as _legacy_analyze
    from src.agents.nodes.example_node import respond_node as _legacy_respond

    # Force the legacy keyword path here so an LLM outage cannot trigger a
    # second LLM request while building the fallback response.
    analyzed = await _legacy_analyze(state, use_llm=False)
    merged = {**state, **analyzed}
    responded = await _legacy_respond(merged)
    return {"response": responded.get("response", ""), **analyzed}


async def answer_informational_remainder(question: str, mode: str | None = None) -> str:
    """Answer a non-command remainder without exposing side-effecting tools."""
    from src.services.llm import get_llm

    model = get_llm()
    llm = model.bind_tools([]) if hasattr(model, "bind_tools") else model
    response = await llm.ainvoke(
        [
            SystemMessage(content=build_system_prompt(mode=mode, profile="informational_no_tools")),
            HumanMessage(content=question),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip()


async def command_node(state: AgentState) -> dict:
    """Execute deterministic commands, then cover any independent question clause."""
    query = state.get("query", "")
    mode = state.get("data_mode")
    result = await handle_natural_home_request(query, state.get("session_id"), mode=mode)
    if not result:
        return {"response": "", "fallback_required": True}
    commands = result.get("metadata", {}).get("commands", [])
    if not commands:
        return result
    remainder = informational_remainder(query)
    if not remainder:
        return result
    if get_settings().llm_enabled:
        if mode:
            informational = await answer_informational_remainder(remainder, mode=mode)
        else:
            informational = await answer_informational_remainder(remainder)
    else:
        informational = f'Mình chưa thể trả lời phần "{remainder}" vì mô hình ngôn ngữ hiện không khả dụng.'
    result["response"] = " ".join(part for part in (result.get("response", ""), informational) if part)
    return result


# ── Routing ──────────────────────────────────────────────────────────────────


def _should_use_tools(state: AgentState) -> str:
    """After the agent node, decide: call tools or return response."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "respond"


def _entry_router(state: AgentState) -> str:
    """At entry, pick the ReAct path or the fallback path."""
    if should_handle_natural_home_request(
        state.get("query", ""),
        state.get("session_id"),
        mode=state.get("data_mode"),
    ):
        return "command"
    settings = get_settings()
    if settings.llm_enabled:
        return "agent"
    return "fallback"


async def execute_tools(state: AgentState) -> dict:
    """Reject over-budget control batches before executing any tool."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []
    requested_device_commands = sum(
        call.get("name") in CONTROL_TOOL_NAMES or call.get("name") == "control_smart_device" for call in tool_calls
    )
    used_device_commands = state.get("device_command_count", 0)
    if used_device_commands + requested_device_commands > _MAX_DEVICE_COMMANDS:
        return {
            "messages": [AIMessage(content=_DEVICE_COMMAND_LIMIT_RESPONSE)],
            "tool_iterations": state.get("tool_iterations", 0),
            "device_command_count": used_device_commands,
        }

    result = await _tool_node.ainvoke(state)
    return {
        **result,
        "tool_iterations": state.get("tool_iterations", 0) + 1,
        "device_command_count": used_device_commands + requested_device_commands,
    }


# ── Graph assembly ───────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and compile the Homing Hub agent graph.

    Graph topology::

        ┌─────────────────────────────────────────┐
        │               START                      │
        │       ┌─────────┴──────────┐             │
        │       ▼                    ▼             │
        │   [agent]             [fallback]         │
        │       │                    │             │
        │   ┌───┴───┐               │             │
        │   ▼       ▼               │             │
        │ [tools] [respond]         │             │
        │   │       │               │             │
        │   └─►agent│               │             │
        │           ▼               ▼             │
        │          END             END             │
        └─────────────────────────────────────────┘
    """
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", execute_tools)
    graph.add_node("respond", respond_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("command", command_node)

    # Entry — choose mode based on LLM_ENABLED
    graph.set_conditional_entry_point(
        _entry_router,
        {
            "command": "command",
            "agent": "agent",
            "fallback": "fallback",
        },
    )

    # ReAct loop: agent → tools → agent  OR  agent → respond → END
    graph.add_conditional_edges(
        "agent",
        _should_use_tools,
        {
            "tools": "tools",
            "respond": "respond",
        },
    )
    graph.add_edge("tools", "agent")  # After tool execution, return to agent
    graph.add_edge("respond", END)

    # Fallback goes straight to END
    graph.add_edge("fallback", END)
    graph.add_edge("command", END)

    return graph.compile()


def _after_interpret(state: TypedAgentState) -> str:
    match state.get("interpretation_status", InterpretationStatus.INVALID):
        case InterpretationStatus.GENERIC_FALLBACK:
            return "respond"
        case InterpretationStatus.READY | InterpretationStatus.NEEDS_CLARIFICATION:
            return "resolve"
        case InterpretationStatus.REPAIR_REQUIRED | InterpretationStatus.INVALID:
            return "respond"
        case _:
            return "respond"


def _after_resolve(state: TypedAgentState) -> str:
    match state.get("interpretation_status", InterpretationStatus.INVALID):
        case InterpretationStatus.NEEDS_CLARIFICATION:
            return "clarify"
        case InterpretationStatus.READY:
            return "validate"
        case (
            InterpretationStatus.REPAIR_REQUIRED | InterpretationStatus.INVALID | InterpretationStatus.GENERIC_FALLBACK
        ):
            return "respond"


def build_typed_graph():
    """Compile explicit typed stages without enabling deferred side effects."""
    graph = StateGraph(TypedAgentState)
    graph.add_node("load_context", load_context)
    graph.add_node("interpret", interpret)
    graph.add_node("resolve", resolve)
    graph.add_node("validate", validate)
    graph.add_node("policy", policy)
    graph.add_node("clarify", clarify)
    graph.add_node("execute", execute)
    graph.add_node("verify", verify)
    graph.add_node("respond", respond)
    graph.add_node("persist_trace", persist_trace)
    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "interpret")
    graph.add_conditional_edges("interpret", _after_interpret)
    graph.add_conditional_edges("resolve", _after_resolve)
    graph.add_edge("validate", "policy")
    graph.add_edge("policy", "execute")
    graph.add_edge("clarify", "respond")
    graph.add_edge("execute", "verify")
    graph.add_edge("verify", "respond")
    graph.add_edge("respond", "persist_trace")
    graph.add_edge("persist_trace", END)
    return graph.compile()


agent = select_agent(get_settings(), build_graph, build_typed_graph)
