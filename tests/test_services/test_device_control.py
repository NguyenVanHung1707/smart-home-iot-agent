from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.models.schemas import DeviceCommand
from src.services.approvals import ApprovalStore
from src.services.device_control import control_device
from src.services.devices import registry


def test_simulated_devices_use_natural_vietnamese_labels():
    devices = {device.id: device for device in registry.list()}

    assert devices["living-light"].name == "Đèn phòng khách"
    assert devices["living-aircon"].name == "Điều hòa phòng khách"
    assert devices["entry-lock"].room == "Lối vào"


def test_control_device_publishes_resulting_state(monkeypatch):
    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type(
            "Hub",
            (),
            {
                "command": lambda *_: (
                    {"id": "living-light", "name": "Den", "room": "Phong", "kind": "light", "state": {"power": True}},
                    None,
                )
            },
        )(),
    )

    device, error = control_device("living-light", "on")

    assert device is not None
    assert device.state["power"] is True
    assert error is None


def test_control_device_keeps_local_state_when_mqtt_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub", lambda: type("Hub", (), {"command": lambda *_: (None, "timeout")})()
    )

    device, error = control_device("living-light", "off")

    assert device is None
    assert error == "timeout"


def test_control_device_blocks_unlock_without_approval(monkeypatch):
    def get_hub():
        raise AssertionError("MQTT must not be called")

    monkeypatch.setattr("src.services.device_control.get_mqtt_hub", get_hub)

    device, error = control_device("entry-lock", "unlock")

    assert device is None
    assert error == "approval_required"


def test_control_device_rejects_out_of_range_value(monkeypatch):
    def get_hub():
        raise AssertionError("MQTT must not be called")

    monkeypatch.setattr("src.services.device_control.get_mqtt_hub", get_hub)

    device, error = control_device("living-light", "set", {"brightness": 101})

    assert device is None
    assert error == "invalid_set_value:brightness"


def test_control_device_allows_unlock_once_with_store_issued_approval(monkeypatch):
    calls = {"publish": 0, "mutation": 0}

    def command(self, *_):
        calls["publish"] += 1
        calls["mutation"] += 1
        return (
            {
                "id": "entry-lock",
                "name": "Khoa cua chinh",
                "room": "Loi vao",
                "kind": "lock",
                "state": {"locked": False},
            },
            None,
        )

    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type("Hub", (), {"command": command})(),
    )
    store = ApprovalStore()
    approval = store.create("entry-lock", DeviceCommand(action="unlock"))
    capability = store.approve(approval.id)

    first = control_device("entry-lock", "unlock", approval=capability, command_id=approval.id)
    replay = control_device("entry-lock", "unlock", approval=capability, command_id=approval.id)

    assert first == replay
    assert first[0] is not None
    assert first[1] is None
    assert calls == {"publish": 1, "mutation": 1}


def test_sensitive_approval_rejects_expired_replayed_or_changed_without_dispatch(monkeypatch):
    calls = {"publish": 0, "mutation": 0}

    def command(self, *_):
        calls["publish"] += 1
        calls["mutation"] += 1
        return None, None

    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type("Hub", (), {"command": command})(),
    )
    store = ApprovalStore()
    approval = store.create("entry-lock", DeviceCommand(action="unlock"))
    expired = store.approve(approval.id, now=datetime.max.replace(tzinfo=UTC))
    assert expired is None

    valid = store.create("entry-lock", DeviceCommand(action="unlock"))
    capability = store.approve(valid.id)
    assert capability is not None
    changed = control_device("entry-lock", "lock", approval=capability, command_id=valid.id)
    replayed_capability = store.approve(valid.id)

    assert changed == (None, "approval_command_mismatch")
    assert replayed_capability is None
    assert calls == {"publish": 0, "mutation": 0}


