import json

from src.agents import system_prompt
from src.agents.tools import smart_home_tools
from src.models.schemas import Device
from src.services.devices import DeviceRegistry


def test_registry_crud_and_dynamic_kind_tool(tmp_path, monkeypatch):
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.add(
        Device(
            id="office-thermostat",
            name="Thermostat văn phòng",
            room="Văn phòng",
            kind="thermostat",
            state={"power": False, "target": 22},
            capabilities={
                "actions": ["on", "off", "set"],
                "set_fields": {"target": {"type": "integer", "minimum": 10, "maximum": 35}},
                "requires_approval": [],
            },
        )
    )

    monkeypatch.setattr(smart_home_tools, "registry", registry)
    monkeypatch.setattr(system_prompt, "registry", registry)
    tools = smart_home_tools.get_runtime_tools()

    assert registry.rooms() == ["Văn phòng"]
    assert registry.get("office-thermostat") is not None
    assert "control_thermostat" in {tool.name for tool in tools}
    assert "control_thermostat" in system_prompt.build_system_prompt()
    assert registry.validate_command("office-thermostat", "set", {"target": 24})[1] is None

    assert registry.update("office-thermostat", {"room": "Phòng họp"}) is not None
    assert registry.rename_room("Phòng họp", "Phòng lab")
    assert registry.delete("office-thermostat") is True


