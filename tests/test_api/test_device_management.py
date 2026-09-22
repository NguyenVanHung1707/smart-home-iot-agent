import pytest
from httpx import AsyncClient

from src.models.schemas import Device
from src.services.devices import DeviceRegistry


@pytest.mark.asyncio
async def test_create_and_delete_device(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    # 1. Create a new device
    payload = {
        "id": "balcony-light",
        "name": "Đèn ban công",
        "room": "Ban công",
        "kind": "light",
        "state": {"power": False, "brightness": 80},
    }
    create_resp = await client.post("/api/v1/devices", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] == "balcony-light"
    assert data["name"] == "Đèn ban công"
    assert data["room"] == "Ban công"
    assert data["kind"] == "light"
    assert data["state"]["brightness"] == 80

    # Verify duplicate id returns 409
    dup_resp = await client.post("/api/v1/devices", json=payload)
    assert dup_resp.status_code == 409

    # 2. Get the device
    get_resp = await client.get("/api/v1/devices/balcony-light")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == "balcony-light"

    # 3. Update the device
    update_resp = await client.put(
        "/api/v1/devices/balcony-light",
        json={"name": "Đèn ban công tầng 2", "room": "Tầng 2"},
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["name"] == "Đèn ban công tầng 2"
    assert updated_data["room"] == "Tầng 2"

    # 4. Delete the device
    del_resp = await client.delete("/api/v1/devices/balcony-light")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Verify 404 after deletion
    get_after_del = await client.get("/api/v1/devices/balcony-light")
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_auto_discovery_and_pairing(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    # 1. Initially no discovered devices
    resp = await client.get("/api/v1/discovery/devices")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Simulate discovered device added to registry
    test_reg.add_discovered(
        {
            "device_id": "garden-light",
            "name": "Đèn sân vườn",
            "room": "Sân vườn",
            "kind": "light",
            "state": {"power": False, "brightness": 100},
        }
    )

    resp = await client.get("/api/v1/discovery/devices")
    assert resp.status_code == 200
    discovered = resp.json()
    assert len(discovered) == 1
    assert discovered[0]["device_id"] == "garden-light"
    assert discovered[0]["name"] == "Đèn sân vườn"

    # 3. Pair the discovered device
    pair_resp = await client.post(
        "/api/v1/discovery/devices/garden-light/pair",
        json={"name": "Đèn vườn phía trước", "room": "Vườn trước"},
    )
    assert pair_resp.status_code == 200
    paired_device = pair_resp.json()
    assert paired_device["id"] == "garden-light"
    assert paired_device["name"] == "Đèn vườn phía trước"
    assert paired_device["room"] == "Vườn trước"

    # 4. Discovered list should now be empty and device is in devices list
    resp_after = await client.get("/api/v1/discovery/devices")
    assert resp_after.json() == []

    dev_resp = await client.get("/api/v1/devices/garden-light")
    assert dev_resp.status_code == 200


@pytest.mark.asyncio
async def test_dismiss_discovered_device(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    test_reg.add_discovered(
        {
            "device_id": "unknown-node",
            "name": "ESP32 Node 99",
        }
    )

    del_resp = await client.delete("/api/v1/discovery/devices/unknown-node")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "dismissed"

    # Verify it is no longer discovered
    resp = await client.get("/api/v1/discovery/devices")
    assert resp.json() == []


def test_heartbeat_watchdog_marks_stale_devices_offline(tmp_path):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    for device in (
        Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"),
        Device(id="living-temperature", name="Cảm biến nhiệt độ", room="Phòng khách", kind="sensor"),
    ):
        test_reg.add(device)

    # 1. Record heartbeat for Home Appliances board node
    test_reg.record_heartbeat("esp32_home_appliances")

    # All home appliances devices should be online
    assert test_reg.get("living-light").online is True
    assert test_reg.get("living-temperature").online is True

    # 2. Fast-forward last_seen to simulate 15 seconds elapsed
    for dev_id in list(test_reg._last_seen.keys()):
        test_reg._last_seen[dev_id] -= 20.0

    # 3. Check stale devices
    stale_ids = test_reg.check_stale_devices(timeout_seconds=12.0)
    assert "living-light" in stale_ids
    assert "living-temperature" in stale_ids

    # Devices should now be marked offline
    assert test_reg.get("living-light").online is False
    assert test_reg.get("living-temperature").online is False

    # 4. Device sends telemetry again (only reporting device comes back online)
    test_reg.update_state("living-temperature", {"temperature": 28.0, "humidity": 60.0}, online=True)

    # Only living-temperature should come back online (no cross-device resurrection)
    assert test_reg.get("living-light").online is False
    assert test_reg.get("living-temperature").online is True

    # 5. Node heartbeat brings entire node back online
    test_reg.record_heartbeat("esp32_home_appliances")
    assert test_reg.get("living-light").online is True
    assert test_reg.get("living-temperature").online is True


@pytest.mark.asyncio
async def test_rename_room_endpoint(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    for device in (
        Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"),
        Device(id="bedroom-light", name="Đèn phòng ngủ", room="Phòng ngủ", kind="light"),
        Device(id="bedroom-fan", name="Quạt phòng ngủ", room="Phòng ngủ", kind="fan"),
    ):
        test_reg.add(device)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    # Initially bedroom-light is in "Phòng ngủ"
    assert test_reg.get("bedroom-light").room == "Phòng ngủ"

    # Rename "Phòng ngủ" -> "Phòng ngủ Master"
    resp = await client.post("/api/v1/rooms/rename", json={"old_name": "Phòng ngủ", "new_name": "Phòng ngủ Master"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["old_name"] == "Phòng ngủ"
    assert data["new_name"] == "Phòng ngủ Master"
    assert data["updated_devices_count"] >= 2

    # Check updated device in registry
    assert test_reg.get("bedroom-light").room == "Phòng ngủ Master"
    assert test_reg.get("bedroom-fan").room == "Phòng ngủ Master"


@pytest.mark.asyncio
async def test_delete_room_endpoint(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "test_del_room_devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    for device in (
        Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"),
        Device(id="bedroom-light", name="Đèn phòng ngủ", room="Phòng ngủ", kind="light"),
        Device(id="bedroom-fan", name="Quạt phòng ngủ", room="Phòng ngủ", kind="fan"),
    ):
        test_reg.add(device)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    # Initial rooms list includes "Phòng ngủ"
    assert "Phòng ngủ" in test_reg.rooms()
    assert test_reg.get("bedroom-light") is not None
    assert test_reg.get("bedroom-fan") is not None

    # Delete "Phòng ngủ"
    resp = await client.delete("/api/v1/rooms/Phòng ngủ")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"
    assert data["room"] == "Phòng ngủ"
    assert data["deleted_devices_count"] == 2
    assert set(data["deleted_devices"]) == {"bedroom-light", "bedroom-fan"}

    # Verify devices are deleted from registry
    assert test_reg.get("bedroom-light") is None
    assert test_reg.get("bedroom-fan") is None
    assert "Phòng ngủ" not in test_reg.rooms()
    # "Phòng khách" remains intact
    assert "Phòng khách" in test_reg.rooms()
    assert test_reg.get("living-light") is not None


@pytest.mark.asyncio
async def test_trigger_discovery_scan_endpoint(client: AsyncClient, monkeypatch):
    class DummyMqttHub:
        def __init__(self):
            self.last_mode = None

        def trigger_discovery_scan(self, mode: str = "real"):
            self.last_mode = mode
            return True

    hub = DummyMqttHub()
    monkeypatch.setattr("src.api.routes.get_mqtt_hub", lambda: hub)

    # 1. Default (no params or headers) defaults to simulator
    resp = await client.post("/api/v1/discovery/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scan_initiated"
    assert "Simulator" in data["message"]
    assert hub.last_mode == "simulator"

    # 2. Real mode via Query parameter
    resp = await client.post("/api/v1/discovery/scan?mode=real")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scan_initiated"
    assert "ESP32" in data["message"]
    assert hub.last_mode == "real"

    # 3. Real mode via X-Data-Mode header
    resp = await client.post("/api/v1/discovery/scan", headers={"X-Data-Mode": "real"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scan_initiated"
    assert "ESP32" in data["message"]
    assert hub.last_mode == "real"

    # 4. Mode query param overrides header
    resp = await client.post("/api/v1/discovery/scan?mode=simulator", headers={"X-Data-Mode": "real"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scan_initiated"
    assert "Simulator" in data["message"]
    assert hub.last_mode == "simulator"


@pytest.mark.asyncio
async def test_trigger_discovery_scan_clears_discovered(client: AsyncClient, monkeypatch):
    class DummyMqttHub:
        def trigger_discovery_scan(self, mode: str = "real"):
            return True

    monkeypatch.setattr("src.api.routes.get_mqtt_hub", lambda: DummyMqttHub())

    import src.services.devices as devices_mod
    sim_reg = devices_mod.get_registry("simulator")
    real_reg = devices_mod.get_registry("real")

    # Add stale discovered devices
    sim_reg.add_discovered({"device_id": "stale-sim-dev", "name": "Stale Sim", "kind": "light"})
    real_reg.add_discovered({"device_id": "stale-real-dev", "name": "Stale Real", "kind": "fan"})

    assert any(d["device_id"] == "stale-sim-dev" for d in sim_reg.list_discovered())
    assert any(d["device_id"] == "stale-real-dev" for d in real_reg.list_discovered())

    # Trigger scan in simulator mode clears simulator discovered devices
    resp = await client.post("/api/v1/discovery/scan?mode=simulator")
    assert resp.status_code == 200
    assert not any(d["device_id"] == "stale-sim-dev" for d in sim_reg.list_discovered())
    assert any(d["device_id"] == "stale-real-dev" for d in real_reg.list_discovered())

    # Trigger scan in real mode clears real discovered devices
    resp = await client.post("/api/v1/discovery/scan?mode=real")
    assert resp.status_code == 200
    assert not any(d["device_id"] == "stale-real-dev" for d in real_reg.list_discovered())

    # Re-add to both and test "all" mode
    sim_reg.add_discovered({"device_id": "stale-sim-2", "name": "Stale Sim 2", "kind": "light"})
    real_reg.add_discovered({"device_id": "stale-real-2", "name": "Stale Real 2", "kind": "fan"})
    resp = await client.post("/api/v1/discovery/scan?mode=all")
    assert resp.status_code == 200
    assert not any(d["device_id"] == "stale-sim-2" for d in sim_reg.list_discovered())
    assert not any(d["device_id"] == "stale-real-2" for d in real_reg.list_discovered())



@pytest.mark.asyncio
async def test_auto_discovery_infers_and_preserves_all_kinds(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    devices_to_discover = [
        {
            "device_id": "living-aircon-2",
            "name": "Điều hòa phụ",
            "room": "Phòng khách",
            "state": {"target_temperature": 26, "mode": "cool"},
        },
        {"device_id": "balcony-blind", "name": "Rèm ban công", "room": "Ban công", "state": {"position": 0}},
        {
            "device_id": "bedroom-speaker",
            "name": "Loa phòng ngủ",
            "room": "Phòng ngủ",
            "state": {"volume": 30, "playing": False},
        },
        {
            "device_id": "hallway-display",
            "name": "Màn hình hành lang",
            "room": "Hành lang",
            "state": {"text": "Welcome"},
        },
        {"device_id": "kitchen-fan-2", "name": "Quạt bếp", "room": "Phòng bếp", "state": {"speed": 60, "power": True}},
        {"device_id": "backdoor-lock", "name": "Khóa cửa sau", "room": "Cửa sau", "state": {"locked": True}},
        {
            "device_id": "balcony-motion",
            "name": "Cảm biến ban công",
            "room": "Ban công",
            "state": {"motion": False, "battery": 95},
        },
    ]

    for item in devices_to_discover:
        test_reg.add_discovered(item)

    resp = await client.get("/api/v1/discovery/devices")
    assert resp.status_code == 200
    discovered = {item["device_id"]: item for item in resp.json()}

    assert discovered["living-aircon-2"]["kind"] == "aircon"
    assert discovered["balcony-blind"]["kind"] == "blind"
    assert discovered["bedroom-speaker"]["kind"] == "speaker"
    assert discovered["hallway-display"]["kind"] == "display"
    assert discovered["kitchen-fan-2"]["kind"] == "fan"
    assert discovered["backdoor-lock"]["kind"] == "lock"
    assert discovered["balcony-motion"]["kind"] == "sensor"

    # Pair each device and verify kind & capabilities
    for item in devices_to_discover:
        d_id = item["device_id"]
        pair_resp = await client.post(f"/api/v1/discovery/devices/{d_id}/pair")
        assert pair_resp.status_code == 200
        paired = pair_resp.json()
        assert paired["kind"] == discovered[d_id]["kind"]


@pytest.mark.asyncio
async def test_control_various_device_kinds_via_api(client: AsyncClient, tmp_path, monkeypatch):
    test_storage = tmp_path / "devices.json"
    test_reg = DeviceRegistry(storage_path=test_storage)
    monkeypatch.setattr("src.api.routes.registry", test_reg)
    monkeypatch.setattr("src.services.devices.registry", test_reg)

    test_reg.add(
        Device(
            id="test-aircon",
            name="AC",
            room="Living",
            kind="aircon",
            state={"power": False, "target_temperature": 25, "mode": "cool"},
        )
    )
    test_reg.add(
        Device(id="test-blind", name="Blind", room="Living", kind="blind", state={"position": 0, "power": False})
    )
    test_reg.add(
        Device(
            id="test-speaker",
            name="Speaker",
            room="Living",
            kind="speaker",
            state={"power": False, "volume": 30, "playing": False},
        )
    )
    test_reg.add(Device(id="test-fan", name="Fan", room="Living", kind="fan", state={"power": False, "speed": 50}))
    test_reg.add(
        Device(id="test-display", name="Display", room="Living", kind="display", state={"power": True, "text": ""})
    )

    # Control aircon
    resp = await client.post(
        "/api/v1/devices/test-aircon/command",
        json={"action": "set", "value": {"target_temperature": 22, "mode": "cool"}},
    )
    assert resp.status_code == 200
    assert resp.json()["state"]["target_temperature"] == 22

    # Control blind
    resp = await client.post("/api/v1/devices/test-blind/command", json={"action": "open"})
    assert resp.status_code == 200

    # Control speaker
    resp = await client.post("/api/v1/devices/test-speaker/command", json={"action": "set", "value": {"volume": 65}})
    assert resp.status_code == 200
    assert resp.json()["state"]["volume"] == 65

    # Control fan
    resp = await client.post("/api/v1/devices/test-fan/command", json={"action": "set", "value": {"speed": 80}})
    assert resp.status_code == 200
    assert resp.json()["state"]["speed"] == 80

    # Control display
    resp = await client.post(
        "/api/v1/devices/test-display/command", json={"action": "set", "value": {"text": "Hello HomeMind"}}
    )
    assert resp.status_code == 200
    assert resp.json()["state"]["text"] == "Hello HomeMind"


@pytest.mark.asyncio
async def test_dual_database_isolation_between_simulator_and_real(client: AsyncClient, tmp_path, monkeypatch):
    sim_storage = tmp_path / "devices_sim.json"
    real_storage = tmp_path / "devices_real.json"

    sim_reg = DeviceRegistry(storage_path=sim_storage)
    sim_reg.add(Device(id="sim-lamp", name="Simulated Lamp", room="Phòng khách", kind="light"))

    real_reg = DeviceRegistry(storage_path=real_storage)
    real_reg.add(Device(id="real-lamp", name="Real ESP32 Lamp", room="Phòng khách", kind="light"))

    def mock_get_registry(mode: str | None = None):
        if str(mode).strip().lower() in {"real", "live"}:
            return real_reg
        return sim_reg

    monkeypatch.setattr("src.services.devices.get_registry", mock_get_registry)
    monkeypatch.setattr("src.api.deps.devices_mod.get_registry", mock_get_registry)

    # 1. Querying simulator mode
    resp_sim = await client.get("/api/v1/devices", headers={"X-Data-Mode": "simulator"})
    assert resp_sim.status_code == 200
    sim_ids = [d["id"] for d in resp_sim.json()]
    assert "sim-lamp" in sim_ids
    assert "real-lamp" not in sim_ids

    # 2. Querying real mode
    resp_real = await client.get("/api/v1/devices", headers={"X-Data-Mode": "real"})
    assert resp_real.status_code == 200
    real_ids = [d["id"] for d in resp_real.json()]
    assert "real-lamp" in real_ids
    assert "sim-lamp" not in real_ids

    # 3. Create a device in real mode
    create_real = await client.post(
        "/api/v1/devices",
        json={"id": "esp32-fan", "name": "ESP32 Quạt", "room": "Phòng ngủ", "kind": "fan"},
        headers={"X-Data-Mode": "real"},
    )
    assert create_real.status_code == 201

    # Verify device exists in real mode but NOT in simulator mode
    resp_real_after = await client.get("/api/v1/devices", headers={"X-Data-Mode": "real"})
    assert "esp32-fan" in [d["id"] for d in resp_real_after.json()]

    resp_sim_after = await client.get("/api/v1/devices", headers={"X-Data-Mode": "simulator"})
    assert "esp32-fan" not in [d["id"] for d in resp_sim_after.json()]

    # 4. Delete device in real mode
    del_real = await client.delete("/api/v1/devices/real-lamp", headers={"X-Data-Mode": "real"})
    assert del_real.status_code == 200

    # Verify real-lamp is gone in real mode
    resp_real_del = await client.get("/api/v1/devices", headers={"X-Data-Mode": "real"})
    assert "real-lamp" not in [d["id"] for d in resp_real_del.json()]
