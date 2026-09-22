import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agents import graph
from src.agents.homeassistant_protocol import (
    HomeAssistantProtocolError,
    parse_homeassistant_call,
)


@pytest.mark.parametrize(
    "content",
    [
        '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```\n'
        '```homeassistant\n{"service":"light.turn_off","target_device":"bedroom-light"}\n```',
        '```homeassistant\n{"service":"light.turn_on","target_device":"missing-light"}\n```',
        '```homeassistant\n{"service":"lock.unlock","target_device":"entry-lock"}\n```',
        '```homeassistant\n{"service":"light.turn_on",}\n```',
        "```homeassistant\n[]\n```",
        '```homeassistant\n{"service":"light.explode","target_device":"living-light"}\n```',
    ],
)
def test_parser_rejects_unsafe_or_malformed_calls(content):
    with pytest.raises(HomeAssistantProtocolError):
        parse_homeassistant_call(content)


def test_parser_maps_homeassistant_service_to_local_control():
    call = parse_homeassistant_call('```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```')

    assert call is not None
    assert call.device_id == "living-light"
    assert call.action == "on"
    assert call.value is None


@pytest.mark.parametrize(
    ("service", "target", "service_data", "action", "value"),
    [
        ("light.turn_on", "living-light", None, "on", None),
        ("light.turn_off", "living-light", None, "off", None),
        ("light.toggle", "living-light", None, "toggle", None),
        ("climate.turn_on", "living-aircon", None, "on", None),
        ("climate.turn_off", "living-aircon", None, "off", None),
        ("climate.set_temperature", "living-aircon", {"temperature": 24}, "set", {"target_temperature": 24}),
        ("cover.open_cover", "living-blind", None, "set", {"position": 100}),
        ("cover.close_cover", "living-blind", None, "set", {"position": 0}),
        ("cover.set_cover_position", "living-blind", {"position": 40}, "set", {"position": 40}),
        ("media_player.turn_on", "hub-speaker", None, "on", None),
        ("media_player.turn_off", "hub-speaker", None, "off", None),
        ("media_player.volume_set", "hub-speaker", {"volume_level": 0.45}, "set", {"volume": 45}),
        ("lock.lock", "entry-lock", None, "lock", None),
    ],
)
def test_parser_maps_every_advertised_service(service, target, service_data, action, value):
    payload = {"service": service, "target_device": target}
    if service_data is not None:
        payload["service_data"] = service_data

    call = parse_homeassistant_call(f"```homeassistant\n{json.dumps(payload)}\n```")

    assert call is not None
    assert call.action == action
    assert call.value == value


@pytest.mark.parametrize(
    ("service", "target", "service_data"),
    [
        ("climate.set_temperature", "living-aircon", {"target_temperature": 24}),
        ("climate.set_temperature", "living-aircon", {"temperature": 31}),
        ("cover.set_cover_position", "living-blind", {"position": -1}),
        ("cover.open_cover", "living-blind", {"position": 100}),
        ("media_player.volume_set", "hub-speaker", {"volume": 50}),
        ("media_player.volume_set", "hub-speaker", {"volume_level": 1.01}),
        ("light.turn_on", "living-light", {"brightness": 50}),
    ],
)
def test_parser_rejects_wrong_fields_and_ranges(service, target, service_data):
    payload = {"service": service, "target_device": target, "service_data": service_data}

    with pytest.raises(HomeAssistantProtocolError):
        parse_homeassistant_call(f"```homeassistant\n{json.dumps(payload)}\n```")


def test_parser_accepts_plain_answer_without_protocol_block():
    assert parse_homeassistant_call("Hà Nội là thủ đô của Việt Nam.") is None


@pytest.mark.parametrize(
    "content",
    [
        'Đã bật.\n```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```',
        '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```\nĐã bật.',
        '> ```homeassistant\n> {"service":"light.turn_on","target_device":"living-light"}\n> ```',
        'Ví dụ: "```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```"',
        '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n',
        '```homeassistant {"service":"light.turn_on","target_device":"living-light"}```',
    ],
)
def test_parser_rejects_embedded_quoted_or_malformed_protocol(content):
    with pytest.raises(HomeAssistantProtocolError):
        parse_homeassistant_call(content)


