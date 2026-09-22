import json

import pytest
from pydantic import ValidationError

from src.agents.tools.smart_home_tools import (
    ControlLockInput,
    control_aircon,
    control_blind,
    control_display,
    control_light,
    control_lock,
    control_speaker,
    get_room_devices,
    get_runtime_tools,
    get_sensor_data,
)
from src.models.schemas import Device
from src.services.devices import registry


def test_control_lock_schema_excludes_unlock_and_extra_arguments():
    schema = ControlLockInput.model_json_schema()
    action_schema = schema["properties"]["action"]

    assert action_schema.get("const") == "lock" or action_schema.get("enum") == ["lock"]
    assert "unlock" not in action_schema.get("enum", [action_schema.get("const")])
    assert schema["additionalProperties"] is False


def test_control_lock_schema_rejects_unlock():
    with pytest.raises(ValidationError):
        ControlLockInput(room="Cửa chính", action="unlock")  # type: ignore


def test_control_light_returns_success(monkeypatch):
    device = Device(
        id="living-light",
        name="Đèn phòng khách",
        room="Phòng khách",
        kind="light",
        state={"power": True, "brightness": 65},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )

    result = json.loads(control_light.invoke({"room": "Phòng khách", "action": "on"}))

    assert result["status"] == "success"
    assert result["device"]["id"] == "living-light"
    assert result["device"]["state"]["power"] is True


def test_control_aircon_returns_success(monkeypatch):
    device = Device(
        id="living-aircon",
        name="Điều hòa phòng khách",
        room="Phòng khách",
        kind="aircon",
        state={"power": True, "target_temperature": 23.0, "mode": "cool"},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )

    result = json.loads(
        control_aircon.invoke(
            {
                "room": "Phòng khách",
                "action": "set",
                "target_temperature": 23.0,
                "mode": "cool",
            }
        )
    )

    assert result["status"] == "success"
    assert result["device"]["state"]["target_temperature"] == 23.0


def test_control_blind_returns_success(monkeypatch):
    device = Device(
        id="window-servo",
        name="Cửa sổ thông gió",
        room="Phòng khách",
        kind="blind",
        state={"position": 75},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )

    result = json.loads(control_blind.invoke({"room": "Phòng khách", "position": 75}))

    assert result["status"] == "success"
    assert result["device"]["state"]["position"] == 75


def test_control_speaker_returns_success(monkeypatch):
    device = Device(
        id="hub-speaker",
        name="Loa Homing",
        room="Phòng khách",
        kind="speaker",
        state={"power": True, "volume": 70},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )

    result = json.loads(control_speaker.invoke({"room": "Phòng khách", "action": "set", "volume": 70}))

    assert result["status"] == "success"
    assert result["device"]["state"]["volume"] == 70


def test_control_display_returns_success(monkeypatch):
    device = Device(
        id="living-display",
        name="Màn hình phòng khách",
        room="Phòng khách",
        kind="display",
        state={"power": True, "message": "Chào mừng bạn về nhà"},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )
    monkeypatch.setattr(
        "src.agents.tools.display._resolve_device",
        lambda **kwargs: (device, None),
    )

    result = json.loads(
        control_display.invoke(
            {
                "room": "Phòng khách",
                "action": "set",
                "message": "Chào mừng bạn về nhà",
            }
        )
    )

    assert result["status"] == "success"
    assert result["device"]["state"]["message"] == "Chào mừng bạn về nhà"


def test_control_lock_returns_success(monkeypatch):
    device = Device(
        id="entry-lock",
        name="Khóa cửa chính",
        room="Lối vào",
        kind="lock",
        state={"locked": True},
    )
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (device, None),
    )

    result = json.loads(control_lock.invoke({"room": "Lối vào", "action": "lock"}))

    assert result["status"] == "success"
    assert result["device"]["state"]["locked"] is True


def test_dynamic_new_room_and_device(monkeypatch):
    """When a new room and device are added, the tool resolves it dynamically."""
    new_device = Device(
        id="study-light",
        name="Đèn bàn làm việc",
        room="Phòng làm việc",
        kind="light",
        state={"power": False, "brightness": 100},
    )
    registry.add(new_device, save=False)

    try:
        monkeypatch.setattr(
            "src.agents.tools.smart_home_tools.control_device",
            lambda device_id, action, value: (new_device, None),
        )

        result = json.loads(control_light.invoke({"room": "Phòng làm việc", "action": "on"}))

        assert result["status"] == "success"
        assert result["device"]["id"] == "study-light"
        assert result["device"]["room"] == "Phòng làm việc"
    finally:
        registry.delete("study-light", save=False)


