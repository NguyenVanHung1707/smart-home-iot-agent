from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agents import graph
from src.agents.graph import agent
from src.models.schemas import Device


@pytest.mark.asyncio
async def test_agent_basic_flow(monkeypatch):
    """Agent should return a response when given a simple query (fallback mode)."""

    class MockLlm:
        async def ainvoke(self, messages):
            return AIMessage(content="Xin chào! Tôi có thể giúp gì cho bạn?")

    monkeypatch.setattr(graph, "_get_bound_llm", lambda *args, **kwargs: MockLlm())
    result = await agent.ainvoke({"query": "Hello", "messages": []})
    assert "response" in result


@pytest.mark.asyncio
async def test_agent_state_structure(monkeypatch):
    """Agent should return a dict containing at least 'query'."""

    class MockLlm:
        async def ainvoke(self, messages):
            return AIMessage(content="Kế hoạch kiểm tra thiết bị.")

    monkeypatch.setattr(graph, "_get_bound_llm", lambda *args, **kwargs: MockLlm())
    result = await agent.ainvoke({"query": "Test query", "messages": []})
    assert isinstance(result, dict)
    assert "query" in result


@pytest.mark.asyncio
async def test_fallback_general_reply_uses_accented_vietnamese():
    result = await graph.fallback_node({"query": "xin chào", "messages": []})

    assert result["response"] == ("Tôi có thể điều khiển thiết bị, tra hướng dẫn hoặc lập kế hoạch cho ngôi nhà.")


@pytest.mark.asyncio
async def test_agent_asks_for_room_when_light_command_is_ambiguous(monkeypatch):
    commands = []
    device = Device(
        id="living-light",
        name="Den phong khach",
        room="Phong khach",
        kind="light",
        state={"power": True},
    )
    monkeypatch.setattr(
        "src.agents.nodes.example_node.control_device",
        lambda device_id, action: (commands.append((device_id, action)) or device, None),
    )

    result = await agent.ainvoke({"query": "bat den", "messages": []})

    assert commands == []
    assert "phòng khách hay phòng ngủ" in result["response"]
    assert result["metadata"]["commands"] == []


@pytest.mark.asyncio
async def test_fallback_routes_bedroom_light_by_room_name(monkeypatch):
    commands = []
    device = Device(
        id="bedroom-light",
        name="Den phong ngu",
        room="Phong ngu",
        kind="light",
        state={"power": True},
    )
    monkeypatch.setattr(
        "src.agents.nodes.example_node.control_device",
        lambda device_id, action: (commands.append((device_id, action)) or device, None),
    )

    result = await graph.fallback_node({"query": "bật đèn phòng ngủ", "messages": []})

    assert commands == [("bedroom-light", "on")]
    assert result["metadata"]["device"]["id"] == "bedroom-light"


@pytest.mark.asyncio
async def test_mixed_command_and_general_question_combines_both_answers(monkeypatch):
    command_result = {
        "response": "Đã bật Đèn phòng khách.",
        "analysis": "deterministic_natural_language_control",
        "metadata": {"commands": [{"device_id": "living-light", "action": "on", "value": None}]},
    }
    handler = AsyncMock(return_value=command_result)
    informational = AsyncMock(return_value="Hà Nội là thủ đô của Việt Nam.")
    monkeypatch.setattr(graph, "handle_natural_home_request", handler)
    monkeypatch.setattr(graph, "answer_informational_remainder", informational)
    monkeypatch.setattr(graph.get_settings(), "llm_enabled", True)

    result = await graph.command_node({"query": "bật đèn phòng khách và thủ đô Việt Nam là gì?", "messages": []})

    assert result["response"] == "Đã bật Đèn phòng khách. Hà Nội là thủ đô của Việt Nam."
    handler.assert_awaited_once()
    informational.assert_awaited_once_with("thủ đô Việt Nam là gì?")