@pytest.mark.asyncio
async def test_agent_executes_validated_fenced_call_and_uses_hub_result(monkeypatch):
    class LegacyLlm:
        async def ainvoke(self, messages):
            return AIMessage(
                content=('```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```')
            )

    monkeypatch.setattr(graph, "_get_llm", lambda: LegacyLlm())
    monkeypatch.setattr(
        graph,
        "execute_homeassistant_call",
        lambda call: ToolMessage(
            name="control_smart_device",
            tool_call_id="legacy-call",
            content=(
                '{"status":"success","action":"on","device":'
                '{"id":"living-light","name":"Đèn phòng khách","state":{"power":true}}}'
            ),
        ),
    )

    result = await graph.agent_node({"messages": []})

    assert len(result["messages"]) == 2
    assert result["messages"][1].name == "control_smart_device"
    response = await graph.respond_node({"messages": result["messages"]})
    assert response["response"] == "Đã bật Đèn phòng khách."


@pytest.mark.asyncio
async def test_compiled_graph_executes_legacy_call_with_message_reducer(monkeypatch):
    class LegacyLlm:
        async def ainvoke(self, messages):
            return AIMessage(
                content=('```homeassistant\n{"service":"cover.open_cover","target_device":"living-blind"}\n```')
            )

    monkeypatch.setattr(graph.get_settings(), "llm_enabled", True)
    monkeypatch.setattr(graph, "_get_llm", lambda: LegacyLlm())
    monkeypatch.setattr(graph, "should_handle_natural_home_request", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        graph,
        "execute_homeassistant_call",
        lambda call: ToolMessage(
            name="control_smart_device",
            tool_call_id="legacy-integration-call",
            content=(
                '{"status":"success","action":"set","device":'
                '{"id":"living-blind","name":"Rèm phòng khách","state":{"position":100}}}'
            ),
        ),
    )

    result = await graph.agent.ainvoke({"query": "Mở rèm phòng khách", "messages": []})

    assert result["response"] == "Đã cập nhật Rèm phòng khách."
    assert [message.name for message in result["messages"] if isinstance(message, ToolMessage)] == [
        "control_smart_device"
    ]


@pytest.mark.parametrize(
    "content",
    [
        'Đã bật.\n```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```',
        '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```\nĐã bật.',
        'Ví dụ: "```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```"',
        '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n',
    ],
)
@pytest.mark.asyncio
async def test_agent_rejects_non_exact_protocol_without_execution(monkeypatch, content):
    class LegacyLlm:
        async def ainvoke(self, messages):
            return AIMessage(content=content)

    monkeypatch.setattr(graph, "_get_llm", lambda: LegacyLlm())
    monkeypatch.setattr(
        graph,
        "execute_homeassistant_call",
        lambda call: pytest.fail("non-exact calls must not execute"),
    )

    result = await graph.agent_node({"messages": []})

    assert "không hợp lệ" in result["messages"][0].content


@pytest.mark.asyncio
async def test_agent_rejects_multiple_fenced_calls_without_execution(monkeypatch):
    class LegacyLlm:
        async def ainvoke(self, messages):
            return AIMessage(
                content=(
                    '```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```\n'
                    '```homeassistant\n{"service":"light.turn_off","target_device":"bedroom-light"}\n```'
                )
            )

    monkeypatch.setattr(graph, "_get_llm", lambda: LegacyLlm())
    monkeypatch.setattr(
        graph,
        "execute_homeassistant_call",
        lambda call: pytest.fail("invalid calls must not execute"),
    )

    result = await graph.agent_node({"messages": []})

    assert len(result["messages"]) == 1
    assert "không hợp lệ" in result["messages"][0].content