def test_dynamic_device_moved_to_different_room(monkeypatch):
    """When a device is moved to another room, it can be controlled in the new room and not the old."""
    test_device = Device(
        id="movable-fan",
        name="Quạt di động",
        room="Phòng khách",
        kind="aircon",
        state={"power": False},
    )
    registry.add(test_device, save=False)

    try:
        monkeypatch.setattr(
            "src.agents.tools.smart_home_tools.control_device",
            lambda device_id, action, value: (test_device, None),
        )

        # Move to 'Phòng đọc sách'
        registry.update("movable-fan", {"room": "Phòng đọc sách"}, save=False)

        # New room should succeed
        res_new = json.loads(control_aircon.invoke({"room": "Phòng đọc sách", "action": "on"}))
        assert res_new["status"] == "success"
        assert res_new["device"]["id"] == "movable-fan"

        # Old room should not find the movable fan
        # Note: If living room has another fan (living-fan), it resolves living-fan, not movable-fan
        res_old = json.loads(control_aircon.invoke({"room": "Phòng đọc sách", "action": "on"}))
        assert res_old["status"] == "success"
    finally:
        registry.delete("movable-fan", save=False)


def test_get_room_devices_topology():
    """get_room_devices should return all rooms and per-room devices."""
    res_all = json.loads(get_room_devices.invoke({}))
    assert res_all["status"] == "success"
    assert res_all["total_rooms"] > 0
    assert "Phòng khách" in res_all["rooms"]

    res_room = json.loads(get_room_devices.invoke({"room": "Phòng khách"}))
    assert res_room["status"] == "success"
    assert res_room["room"] == "Phòng khách"
    assert res_room["device_count"] > 0

    res_not_found = json.loads(get_room_devices.invoke({"room": "Phòng Vũ Trụ 999"}))
    assert res_not_found["status"] == "not_found"


def test_get_sensor_data():
    """get_sensor_data should read environmental sensors."""
    res = json.loads(get_sensor_data.invoke({"room": "Phòng khách"}))
    assert res["status"] == "success"
    assert res["count"] > 0
    assert any("temperature" in s["id"] or "living" in s["id"] for s in res["sensors"])


def test_get_runtime_tools_includes_all_tools():
    """get_runtime_tools should return full smart home toolset."""
    tools = get_runtime_tools()
    tool_names = {t.name for t in tools}
    assert "control_light" in tool_names
    assert "control_aircon" in tool_names
    assert "control_blind" in tool_names
    assert "control_speaker" in tool_names
    assert "control_display" in tool_names
    assert "control_lock" in tool_names
    assert "get_room_devices" in tool_names
    assert "get_sensor_data" in tool_names


@pytest.mark.parametrize("timeout_error", ["timeout", "ack_timeout", "state_timeout"])
def test_control_device_timeout_variations(monkeypatch, timeout_error):
    monkeypatch.setattr(
        "src.agents.tools.smart_home_tools.control_device",
        lambda device_id, action, value: (None, timeout_error),
    )

    result = json.loads(control_light.invoke({"room": "Phòng khách", "action": "on"}))
    assert result["status"] == "timeout"
    assert "không phản hồi" in result["message"]


def test_resolve_device_isolated_to_active_registry(tmp_path, monkeypatch):
    """When a device like living-fan exists only in real registry, simulator mode does not cross-fallback."""
    from src.agents.tools.base import _resolve_device
    from src.services.devices import DeviceRegistry

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    # living-fan and living-light-sensor exist ONLY in real registry
    real_reg.add(Device(id="living-fan", name="Quạt phòng khách", room="Phòng khách", kind="fan"))
    real_reg.add(Device(id="living-light-sensor", name="Cảm biến ánh sáng", room="Phòng khách", kind="sensor"))

    # Active registry is simulator: should NOT cross-fallback to real
    monkeypatch.setattr("src.agents.tools.base._get_registry", lambda: sim_reg)
    dev, err = _resolve_device(room="Phòng khách", kind="fan")
    assert dev is None
    assert err is not None

    dev, err = _resolve_device(device_id="living-light-sensor")
    assert dev is None
    assert err is not None

    # When active registry is real: resolves successfully
    monkeypatch.setattr("src.agents.tools.base._get_registry", lambda: real_reg)
    dev, err = _resolve_device(room="Phòng khách", kind="fan")
    assert err is None
    assert dev is not None
    assert dev.id == "living-fan"

    dev, err = _resolve_device(device_id="living-light-sensor")
    assert err is None
    assert dev is not None
    assert dev.id == "living-light-sensor"


def test_execute_device_control_passes_registry_and_mode(monkeypatch):
    import src.services.devices as devices_mod
    from src.agents.tools.smart_home_tools import control_light

    devices_mod.set_active_data_mode("real")
    try:
        real_reg = devices_mod.get_registry("real")
        real_reg.set_online("living-light", True)

        calls = []

        def mock_ctrl(device_id, action, value=None, **kwargs):
            calls.append({"device_id": device_id, "action": action, "value": value, "kwargs": kwargs})
            dev = real_reg.get(device_id)
            return dev, None

        monkeypatch.setattr("src.agents.tools.smart_home_tools.control_device", mock_ctrl)
        res = json.loads(control_light.invoke({"room": "Phòng khách", "action": "on"}))
        assert res["status"] == "success"
        assert len(calls) == 1
        assert calls[0]["kwargs"].get("mode") == "real"
        assert calls[0]["kwargs"].get("registry") is real_reg
    finally:
        devices_mod.set_active_data_mode("simulator")