@pytest.mark.asyncio
async def test_mixed_command_and_unsupported_clause_reports_limitation(monkeypatch):
    command_result = {
        "response": "Đã tắt Đèn phòng ngủ.",
        "analysis": "deterministic_natural_language_control",
        "metadata": {"commands": [{"device_id": "bedroom-light", "action": "off", "value": None}]},
    }
    monkeypatch.setattr(graph, "handle_natural_home_request", AsyncMock(return_value=command_result))
    monkeypatch.setattr(
        graph,
        "answer_informational_remainder",
        AsyncMock(return_value="Mình chưa hỗ trợ kiểm tra trạng thái máy giặt."),
    )
    monkeypatch.setattr(graph.get_settings(), "llm_enabled", True)

    result = await graph.command_node({"query": "tắt đèn phòng ngủ và máy giặt chạy xong chưa?", "messages": []})

    assert "Đã tắt Đèn phòng ngủ." in result["response"]
    assert "chưa hỗ trợ kiểm tra trạng thái máy giặt" in result["response"]


@pytest.mark.parametrize(
    "query",
    [
        "đừng bật đèn phòng khách và thủ đô Việt Nam là gì?",
        "nếu tôi nói bật đèn phòng khách thì sao và thủ đô Việt Nam là gì?",
        "tối nay bật đèn phòng khách và thủ đô Việt Nam là gì?",
        "mở khóa cửa chính và thủ đô Việt Nam là gì?",
        "bật đèn và thủ đô Việt Nam là gì?",
        "bật đèn phòng khách rồi tắt đi và thủ đô Việt Nam là gì?",
    ],
)
@pytest.mark.asyncio
async def test_protected_deterministic_outcome_never_calls_residual_model(monkeypatch, query):
    informational = AsyncMock(return_value="Không được dùng.")
    monkeypatch.setattr(graph, "answer_informational_remainder", informational)
    monkeypatch.setattr(graph.get_settings(), "llm_enabled", True)

    result = await graph.command_node({"query": query, "messages": []})

    assert result["metadata"]["commands"] == []
    informational.assert_not_awaited()


@pytest.mark.asyncio
async def test_general_question_uses_model_path_without_deterministic_handler(monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(graph, "handle_natural_home_request", handler)
    monkeypatch.setattr(graph.get_settings(), "llm_enabled", True)

    assert graph._entry_router({"query": "Thủ đô Việt Nam là gì?", "messages": []}) == "agent"
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_agent_routes_natural_command_without_llm(monkeypatch):
    command_result = {
        "response": "Đã tắt Đèn phòng ngủ.",
        "analysis": "deterministic_natural_language_control",
        "metadata": {"commands": [{"device_id": "bedroom-light", "action": "off", "value": None}]},
    }
    handler = AsyncMock(return_value=command_result)
    llm = AsyncMock()
    monkeypatch.setattr(graph, "handle_natural_home_request", handler)
    monkeypatch.setattr(graph, "_get_bound_llm", llm)

    result = await agent.ainvoke({"query": "tắt giúp mình cái đèn chỗ ngủ", "messages": []})

    assert result["response"] == "Đã tắt Đèn phòng ngủ."
    handler.assert_awaited_once()
    llm.assert_not_called()


@pytest.mark.asyncio
async def test_agent_answers_room_device_query():
    result = await agent.ainvoke({"query": "phòng khách của tôi có những thiết bị nào", "messages": []})
    assert "Phòng khách hiện có" in result["response"]
    assert "Đèn phòng khách" in result["response"]


@pytest.mark.asyncio
async def test_mixed_request_reports_unanswered_clause_when_llm_unavailable(monkeypatch):
    command_result = {
        "response": "Đã bật Đèn phòng khách.",
        "analysis": "deterministic_natural_language_control",
        "metadata": {"commands": [{"device_id": "living-light", "action": "on", "value": None}]},
    }
    monkeypatch.setattr(graph, "handle_natural_home_request", AsyncMock(return_value=command_result))
    monkeypatch.setattr(graph.get_settings(), "llm_enabled", False)

    result = await graph.command_node({"query": "bật đèn phòng khách và thủ đô Việt Nam là gì?", "messages": []})

    assert "Đã bật Đèn phòng khách." in result["response"]
    assert "thủ đô việt nam là gì" in result["response"].lower()
    assert "chưa thể trả lời" in result["response"].lower()


@pytest.mark.asyncio
async def test_agent_blocks_tool_calls_after_iteration_budget(monkeypatch):
    class BoundLlm:
        async def ainvoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_room_devices",
                        "args": {},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )

    monkeypatch.setattr(graph, "_get_bound_llm", lambda *args, **kwargs: BoundLlm())

    result = await graph.agent_node({"messages": [], "tool_iterations": graph._MAX_ITERATIONS})

    assert result["messages"][0].tool_calls == []
    assert "giới hạn" in result["messages"][0].content