def test_executor_rejects_capability_expired_after_approval_without_dispatch(monkeypatch):
    calls = {"publish": 0, "mutation": 0}

    def command(self, *_):
        calls["publish"] += 1
        calls["mutation"] += 1
        return None, None

    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type("Hub", (), {"command": command})(),
    )
    store = ApprovalStore()
    approval = store.create("entry-lock", DeviceCommand(action="unlock"))
    capability = store.approve(approval.id)
    assert capability is not None
    expired = replace(capability, expires_at=datetime.now(UTC) - timedelta(seconds=1))

    result = control_device("entry-lock", "unlock", approval=expired, command_id=approval.id)

    assert result == (None, "approval_expired")
    assert calls == {"publish": 0, "mutation": 0}


def test_legacy_duplicate_command_identity_dispatches_once(monkeypatch):
    calls = {"publish": 0}

    def command(self, device_id, action, value=None):
        calls["publish"] += 1
        return {
            "id": device_id,
            "name": "Den",
            "room": "Phong",
            "kind": "light",
            "state": {"power": action == "on"},
        }, None

    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type("Hub", (), {"command": command})(),
    )
    identity = str(uuid4())

    first = control_device("living-light", "on", command_id=identity)
    replay = control_device("living-light", "on", command_id=identity)

    assert replay == first
    assert calls["publish"] == 1


def test_control_device_allows_direct_unlock_with_approved_sensitive(monkeypatch):
    calls = {"publish": 0}

    def command(self, device_id, action, value=None):
        calls["publish"] += 1
        return {
            "id": device_id,
            "name": "Khóa cửa chính",
            "room": "Phòng khách",
            "kind": "lock",
            "state": {"locked": False},
        }, None

    monkeypatch.setattr(
        "src.services.device_control.get_mqtt_hub",
        lambda: type("Hub", (), {"authorized_command": command, "command": command})(),
    )

    device, error = control_device("entry-lock", "unlock", approved_sensitive=True)

    assert error is None
    assert device is not None
    assert device.state["locked"] is False
    assert calls["publish"] == 1


def test_control_device_supports_all_actuator_kinds(monkeypatch):
    test_cases = [
        (
            "living-aircon",
            "set",
            {"target_temperature": 24, "mode": "cool"},
            "aircon",
            {"target_temperature": 24, "mode": "cool"},
        ),
        ("living-blind", "open", None, "blind", {"position": 100, "power": True}),
        ("living-blind", "set", {"position": 50}, "blind", {"position": 50}),
        ("hub-speaker", "play", None, "speaker", {"playing": True, "power": True}),
        ("hub-speaker", "set", {"volume": 70}, "speaker", {"volume": 70}),
        ("entry-lock", "lock", None, "lock", {"locked": True}),
    ]

    for dev_id, action, value, kind, expected_state in test_cases:
        dev_payload = {
            "id": dev_id,
            "name": "Device",
            "room": "Phòng khách",
            "kind": kind,
            "state": expected_state,
        }

        monkeypatch.setattr(
            "src.services.device_control.get_mqtt_hub",
            lambda payload=dev_payload: type("Hub", (), {"command": lambda self, *_: (payload, None)})(),
        )

        device, error = control_device(dev_id, action, value)
        assert error is None, f"Failed for {dev_id} {action}: {error}"
        assert device is not None
        for k, v in expected_state.items():
            assert device.state.get(k) == v


def test_control_device_resolves_real_mode_from_active_data_mode(monkeypatch):
    import src.services.devices as devices_mod

    devices_mod.set_active_data_mode("real")
    try:
        real_reg = devices_mod.get_registry("real")
        real_reg.set_online("living-light", True)

        dispatched = {}

        def mock_command(self, device_id, action, value=None, mode=None):
            dispatched["device_id"] = device_id
            dispatched["action"] = action
            dispatched["mode"] = mode
            return (
                {
                    "id": device_id,
                    "name": "Đèn phòng khách",
                    "room": "Phòng khách",
                    "kind": "light",
                    "state": {"power": True},
                },
                None,
            )

        monkeypatch.setattr(
            "src.services.device_control.get_mqtt_hub",
            lambda: type("Hub", (), {"command": mock_command})(),
        )

        device, error = control_device("living-light", "on")
        assert error is None
        assert device is not None
        assert dispatched.get("mode") == "real"
        assert dispatched.get("device_id") == "living-light"
    finally:
        devices_mod.set_active_data_mode("simulator")

