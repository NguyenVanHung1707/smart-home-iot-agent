import json

from src.services.mqtt import device_ack_topic, device_command_topic, device_state_message, device_state_topic


def test_device_state_topic_uses_configured_prefix():
    assert device_state_topic("living-light") == "homing/devices/living-light/state"
    assert device_command_topic("living-light") == "homing/devices/living-light/command"
    assert device_ack_topic("living-light") == "homing/devices/living-light/ack"


def test_device_state_message_has_a_versioned_envelope():
    message = json.loads(device_state_message("living-light", {"power": True}))

    assert message["schema_version"] == 1
    assert message["event"] == "device.state"
    assert message["device_id"] == "living-light"
    assert message["state"] == {"power": True}
    assert message["timestamp"].endswith("+00:00")


def test_lwt_offline_message_marks_device_offline(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    reg = DeviceRegistry(tmp_path / "devices.json")
    reg.add(Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"))
    assert reg.get("living-light").online is True

    monkeypatch.setattr("src.services.mqtt._registry", lambda: reg)

    hub = MqttHub()
    # Simulate LWT message arriving on homing/devices/living-light/lwt
    msg = MagicMock()
    msg.topic = "homing/devices/living-light/lwt"
    msg.payload = json.dumps({"device_id": "living-light", "online": False, "status": "offline"}).encode()

    hub._on_message(None, None, msg)
    assert reg.get("living-light").online is False


def test_node_lwt_offline_marks_all_node_devices_offline(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    reg = DeviceRegistry(tmp_path / "devices.json")
    reg.add(Device(id="living-light", name="Đèn phòng khách", room="Phòng khách", kind="light"))
    reg.add(Device(id="bedroom-light", name="Đèn phòng ngủ", room="Phòng ngủ", kind="light"))
    assert reg.get("living-light").online is True
    assert reg.get("bedroom-light").online is True

    monkeypatch.setattr("src.services.mqtt._registry", lambda: reg)

    hub = MqttHub()
    # Simulate Node LWT message arriving on homing/nodes/esp32_home_appliances/lwt
    msg = MagicMock()
    msg.topic = "homing/nodes/esp32_home_appliances/lwt"
    msg.payload = json.dumps({"node_id": "esp32_home_appliances", "online": False, "status": "offline"}).encode()

    hub._on_message(None, None, msg)
    assert reg.get("living-light").online is False
    assert reg.get("bedroom-light").online is False


def test_simulator_message_routes_only_to_simulator_registry(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    sim_reg.add(Device(id="living-light", name="Simulator Light", room="Phòng khách", kind="light", online=False, state={"power": False}))
    real_reg.add(Device(id="living-light", name="Real Light", room="Phòng khách", kind="light", online=False, state={"power": False}))

    monkeypatch.setattr(
        "src.services.mqtt._target_registries",
        lambda is_sim: [sim_reg] if is_sim else [sim_reg, real_reg],
    )

    hub = MqttHub()
    # Simulator state message arrives
    msg = MagicMock()
    msg.topic = "homing/devices/living-light/state"
    msg.payload = json.dumps(
        {
            "device_id": "living-light",
            "source": "simulator",
            "state": {"power": True},
            "online": True,
        }
    ).encode()

    hub._on_message(None, None, msg)

    # Simulator registry should be updated to online, real registry untouched
    assert sim_reg.get("living-light").online is True
    assert sim_reg.get("living-light").state["power"] is True
    assert real_reg.get("living-light").online is False
    assert real_reg.get("living-light").state["power"] is False


def test_command_ack_timeout_marks_device_offline(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub, VerificationStatus

    reg = DeviceRegistry(tmp_path / "devices.json")
    reg.add(Device(id="living-light", name="Light", room="Phòng khách", kind="light", online=True))
    assert reg.get("living-light").online is True

    monkeypatch.setattr("src.services.mqtt._registry", lambda: reg)
    monkeypatch.setattr("src.services.mqtt._all_registries", lambda: [reg])

    hub = MqttHub()
    hub.settings.mqtt_enabled = True
    mock_client = MagicMock()
    hub.client = mock_client

    result = hub.command("living-light", "on", timeout=0.01)

    assert result.status is VerificationStatus.INDETERMINATE
    assert result.reason == "ack_timeout"
    # Device must be marked offline
    assert reg.get("living-light").online is False

    # Event logged
    events = [e for e in hub.events if e.get("type") == "timeout"]
    assert len(events) == 1
    assert events[0]["device_id"] == "living-light"
    assert events[0]["status"] == "offline"
    assert events[0]["online"] is False


def test_trigger_discovery_scan_topics_by_mode(monkeypatch):
    from unittest.mock import MagicMock

    from src.services.mqtt import MqttHub

    hub = MqttHub()
    hub.settings.mqtt_enabled = True
    monkeypatch.setattr(hub.settings, "app_env", "production")
    mock_client = MagicMock()
    hub.client = mock_client

    # Real mode
    mock_client.reset_mock()
    assert hub.trigger_discovery_scan(mode="real") is True
    assert mock_client.publish.call_count == 1
    assert mock_client.publish.call_args[0][0] == "homing/broadcast/scan"

    # Simulator mode
    mock_client.reset_mock()
    assert hub.trigger_discovery_scan(mode="simulator") is True
    assert mock_client.publish.call_count == 1
    assert mock_client.publish.call_args[0][0] == "homing/simulator/broadcast/scan"

    # All mode
    mock_client.reset_mock()
    assert hub.trigger_discovery_scan(mode="all") is True
    assert mock_client.publish.call_count == 2
    published_topics = [call[0][0] for call in mock_client.publish.call_args_list]
    assert "homing/broadcast/scan" in published_topics
    assert "homing/simulator/broadcast/scan" in published_topics


def test_discovery_topic_routing_isolation(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    import src.services.devices as devices_mod
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    def mock_get_registry(mode: str | None = None):
        if mode == "simulator":
            return sim_reg
        return real_reg

    monkeypatch.setattr(devices_mod, "get_registry", mock_get_registry)

    hub = MqttHub()

    # 1. Simulator discovery topic
    msg_sim_topic = MagicMock()
    msg_sim_topic.topic = "homing/simulator/discovery"
    msg_sim_topic.payload = json.dumps({
        "device_id": "sim-fan",
        "name": "Simulated Fan",
        "kind": "fan",
        "room": "Phòng khách",
        "source": "simulator",
    }).encode()
    hub._on_message(None, None, msg_sim_topic)

    assert any(d["device_id"] == "sim-fan" for d in sim_reg.list_discovered())
    assert not any(d["device_id"] == "sim-fan" for d in real_reg.list_discovered())

    # 2. General discovery topic with source: "simulator"
    msg_gen_sim = MagicMock()
    msg_gen_sim.topic = "homing/discovery"
    msg_gen_sim.payload = json.dumps({
        "device_id": "sim-light-2",
        "name": "Simulated Light 2",
        "kind": "light",
        "room": "Phòng khách",
        "source": "simulator",
    }).encode()
    hub._on_message(None, None, msg_gen_sim)

    assert any(d["device_id"] == "sim-light-2" for d in sim_reg.list_discovered())
    assert not any(d["device_id"] == "sim-light-2" for d in real_reg.list_discovered())

    # 3. Real ESP32 discovery on homing/discovery (without source="simulator")
    msg_real = MagicMock()
    msg_real.topic = "homing/discovery"
    msg_real.payload = json.dumps({
        "device_id": "esp32-living-light",
        "name": "Đèn ESP32",
        "kind": "light",
        "room": "Phòng khách",
    }).encode()
    hub._on_message(None, None, msg_real)

    assert any(d["device_id"] == "esp32-living-light" for d in real_reg.list_discovered())
    assert not any(d["device_id"] == "esp32-living-light" for d in sim_reg.list_discovered())


def test_state_topic_unknown_device_isolation(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    import src.services.devices as devices_mod
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    def mock_get_registry(mode: str | None = None):
        if mode == "simulator":
            return sim_reg
        return real_reg

    monkeypatch.setattr(devices_mod, "get_registry", mock_get_registry)
    monkeypatch.setattr("src.services.mqtt._target_registries", lambda is_sim: [sim_reg] if is_sim else [real_reg])

    hub = MqttHub()

    # State from unknown simulator device
    msg_sim_state = MagicMock()
    msg_sim_state.topic = "homing/devices/unknown-sim-device/state"
    msg_sim_state.payload = json.dumps({
        "device_id": "unknown-sim-device",
        "source": "simulator",
        "state": {"power": True},
    }).encode()
    hub._on_message(None, None, msg_sim_state)

    assert any(d["device_id"] == "unknown-sim-device" for d in sim_reg.list_discovered())
    assert not any(d["device_id"] == "unknown-sim-device" for d in real_reg.list_discovered())

    # State from unknown real device
    msg_real_state = MagicMock()
    msg_real_state.topic = "homing/devices/unknown-real-device/state"
    msg_real_state.payload = json.dumps({
        "device_id": "unknown-real-device",
        "state": {"power": True},
    }).encode()
    hub._on_message(None, None, msg_real_state)

    assert any(d["device_id"] == "unknown-real-device" for d in real_reg.list_discovered())
    assert not any(d["device_id"] == "unknown-real-device" for d in sim_reg.list_discovered())


def test_node_lwt_offline_does_not_affect_simulator_registry(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    import src.services.devices as devices_mod
    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    sim_reg.add(Device(id="living-light", name="Simulator Light", room="Phòng khách", kind="light", online=True))
    real_reg.add(Device(id="living-light", name="Real Light", room="Phòng khách", kind="light", online=True))

    def mock_get_registry(mode: str = "simulator"):
        if (mode or "").strip().lower() == "simulator":
            return sim_reg
        return real_reg

    monkeypatch.setattr(devices_mod, "get_registry", mock_get_registry)

    hub = MqttHub()
    msg = MagicMock()
    msg.topic = "homing/nodes/esp32_home_appliances/lwt"
    msg.payload = json.dumps({"node_id": "esp32_home_appliances", "online": False, "status": "offline"}).encode()

    hub._on_message(None, None, msg)

    # Real registry must be marked offline, simulator registry MUST remain online
    assert real_reg.get("living-light").online is False
    assert sim_reg.get("living-light").online is True


def test_device_command_topic_with_mode():
    assert device_command_topic("living-light", mode="simulator") == "homing/simulator/devices/living-light/command"
    assert device_command_topic("living-light", mode="real") == "homing/devices/living-light/command"
    assert device_command_topic("living-light") == "homing/devices/living-light/command"


def test_mqtt_hub_command_mode():
    from unittest.mock import MagicMock

    from src.services.mqtt import MqttHub

    hub = MqttHub()
    hub.settings.mqtt_enabled = True
    mock_client = MagicMock()
    hub.client = mock_client

    # Command in simulator mode
    hub.command("living-light", "on", timeout=0.01, mode="simulator")
    assert mock_client.publish.called
    topic = mock_client.publish.call_args[0][0]
    assert topic == "homing/simulator/devices/living-light/command"

    # Command in real mode
    mock_client.reset_mock()
    hub.command("living-light", "on", timeout=0.01, mode="real")
    assert mock_client.publish.called
    topic = mock_client.publish.call_args[0][0]
    assert topic == "homing/devices/living-light/command"


def test_simulator_topic_message_routes_only_to_simulator(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    import src.services.devices as devices_mod
    from src.models.schemas import Device
    from src.services.devices import DeviceRegistry
    from src.services.mqtt import MqttHub

    sim_reg = DeviceRegistry(tmp_path / "sim_devices.json")
    real_reg = DeviceRegistry(tmp_path / "real_devices.json")

    sim_reg.add(Device(id="living-light", name="Simulator Light", room="Phòng khách", kind="light", online=False, state={"power": False}))
    real_reg.add(Device(id="living-light", name="Real Light", room="Phòng khách", kind="light", online=False, state={"power": False}))

    def mock_get_registry(mode: str = "simulator"):
        if (mode or "").strip().lower() == "simulator":
            return sim_reg
        return real_reg

    monkeypatch.setattr(devices_mod, "get_registry", mock_get_registry)

    hub = MqttHub()
    # Message arrives on simulator topic
    msg = MagicMock()
    msg.topic = "homing/simulator/devices/living-light/state"
    msg.payload = json.dumps({
        "device_id": "living-light",
        "state": {"power": True},
        "online": True,
    }).encode()

    hub._on_message(None, None, msg)

    assert sim_reg.get("living-light").online is True
    assert sim_reg.get("living-light").state["power"] is True
    assert real_reg.get("living-light").online is False
    assert real_reg.get("living-light").state["power"] is False