def test_registry_infer_kind(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")

    assert registry._infer_kind("door-lock", {}) == "lock"
    assert registry._infer_kind("some-dev", {"locked": True}) == "lock"
    assert registry._infer_kind("ac-unit", {}) == "aircon"
    assert registry._infer_kind("dev-1", {"target_temperature": 25}) == "aircon"
    assert registry._infer_kind("dev-2", {"position": 50}) == "blind"
    assert registry._infer_kind("window-blind", {}) == "blind"
    assert registry._infer_kind("music-player", {}) == "speaker"
    assert registry._infer_kind("dev-3", {"volume": 80}) == "speaker"
    assert registry._infer_kind("living-screen", {}) == "display"
    assert registry._infer_kind("dev-4", {"message": "hello"}) == "display"
    assert registry._infer_kind("dev-5", {"speed": 50}) == "fan"
    assert registry._infer_kind("ceiling-fan", {}) == "fan"
    assert registry._infer_kind("temp-sensor", {}) == "sensor"
    assert registry._infer_kind("dev-6", {"gas_detected": False, "ppm": 50}) == "sensor"
    assert registry._infer_kind("dev-7", {"brightness": 70}) == "light"


def test_discovery_and_pair_preserves_inferred_kind_and_capabilities(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")

    # Add discovered aircon without explicit kind
    registry.add_discovered(
        {
            "device_id": "bedroom-ac",
            "name": "Điều hòa phòng ngủ",
            "room": "Phòng ngủ",
            "state": {"target_temperature": 24, "mode": "cool"},
        }
    )

    discovered = registry.list_discovered()
    assert len(discovered) == 1
    assert discovered[0]["kind"] == "aircon"
    assert "target_temperature" in discovered[0]["capabilities"]["set_fields"]

    # Pair the device
    paired = registry.pair_discovered("bedroom-ac")
    assert paired is not None
    assert paired.kind == "aircon"
    assert "target_temperature" in paired.capabilities["set_fields"]


def test_registry_update_kind(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.add(
        Device(
            id="multi-dev",
            name="Thiết bị đa năng",
            room="Phòng khách",
            kind="light",
            state={"power": True},
        )
    )

    updated = registry.update("multi-dev", {"kind": "fan"})
    assert updated is not None
    assert updated.kind == "fan"
    assert registry.get("multi-dev").kind == "fan"


def test_node_groups_independent_heartbeat(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.add(Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"))
    registry.add(Device(id="bedroom-light", name="Đèn phòng ngủ", room="Phòng ngủ", kind="light"))
    registry.add(Device(id="entry-lock", name="Khóa cổng", room="Lối vào", kind="lock"))
    registry.add(Device(id="custom-plug", name="Ổ cắm", room="Phòng làm việc", kind="switch"))

    # Heartbeat from esp32_home_appliances node
    registry.record_heartbeat("esp32_home_appliances")
    # All devices on ESP32 Home Appliances should be online
    assert registry.get("living-light").online is True
    assert registry.get("bedroom-light").online is True

    # Fast-forward last_seen for entry-lock and custom-plug
    registry._last_seen["entry-lock"] -= 40.0
    registry._last_seen["custom-plug"] -= 40.0

    stale = registry.check_stale_devices(timeout_seconds=30.0)
    assert "entry-lock" in stale
    assert "custom-plug" in stale
    assert "living-light" not in stale
    assert "bedroom-light" not in stale

    # Node LWT sets all appliances offline
    registry.set_node_online("esp32_home_appliances", False)
    assert registry.get("living-light").online is False
    assert registry.get("bedroom-light").online is False


def test_no_cross_device_heartbeat_resurrection(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.add(Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light", online=False))
    registry.add(Device(id="bedroom-light", name="Đèn phòng ngủ", room="Phòng ngủ", kind="light", online=False))

    assert registry.get("living-light").online is False
    assert registry.get("bedroom-light").online is False

    # 1. Heartbeat from bedroom-light must NOT resurrect living-light
    registry.record_heartbeat("bedroom-light")
    assert registry.get("bedroom-light").online is True
    assert registry.get("living-light").online is False

    # 2. Reset bedroom-light to offline, then test update_state with online=True
    registry.set_online("bedroom-light", False)
    assert registry.get("bedroom-light").online is False
    assert registry.get("living-light").online is False

    registry.update_state("bedroom-light", {"power": True}, online=True)
    assert registry.get("bedroom-light").online is True
    assert registry.get("living-light").online is False

    # 3. Heartbeat from node_id esp32_home_appliances updates entire node
    registry.record_heartbeat("esp32_home_appliances")
    assert registry.get("living-light").online is True
    assert registry.get("bedroom-light").online is True


def test_initial_offline_device_not_in_last_seen(tmp_path):
    storage_path = tmp_path / "devices.json"
    storage_path.write_text(
        json.dumps(
            [
                {"id": "dev-online", "name": "Online Dev", "kind": "light", "room": "R1", "online": True},
                {"id": "dev-offline", "name": "Offline Dev", "kind": "light", "room": "R1", "online": False},
            ]
        ),
        encoding="utf-8",
    )
    reg = DeviceRegistry(storage_path)
    assert "dev-online" in reg._last_seen
    assert "dev-offline" not in reg._last_seen
    assert reg.get("dev-offline").online is False


def test_check_stale_devices_saves_to_disk(tmp_path):
    storage_path = tmp_path / "devices.json"
    reg = DeviceRegistry(storage_path)
    reg.add(Device(id="lamp-1", name="Lamp 1", kind="light", room="R1", online=True))
    assert reg.get("lamp-1").online is True

    # Fast forward last seen
    reg._last_seen["lamp-1"] -= 60.0
    stale = reg.check_stale_devices(timeout_seconds=30.0)
    assert "lamp-1" in stale
    assert reg.get("lamp-1").online is False

    # Check file on disk was saved with online: False
    saved = json.loads(storage_path.read_text(encoding="utf-8"))
    saved_lamp = next(d for d in saved if d["id"] == "lamp-1")
    assert saved_lamp["online"] is False


def test_clear_discovered(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.add_discovered(
        {
            "device_id": "test-dev-1",
            "name": "Thiết bị 1",
            "room": "Phòng khách",
            "kind": "light",
        }
    )
    registry.add_discovered(
        {
            "device_id": "test-dev-2",
            "name": "Thiết bị 2",
            "room": "Phòng ngủ",
            "kind": "fan",
        }
    )
    assert len(registry.list_discovered()) == 2
    registry.clear_discovered()
    assert len(registry.list_discovered()) == 0


def test_real_registry_stale_devices_check(tmp_path):
    storage_path = tmp_path / "devices_real.json"
    reg = DeviceRegistry(storage_path)
    reg.add(Device(id="living-fan", name="Quạt phòng khách", kind="fan", room="Phòng khách", online=True))
    reg.add(Device(id="living-light-sensor", name="Cảm biến ánh sáng", kind="sensor", room="Phòng khách", online=True))
    reg.add(Device(id="living-display", name="Màn hình OLED", kind="display", room="Phòng khách", online=True))
    reg.add(Device(id="living-blind", name="Cửa sổ thông gió", kind="blind", room="Phòng khách", online=True))

    assert reg.get("living-fan").online is True
    assert reg.get("living-light-sensor").online is True
    assert reg.get("living-display").online is True
    assert reg.get("living-blind").online is True

    # Fast forward last seen for all hardware devices
    for dev_id in ("living-fan", "living-light-sensor", "living-display", "living-blind"):
        reg._last_seen[dev_id] -= 60.0

    stale = reg.check_stale_devices(timeout_seconds=30.0)
    assert "living-fan" in stale
    assert "living-light-sensor" in stale
    assert "living-display" in stale
    assert "living-blind" in stale

    assert reg.get("living-fan").online is False
    assert reg.get("living-light-sensor").online is False
    assert reg.get("living-display").online is False
    assert reg.get("living-blind").online is False



