from unittest.mock import Mock

import pytest

from src.models.schemas import Device
from src.services import natural_language_control as nlu


@pytest.mark.parametrize(
    ("query", "device_id", "action", "value"),
    [
        ("cho đèn phòng khách sáng lên nhé", "living-light", "on", None),
        ("cho bật đèn phòng khách lên nhé", "living-light", "on", None),
        ("tắt giúp mình cái đèn chỗ ngủ", "bedroom-light", "off", None),
        ("điều chỉnh điều hòa phòng khách về 24 độ", "living-aircon", "set", {"target_temperature": 24}),
        ("kéo rèm phòng khách lên một nửa", "living-blind", "set", {"position": 50}),
        ("cho loa nhỏ xuống mức 20", "hub-speaker", "set", {"volume": 20}),
        ("cho đèn khách sáng 40 phần trăm", "living-light", "set", {"brightness": 40}),
        ("cho loa bé lại", "hub-speaker", "set", {"volume": 35}),
        ("vặn loa to", "hub-speaker", "set", {"volume": 55}),
    ],
)
def test_parses_natural_vietnamese_variants(query, device_id, action, value):
    plan = nlu.parse_home_request(query)

    assert plan.handled is True
    assert plan.commands[0].device_id == device_id
    assert plan.commands[0].action == action
    assert plan.commands[0].value == value


def test_parses_multiple_commands_with_different_actions():
    plan = nlu.parse_home_request("bật đèn phòng khách và tắt đèn phòng ngủ")

    assert [(item.device_id, item.action) for item in plan.commands] == [
        ("living-light", "on"),
        ("bedroom-light", "off"),
    ]


def test_reuses_light_and_action_across_coordinated_rooms():
    plan = nlu.parse_home_request("bật đèn phòng khách và phòng ngủ")

    assert [(item.device_id, item.action) for item in plan.commands] == [
        ("living-light", "on"),
        ("bedroom-light", "on"),
    ]


def test_reuses_explicit_device_for_an_elliptical_follow_up_clause():
    plan = nlu.parse_home_request("bật đèn phòng khách rồi giảm còn 30%")

    assert [(item.device_id, item.action, item.value) for item in plan.commands] == [
        ("living-light", "on", None),
        ("living-light", "set", {"brightness": 30}),
    ]


def test_generic_light_command_asks_for_the_room():
    plan = nlu.parse_home_request("bật đèn lên giúp mình")

    assert plan.handled is True
    assert plan.commands == ()
    assert "phòng khách hay phòng ngủ" in plan.reply


def test_colloquial_living_room_status_question_reads_state(monkeypatch):
    monkeypatch.setattr(
        nlu.registry,
        "get",
        lambda device_id: Device(
            id=device_id,
            name="Đèn phòng khách",
            room="Phòng khách",
            kind="light",
            state={"power": True},
        ),
    )

    plan = nlu.parse_home_request("đèn khách bật chưa?")

    assert plan.commands == ()
    assert plan.reply == "Đèn phòng khách hiện đang bật."


def test_ambiguous_relative_aircon_request_still_requires_clarification():
    plan = nlu.parse_home_request("lạnh quá, giảm máy lạnh một chút")

    assert plan.commands == ()
    assert "nói rõ hơn" in plan.reply


@pytest.mark.parametrize(
    "query",
    [
        "đừng tắt đèn phòng khách",
        "nếu tôi nói bật đèn phòng ngủ thì sao",
        "bật đèn phòng khách được không?",
        "đèn phòng khách đã bật chưa?",
        "đèn phòng ngủ có tắt không?",
        "đèn phòng khách tắt rồi à?",
        "đèn phòng khách đang bật hả?",
        "câu 'bật đèn phòng khách' nghĩa là gì?",
        "nhắc lại câu bật đèn phòng khách",
        "tối nay bật đèn phòng khách giúp mình",
        "khi trời tối thì bật đèn phòng khách",
        "bật đèn phòng khách khi trời tối",
        "chớ bật đèn phòng khách",
        "đừng có bật đèn phòng khách",
        "mở khóa cửa chính",
    ],
)
def test_safety_context_never_creates_commands(query):
    plan = nlu.parse_home_request(query)

    assert plan.handled is True
    assert plan.commands == ()


def test_status_question_reads_current_state_without_creating_command(monkeypatch):
    monkeypatch.setattr(
        nlu.registry,
        "get",
        lambda device_id: Device(
            id=device_id,
            name="Đèn phòng khách",
            room="Phòng khách",
            kind="light",
            state={"power": True},
        ),
    )

    plan = nlu.parse_home_request("đèn phòng khách đã bật chưa?")

    assert plan.commands == ()
    assert plan.reply == "Đèn phòng khách hiện đang bật."


def test_colloquial_completed_state_question_reads_state(monkeypatch):
    monkeypatch.setattr(
        nlu.registry,
        "get",
        lambda device_id: Device(
            id=device_id,
            name="Đèn phòng khách",
            room="Phòng khách",
            kind="light",
            state={"power": False},
        ),
    )

    plan = nlu.parse_home_request("đèn phòng khách tắt rồi à?")

    assert plan.commands == ()
    assert plan.reply == "Đèn phòng khách hiện đang tắt."