def _control_calls(count: int, *, start: int = 0) -> list[dict]:
    return [
        {
            "name": "control_smart_device",
            "args": {"device_id": "living-light", "action": "on", "value": None},
            "id": f"call-{index}",
            "type": "tool_call",
        }
        for index in range(start, start + count)
    ]


@pytest.mark.asyncio
async def test_agent_blocks_device_commands_over_hard_limit(monkeypatch):
    class BoundLlm:
        async def ainvoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "control_light",
                        "args": {"room": "Phòng khách", "action": "on"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )

    monkeypatch.setattr(graph, "_get_bound_llm", lambda *args, **kwargs: BoundLlm())

    result = await graph.agent_node({"messages": [], "device_command_count": graph._MAX_DEVICE_COMMANDS})

    assert result["messages"][0].tool_calls == []
    assert "tối đa 5" in result["messages"][0].content


@pytest.mark.asyncio
async def test_first_batch_over_device_command_budget_executes_no_tools(monkeypatch):
    tool_node = AsyncMock(return_value={"messages": []})
    monkeypatch.setattr(graph, "_tool_node", tool_node)
    state = {"messages": [AIMessage(content="", tool_calls=_control_calls(6))]}

    result = await graph.execute_tools(state)

    tool_node.ainvoke.assert_not_awaited()
    assert result["messages"][0].tool_calls == []
    assert "tối đa 5" in result["messages"][0].content
    assert result["device_command_count"] == 0


@pytest.mark.asyncio
async def test_cumulative_device_command_budget_rejects_entire_overflow_batch(monkeypatch):
    tool_node = AsyncMock(return_value={"messages": []})
    monkeypatch.setattr(graph, "_tool_node", tool_node)
    state = {
        "messages": [AIMessage(content="", tool_calls=_control_calls(2, start=4))],
        "device_command_count": 4,
        "tool_iterations": 1,
    }

    result = await graph.execute_tools(state)

    tool_node.ainvoke.assert_not_awaited()
    assert result["messages"][0].tool_calls == []
    assert "tối đa 5" in result["messages"][0].content
    assert result["device_command_count"] == 4
    assert result["tool_iterations"] == 1


@pytest.mark.asyncio
async def test_empty_model_response_does_not_claim_success():
    result = await graph.respond_node({"messages": [AIMessage(content="")]})

    assert "thực hiện xong" not in result["response"]
    assert "đáng tin cậy" in result["response"]
    assert result["fallback_required"] is True


@pytest.mark.asyncio
async def test_control_response_uses_tool_results_instead_of_model_claim():
    success = ToolMessage(
        name="control_light",
        tool_call_id="call-1",
        content=(
            '{"status":"success","action":"on","device":'
            '{"id":"living-light","name":"Đèn phòng khách","state":{"power":true}}}'
        ),
    )
    failure = ToolMessage(
        name="control_speaker",
        tool_call_id="call-2",
        content=(
            '{"status":"timeout","device_id":"hub-speaker","action":"off",'
            '"message":"Thiết bị không phản hồi; chưa xác nhận thay đổi."}'
        ),
    )

    result = await graph.respond_node({"messages": [success, failure, AIMessage(content="")]})

    assert "Đã bật Đèn phòng khách" in result["response"]
    assert "Chưa thực hiện: hub-speaker" in result["response"]
    assert result["fallback_required"] is False


@pytest.mark.asyncio
async def test_control_result_preserves_independent_model_content():
    success = ToolMessage(
        name="control_smart_device",
        tool_call_id="call-1",
        content=(
            '{"status":"success","action":"on","device":'
            '{"id":"living-light","name":"Đèn phòng khách","state":{"power":true}}}'
        ),
    )

    result = await graph.respond_node({"messages": [success, AIMessage(content="Hà Nội là thủ đô của Việt Nam.")]})

    assert "Đã bật Đèn phòng khách" in result["response"]
    assert "Hà Nội là thủ đô của Việt Nam." in result["response"]
