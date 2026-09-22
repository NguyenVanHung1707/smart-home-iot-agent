from src.agents.system_prompt import build_system_prompt
from src.models.schemas import Device
from src.services import natural_language_control as nlu


def test_resolves_room_and_active_device_queries():
    rooms = nlu.parse_home_request("phòng khách có những thiết bị nào")
    active = nlu.parse_home_request("những thiết bị nào đang bật")

    assert rooms.handled is True
    assert "Phòng khách hiện có" in rooms.reply
    assert "Đèn phòng khách" in rooms.reply
    assert active.handled is True
    assert "thiết bị đang bật" in active.reply


def test_resolves_sensor_query_for_requested_room(monkeypatch):
    devices = [
        Device(
            id="kitchen-sensor",
            name="Cảm biến bếp",
            room="Phòng bếp",
            kind="sensor",
            state={"temperature": 26.5, "humidity": 70},
        ),
        Device(
            id="living-sensor",
            name="Cảm biến khách",
            room="Phòng khách",
            kind="sensor",
            state={"temperature": 28.0, "humidity": 60},
        ),
    ]
    monkeypatch.setattr(nlu.registry, "list", lambda: devices)

    result = nlu.parse_home_request("độ ẩm phòng bếp bao nhiêu")

    assert result.handled is True
    assert "70% tại Phòng bếp" in result.reply
    assert "60%" not in result.reply


def test_system_prompt_contains_runtime_topology():
    prompt = build_system_prompt()

    assert "SƠ ĐỒ NHÀ HIỆN TẠI" in prompt
    assert "Phòng khách" in prompt
    assert "living-light" in prompt