@pytest.mark.parametrize(
    "query",
    [
        "tối nay bật đèn phòng khách giúp mình",
        "lát nữa tắt điều hòa phòng khách",
        "lúc 22 giờ tắt đèn phòng ngủ",
        "khi trời tối thì bật đèn phòng khách",
        "bật đèn phòng khách khi trời tối",
    ],
)
def test_deferred_commands_are_never_executed_immediately(query):
    plan = nlu.parse_home_request(query)

    assert plan.handled is True
    assert plan.commands == ()
    assert "lịch tự động" in plan.reply


def test_conflicting_power_actions_require_clarification():
    plan = nlu.parse_home_request("bật đèn phòng khách rồi tắt đi")

    assert plan.handled is True
    assert plan.commands == ()
    assert "mâu thuẫn" in plan.reply


def test_whole_home_only_targets_devices_that_are_on(monkeypatch):
    devices = [
        Device(id="living-light", name="A", room="A", kind="light", state={"power": True}),
        Device(id="bedroom-light", name="B", room="B", kind="light", state={"power": False}),
        Device(id="living-aircon", name="C", room="C", kind="aircon", state={"power": True}),
    ]
    monkeypatch.setattr(nlu.registry, "list", lambda: devices)

    plan = nlu.parse_home_request("tắt hết thiết bị đang bật giúp mình")

    assert [(item.device_id, item.action) for item in plan.commands] == [
        ("living-light", "off"),
        ("living-aircon", "off"),
    ]


@pytest.mark.asyncio
async def test_handler_reports_only_mqtt_confirmed_success(monkeypatch):
    device = Device(
        id="bedroom-light",
        name="Đèn phòng ngủ",
        room="Phòng ngủ",
        kind="light",
        state={"power": False},
    )
    control = Mock(return_value=(device, None))
    monkeypatch.setattr(nlu, "control_device", control)

    result = await nlu.handle_natural_home_request("tắt giúp mình cái đèn chỗ ngủ")

    control.assert_called_once_with("bedroom-light", "off", None)
    assert result["response"] == "Đã tắt Đèn phòng ngủ."
    assert result["metadata"]["commands"][0]["device_id"] == "bedroom-light"


@pytest.mark.asyncio
async def test_clarification_room_follow_up_executes_original_command(monkeypatch):
    session_id = "room-follow-up"
    nlu.conversations.clear(session_id)
    device = Device(
        id="bedroom-light",
        name="Đèn phòng ngủ",
        room="Phòng ngủ",
        kind="light",
        state={"power": True, "brightness": 45},
    )
    control = Mock(return_value=(device, None))
    monkeypatch.setattr(nlu, "control_device", control)

    first = await nlu.handle_natural_home_request("bật đèn lên", session_id)
    second = await nlu.handle_natural_home_request("phòng ngủ", session_id)

    assert "phòng khách hay phòng ngủ" in first["response"]
    control.assert_called_once_with("bedroom-light", "on", None)
    assert second["response"] == "Đã bật Đèn phòng ngủ."


@pytest.mark.asyncio
async def test_clarification_value_follow_up_sets_aircon(monkeypatch):
    session_id = "value-follow-up"
    nlu.conversations.clear(session_id)
    device = Device(
        id="living-aircon",
        name="Điều hòa",
        room="Phòng khách",
        kind="aircon",
        state={"power": True, "target_temperature": 24, "mode": "cool"},
    )
    control = Mock(return_value=(device, None))
    monkeypatch.setattr(nlu, "control_device", control)

    await nlu.handle_natural_home_request("lạnh quá, giảm máy lạnh một chút", session_id)
    result = await nlu.handle_natural_home_request("24 độ", session_id)

    control.assert_called_once_with("living-aircon", "set", {"target_temperature": 24})
    assert "24°C" in result["response"]


@pytest.mark.asyncio
async def test_single_device_context_resolves_subjectless_adjustment(monkeypatch):
    session_id = "single-device-context"
    nlu.conversations.clear(session_id)
    device = Device(
        id="living-light",
        name="Đèn phòng khách",
        room="Phòng khách",
        kind="light",
        state={"power": True, "brightness": 30},
    )
    control = Mock(return_value=(device, None))
    monkeypatch.setattr(nlu, "control_device", control)

    await nlu.handle_natural_home_request("bật đèn phòng khách", session_id)
    result = await nlu.handle_natural_home_request("giảm xuống 30%", session_id)

    assert control.call_args_list[-1].args == ("living-light", "set", {"brightness": 30})
    assert "30%" in result["response"]


