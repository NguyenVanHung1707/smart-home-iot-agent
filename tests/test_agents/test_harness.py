import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agents.harness import LocalAgentHarness
from src.agents.homeassistant_protocol import HomeAssistantCall


class SequenceModel:
    def __init__(self, *responses: str | AIMessage) -> None:
        self.responses = [r if isinstance(r, AIMessage) else AIMessage(content=r) for r in responses]
        self.histories = []

    async def ainvoke(self, messages):
        self.histories.append(list(messages))
        return self.responses.pop(0)


def fenced_tool(device_id: str = "living-light", action: str = "on") -> str:
    return (
        "```homeassistant\n"
        + json.dumps(
            {
                "tool": "control_smart_device",
                "arguments": {"device_id": device_id, "action": action, "value": None},
            }
        )
        + "\n```"
    )


@pytest.mark.asyncio
async def test_harness_executes_tool_then_requests_final_answer():
    model = SequenceModel(fenced_tool(), "Đã bật đèn phòng khách rồi nhé.")
    executed: list[HomeAssistantCall] = []

    def execute(call: HomeAssistantCall) -> ToolMessage:
        executed.append(call)
        return ToolMessage(
            name="control_smart_device",
            tool_call_id="local-call",
            content='{"status":"success","device":{"name":"Đèn phòng khách"}}',
        )

    generated = await LocalAgentHarness(3).ainvoke([], model=model, execute_tool=execute)

    assert executed[0].device_id == "living-light"
    assert [type(message) for message in generated] == [AIMessage, ToolMessage, AIMessage]
    assert isinstance(model.histories[1][-1], ToolMessage)
    assert generated[-1].content == "Đã bật đèn phòng khách rồi nhé."


@pytest.mark.asyncio
async def test_harness_stops_repeated_identical_tool_calls():
    model = SequenceModel(fenced_tool(), fenced_tool(), "Không lặp nữa.")
    calls = 0

    def execute(_call: HomeAssistantCall) -> ToolMessage:
        nonlocal calls
        calls += 1
        return ToolMessage(name="control_smart_device", tool_call_id="local-call", content="{}")

    generated = await LocalAgentHarness(5).ainvoke([], model=model, execute_tool=execute)

    assert calls == 1
    assert len(generated) == 2


@pytest.mark.asyncio
async def test_harness_handles_protocol_error_with_informative_feedback_allowing_recovery():
    model = SequenceModel(
        'Đã bật.\n```homeassistant\n{"service":"light.turn_on","target_device":"living-light"}\n```',
        "Xin lỗi, có lỗi định dạng lệnh nên mình chưa thay đổi thiết bị.",
    )

    def execute(_call: HomeAssistantCall) -> ToolMessage:
        raise AssertionError("invalid protocol must not execute directly")

    generated = await LocalAgentHarness().ainvoke([], model=model, execute_tool=execute)

    assert len(generated) == 3
    assert isinstance(generated[1], ToolMessage)
    assert "protocol_error" in generated[1].name or "invalid_request" in generated[1].content
    assert "lỗi định dạng" in generated[2].content or "chưa thay đổi" in generated[2].content


@pytest.mark.asyncio
async def test_harness_supports_native_tool_calls():
    native_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "control_smart_device",
                "args": {"device_id": "living-aircon", "action": "on", "value": None},
                "id": "call-aircon-1",
            }
        ],
    )
    model = SequenceModel(native_msg, "Điều hòa phòng khách đã được bật.")
    executed: list[HomeAssistantCall] = []

    def execute(call: HomeAssistantCall) -> ToolMessage:
        executed.append(call)
        return ToolMessage(
            name="control_smart_device",
            tool_call_id="call-aircon-1",
            content='{"status":"success"}',
        )

    generated = await LocalAgentHarness(3).ainvoke([], model=model, execute_tool=execute)

    assert len(executed) == 1
    assert executed[0].device_id == "living-aircon"
    assert len(generated) == 3
    assert generated[-1].content == "Điều hòa phòng khách đã được bật."