@pytest.mark.asyncio
async def test_status_query_sets_context_for_pronoun_follow_up(monkeypatch):
    session_id = "status-context"
    nlu.conversations.clear(session_id)
    device = Device(
        id="living-light",
        name="Đèn phòng khách",
        room="Phòng khách",
        kind="light",
        state={"power": False, "brightness": 65},
    )
    monkeypatch.setattr(nlu.registry, "get", lambda _device_id: device)
    control = Mock(return_value=(device, None))
    monkeypatch.setattr(nlu, "control_device", control)

    status = await nlu.handle_natural_home_request("đèn phòng khách bật chưa?", session_id)
    result = await nlu.handle_natural_home_request("bật nó lên", session_id)

    assert status["response"] == "Đèn phòng khách hiện đang tắt."
    control.assert_called_once_with("living-light", "on", None)
    assert result["metadata"]["commands"][0]["device_id"] == "living-light"


@pytest.mark.asyncio
async def test_multiple_device_context_never_guesses_pronoun(monkeypatch):
    session_id = "multi-device-context"
    nlu.conversations.clear(session_id)
    control = Mock(
        side_effect=lambda device_id, action, value: (
            Device(id=device_id, name=device_id, room="Phòng", kind="light", state={"power": True}),
            None,
        )
    )
    monkeypatch.setattr(nlu, "control_device", control)

    await nlu.handle_natural_home_request("bật đèn phòng khách và phòng ngủ", session_id)
    result = await nlu.handle_natural_home_request("tắt nó đi", session_id)
    resolved = await nlu.handle_natural_home_request("đèn phòng ngủ", session_id)

    assert control.call_count == 3
    assert result["metadata"]["commands"] == []
    assert "nói rõ thiết bị" in result["response"]
    assert resolved["metadata"]["commands"] == [{"device_id": "bedroom-light", "action": "off", "value": None}]


@pytest.mark.asyncio
async def test_cancel_clears_pending_clarification(monkeypatch):
    session_id = "cancel-pending"
    nlu.conversations.clear(session_id)
    control = Mock()
    monkeypatch.setattr(nlu, "control_device", control)

    await nlu.handle_natural_home_request("bật đèn lên", session_id)
    result = await nlu.handle_natural_home_request("thôi, bỏ đi", session_id)

    assert result["metadata"]["commands"] == []
    assert "đã hủy" in result["response"].lower()
    assert nlu.conversations.snapshot(session_id).pending is None
    control.assert_not_called()


@pytest.mark.asyncio
async def test_pending_context_never_bypasses_unlock_or_future_guards(monkeypatch):
    session_id = "safe-pending"
    nlu.conversations.clear(session_id)
    control = Mock()
    monkeypatch.setattr(nlu, "control_device", control)

    await nlu.handle_natural_home_request("bật đèn lên", session_id)
    negated = await nlu.handle_natural_home_request("đừng bật đèn phòng khách", session_id)
    await nlu.handle_natural_home_request("bật đèn lên", session_id)
    unlock = await nlu.handle_natural_home_request("mở khóa cửa chính", session_id)
    await nlu.handle_natural_home_request("bật đèn lên", session_id)
    future = await nlu.handle_natural_home_request("tối nay bật đèn phòng ngủ", session_id)

    assert "phủ định" in negated["response"]
    assert "xác nhận" in unlock["response"]
    assert "lịch tự động" in future["response"]
    control.assert_not_called()


@pytest.mark.asyncio
async def test_queries_room_devices_and_topology():
    # 1. Asking devices in a specific room
    res_living = await nlu.handle_natural_home_request("phòng khách của tôi có những thiết bị nào")
    assert res_living is not None
    assert "Phòng khách hiện có" in res_living["response"]
    assert "Đèn phòng khách" in res_living["response"]

    res_bedroom = await nlu.handle_natural_home_request("phòng ngủ có những thiết bị gì")
    assert res_bedroom is not None
    assert "Phòng ngủ hiện có" in res_bedroom["response"]
    assert "Đèn phòng ngủ" in res_bedroom["response"]

    # 2. Asking how many rooms in the house
    res_rooms = await nlu.handle_natural_home_request("nhà có bao nhiêu phòng")
    assert res_rooms is not None
    assert "Ngôi nhà hiện có" in res_rooms["response"]
    assert "Phòng khách" in res_rooms["response"]

    # 3. Asking active devices
    res_active = await nlu.handle_natural_home_request("những thiết bị nào đang bật")
    assert res_active is not None
    assert "thiết bị đang bật" in res_active["response"]


@pytest.mark.asyncio
async def test_handle_natural_home_request_dispatches_with_real_mode(monkeypatch):
    import src.services.devices as devices_mod

    devices_mod.get_registry("real").set_online("living-light", True)

    calls = []

    def mock_control(device_id, action, value=None, **kwargs):
        calls.append({"device_id": device_id, "action": action, "value": value, "kwargs": kwargs})
        dev = devices_mod.get_registry("real").get(device_id)
        return dev, None

    monkeypatch.setattr("src.services.natural_language_control.control_device", mock_control)

    res = await nlu.handle_natural_home_request("bật đèn phòng khách", mode="real")
    assert res is not None
    assert len(calls) == 1
    assert calls[0]["device_id"] == "living-light"
    assert calls[0]["kwargs"].get("mode") == "real"
    assert calls[0]["kwargs"].get("registry") is devices_mod.get_registry("real")

