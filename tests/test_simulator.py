"""Tests for MQTT Device Simulator and Simulator Storage."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["APP_ENV"] = "test"

import pytest
from fastapi import HTTPException

from src.simulator import (
    add_device,
    delete_device,
    get_simulator_ui,
    get_state,
    health,
    on_message,
    perform_action,
    reset_simulator_state,
    save_walls,
    set_device_fault,
    trigger_scan,
    update_device,
)
from src.simulator_storage import SimulatorStorage, storage


@pytest.fixture
def temp_storage(tmp_path: Path):
    storage_file = tmp_path / "test_simulator_state.json"
    sim_storage = SimulatorStorage(storage_path=storage_file)
    return sim_storage


def test_default_initialization(temp_storage: SimulatorStorage):
    state = temp_storage.get_state()
    assert "walls" in state
    assert "devices" in state
    assert "faults" in state
    assert len(state["walls"]) > 0
    assert len(state["devices"]) > 0


def test_save_and_get_walls(temp_storage: SimulatorStorage):
    custom_walls = [{"x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 200.0}]
    saved = temp_storage.save_walls(custom_walls)
    assert len(saved) == 1
    assert saved[0]["x1"] == 10.0
    assert temp_storage.get_walls() == saved


def test_device_crud(temp_storage: SimulatorStorage):
    new_dev = {
        "id": "test-lamp",
        "name": "Test Lamp",
        "kind": "light",
        "room": "Phòng khách",
        "x": 120.0,
        "y": 140.0,
        "state": {"power": False, "brightness": 60},
        "auto_simulate": False,
    }
    added = temp_storage.add_device(new_dev)
    assert added["id"] == "test-lamp"
    assert added["name"] == "Test Lamp"

    # Duplicate ID should raise ValueError
    with pytest.raises(ValueError, match="device_id_exists"):
        temp_storage.add_device(new_dev)

    # Get device
    fetched = temp_storage.get_device("test-lamp")
    assert fetched is not None
    assert fetched["id"] == "test-lamp"

    # Update device
    updated = temp_storage.update_device(
        "test-lamp",
        {"name": "Updated Lamp", "x": 150.0, "state": {"brightness": 90}},
    )
    assert updated is not None
    assert updated["name"] == "Updated Lamp"
    assert updated["x"] == 150.0
    assert updated["state"]["brightness"] == 90

    # Delete device
    assert temp_storage.delete_device("test-lamp") is True
    assert temp_storage.get_device("test-lamp") is None
    assert temp_storage.delete_device("non-existent") is False


def test_fault_management(temp_storage: SimulatorStorage):
    temp_storage.add_device({"id": "fault-device", "name": "Fault Test"})
    assert temp_storage.get_fault("fault-device") == "none"

    temp_storage.set_fault("fault-device", "offline")
    assert temp_storage.get_fault("fault-device") == "offline"

    temp_storage.set_fault("fault-device", "timeout")
    assert temp_storage.get_fault("fault-device") == "timeout"

    temp_storage.set_fault("fault-device", "error")
    assert temp_storage.get_fault("fault-device") == "error"

    with pytest.raises(ValueError, match="invalid_fault_mode"):
        temp_storage.set_fault("fault-device", "invalid_mode")


def test_apply_action(temp_storage: SimulatorStorage):
    temp_storage.add_device({"id": "action-dev", "name": "Action Device", "state": {"power": False, "locked": True}})

    # Toggle
    res = temp_storage.apply_action("action-dev", "toggle")
    assert res["state"]["power"] is True

    # On / Off
    res = temp_storage.apply_action("action-dev", "off")
    assert res["state"]["power"] is False
    res = temp_storage.apply_action("action-dev", "on")
    assert res["state"]["power"] is True

    # Unlock / Lock
    res = temp_storage.apply_action("action-dev", "unlock")
    assert res["state"]["locked"] is False
    res = temp_storage.apply_action("action-dev", "lock")
    assert res["state"]["locked"] is True

    # Set
    res = temp_storage.apply_action("action-dev", "set", {"brightness": 75})
    assert res["state"]["brightness"] == 75

    # Unsupported
    with pytest.raises(ValueError):
        temp_storage.apply_action("action-dev", "invalid_action")

    # Blind toggle: when position > 0, set position=0 and power=False
    temp_storage.add_device({"id": "blind-dev", "name": "Blind Dev", "kind": "blind", "state": {"position": 50, "power": True}})
    res = temp_storage.apply_action("blind-dev", "toggle")
    assert res["state"]["position"] == 0
    assert res["state"]["power"] is False
    # When position == 0, set position=100 and power=True
    res = temp_storage.apply_action("blind-dev", "toggle")
    assert res["state"]["position"] == 100
    assert res["state"]["power"] is True


@pytest.mark.asyncio
async def test_health_check_api():
    res = await health()
    assert res["status"] == "ok"
    assert "broker" in res
    assert "topic_prefix" in res


@pytest.mark.asyncio
async def test_state_and_walls_api():
    storage.reset()
    state = await get_state()
    assert "walls" in state
    assert "devices" in state

    # Save walls
    wall_payload = [{"x1": 0.0, "y1": 0.0, "x2": 500.0, "y2": 500.0}]
    saved = await save_walls(wall_payload)
    assert len(saved) == 1
    assert saved[0]["x2"] == 500.0


@pytest.mark.asyncio
async def test_device_lifecycle_api():
    storage.reset()
    new_dev = {
        "id": "api-lamp-1",
        "name": "API Lamp",
        "kind": "light",
        "room": "Phòng khách",
        "x": 200.0,
        "y": 200.0,
        "state": {"power": False, "brightness": 50},
        "auto_simulate": False,
    }
    # Create
    dev = await add_device(new_dev)
    assert dev["id"] == "api-lamp-1"

    # Duplicate create error
    with pytest.raises(HTTPException) as exc:
        await add_device(new_dev)
    assert exc.value.status_code == 400

    # Update
    updated = await update_device("api-lamp-1", {"name": "New Lamp Name", "x": 220.0})
    assert updated["name"] == "New Lamp Name"
    assert updated["x"] == 220.0

    # Update not found
    with pytest.raises(HTTPException) as exc:
        await update_device("non-existent-device", {"name": "Test"})
    assert exc.value.status_code == 404

    # Action: toggle
    action_res = await perform_action("api-lamp-1", {"action": "toggle"})
    assert action_res["state"]["power"] is True

    # Action: set
    action_res = await perform_action("api-lamp-1", {"action": "set", "value": {"brightness": 95}})
    assert action_res["state"]["brightness"] == 95

    # Action missing action field
    with pytest.raises(HTTPException) as exc:
        await perform_action("api-lamp-1", {})
    assert exc.value.status_code == 400

    # Fault
    fault_res = await set_device_fault("api-lamp-1", {"mode": "offline"})
    assert fault_res["fault"] == "offline"

    # Delete
    del_res = await delete_device("api-lamp-1")
    assert del_res["success"] is True

    # Delete non-existent
    with pytest.raises(HTTPException) as exc:
        await delete_device("api-lamp-1")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_discovery_scan_and_reset_api():
    storage.reset()
    scan_res = await trigger_scan()
    assert scan_res["status"] == "scan_broadcasted"
    assert scan_res["device_count"] > 0

    reset_res = await reset_simulator_state()
    assert "devices" in reset_res
    assert len(reset_res["devices"]) > 0


@pytest.mark.asyncio
async def test_simulator_ui_page_api():
    html_resp = await get_simulator_ui()
    assert html_resp.status_code == 200
    body = html_resp.body.decode("utf-8")
    assert "Terra Simulator" in body or "root" in body


def test_mqtt_scan_message():
    storage.reset()
    mock_client = MagicMock()

    # Real device scan topic should NOT trigger simulator devices publish
    msg_real = MagicMock()
    msg_real.topic = "homing/broadcast/scan"
    msg_real.payload = json.dumps({"action": "scan"}).encode("utf-8")
    with patch("src.simulator.mqtt_client", mock_client):
        on_message(mock_client, None, msg_real)
        assert not mock_client.publish.called

    # Simulator scan topic should trigger publish
    msg_sim = MagicMock()
    msg_sim.topic = "homing/simulator/broadcast/scan"
    msg_sim.payload = json.dumps({"action": "scan"}).encode("utf-8")
    with patch("src.simulator.mqtt_client", mock_client):
        on_message(mock_client, None, msg_sim)
        assert mock_client.publish.called


def test_mqtt_command_message():
    storage.reset()
    mock_client = MagicMock()
    msg = MagicMock()
    msg.topic = "homing/devices/living-light/command"
    msg.payload = json.dumps(
        {
            "command_id": "cmd-123",
            "device_id": "living-light",
            "action": "on",
        }
    ).encode("utf-8")

    with patch("src.simulator.mqtt_client", mock_client):
        on_message(mock_client, None, msg)
        assert mock_client.publish.called
        # Verify device state changed
        dev = storage.get_device("living-light")
        assert dev["state"]["power"] is True


def test_mqtt_fault_handling():
    storage.reset()
    mock_client = MagicMock()

    # Inject timeout fault
    fault_msg = MagicMock()
    fault_msg.topic = "homing/simulator/living-light/fault"
    fault_msg.payload = json.dumps({"mode": "timeout"}).encode("utf-8")
    on_message(mock_client, None, fault_msg)
    assert storage.get_fault("living-light") == "timeout"

    # Now send command - should be ignored (no ACK)
    mock_client.reset_mock()
    cmd_msg = MagicMock()
    cmd_msg.topic = "homing/devices/living-light/command"
    cmd_msg.payload = json.dumps(
        {
            "command_id": "cmd-456",
            "device_id": "living-light",
            "action": "off",
        }
    ).encode("utf-8")
    on_message(mock_client, None, cmd_msg)
    assert not mock_client.publish.called


def test_security_device_id_validation(temp_storage: SimulatorStorage):
    # Forbidden characters: /, +, #, .., spaces
    invalid_ids = [
        "test/+/sub",
        "test/#/wildcard",
        "../../etc/passwd",
        "device name with spaces",
        "device;drop table",
        "<script>alert(1)</script>",
        "",
    ]
    for bad_id in invalid_ids:
        with pytest.raises(ValueError):
            temp_storage.add_device({"id": bad_id, "name": "Bad ID Device"})


def test_security_coordinate_bounds_and_nan(temp_storage: SimulatorStorage):
    # Negative coords, NaN, Inf, out-of-bounds (> 5000)
    with pytest.raises(ValueError):
        temp_storage.add_device({"id": "neg-coord", "x": -50.0, "y": 100.0})

    with pytest.raises(ValueError):
        temp_storage.add_device({"id": "huge-coord", "x": 6000.0, "y": 100.0})

    with pytest.raises(ValueError):
        temp_storage.add_device({"id": "nan-coord", "x": float("nan"), "y": 100.0})

    with pytest.raises(ValueError):
        temp_storage.add_device({"id": "inf-coord", "x": float("inf"), "y": 100.0})

    # Walls validation
    with pytest.raises(ValueError):
        temp_storage.save_walls([{"x1": -10.0, "y1": 0.0, "x2": 100.0, "y2": 100.0}])

    with pytest.raises(ValueError):
        temp_storage.save_walls([{"x1": float("nan"), "y1": 0.0, "x2": 100.0, "y2": 100.0}])


def test_security_xss_sanitization(temp_storage: SimulatorStorage):
    dev = temp_storage.add_device(
        {
            "id": "xss-lamp",
            "name": "<script>alert('xss')</script>Đèn Test",
            "room": "<img src=x onerror=alert(1)>Phòng Khách",
        }
    )
    assert "<script>" not in dev["name"]
    assert "&lt;script&gt;" in dev["name"]
    assert "<img" not in dev["room"]
    assert "&lt;img" in dev["room"]


@pytest.mark.asyncio
async def test_security_api_rejections():
    storage.reset()
    # Topic injection in API add device
    with pytest.raises(HTTPException) as exc:
        await add_device({"id": "injected/+/topic", "name": "Hack"})
    assert exc.value.status_code == 400

    # Invalid fault mode in API
    with pytest.raises(HTTPException) as exc:
        await set_device_fault("living-light", {"mode": "malicious_mode"})
    assert exc.value.status_code == 400


def test_auto_simulate_heartbeat_keepalive():
    from src.simulator import _auto_simulate_loop, _stop_simulation

    storage.reset()
    storage.set_fault("living-light", "offline")

    calls = []
    iteration_count = 0

    def mock_publish_state(device_id):
        calls.append(device_id)

    def mock_wait(timeout):
        nonlocal iteration_count
        iteration_count += 1
        if iteration_count >= 5:
            _stop_simulation.set()

    _stop_simulation.clear()
    with (
        patch("src.simulator.publish_state", side_effect=mock_publish_state),
        patch.object(_stop_simulation, "wait", side_effect=mock_wait),
    ):
        _auto_simulate_loop()

    # Reset _stop_simulation flag
    _stop_simulation.clear()

    # living-light is offline, so it shouldn't be published during heartbeat
    assert "living-light" not in calls
    # non-offline devices should be published
    assert "living-aircon" in calls
    assert "entry-lock" in calls


def test_stamp_and_publish_discovery_have_simulator_source():
    from src.simulator import publish_discovery, stamp

    stamped = json.loads(stamp("test.event", "test-dev"))
    assert stamped["source"] == "simulator"

    mock_client = MagicMock()
    with patch("src.simulator.mqtt_client", mock_client):
        publish_discovery({"id": "d1", "name": "D1", "kind": "light", "room": "R1"})
        assert mock_client.publish.called
        call_args = mock_client.publish.call_args[0]
        payload = json.loads(call_args[1])
        assert payload["source"] == "simulator"


def test_publish_state_offline_and_timeout_sets_online_false():
    from src.simulator import publish_state

    storage.reset()
    mock_client = MagicMock()

    with patch("src.simulator.mqtt_client", mock_client):
        # Normal
        storage.set_fault("living-light", "none")
        publish_state("living-light")
        payload = json.loads(mock_client.publish.call_args[0][1])
        retain = mock_client.publish.call_args[1].get("retain")
        assert payload["online"] is True
        assert payload["source"] == "simulator"
        assert retain is True

        # Offline fault (not retained)
        storage.set_fault("living-light", "offline")
        publish_state("living-light")
        payload = json.loads(mock_client.publish.call_args[0][1])
        retain = mock_client.publish.call_args[1].get("retain")
        assert payload["online"] is False
        assert retain is False

        # Timeout fault (online remains True so Hub can send commands, retained)
        storage.set_fault("living-light", "timeout")
        publish_state("living-light", command_id="cmd-123")
        payload = json.loads(mock_client.publish.call_args[0][1])
        retain = mock_client.publish.call_args[1].get("retain")
        assert payload["online"] is True
        assert payload["command_id"] == "cmd-123"
        assert retain is True


@pytest.mark.asyncio
async def test_perform_action_rejects_offline_and_timeout_devices():
    storage.reset()

    storage.set_fault("living-light", "offline")
    with pytest.raises(HTTPException) as exc:
        await perform_action("living-light", {"action": "on"})
    assert exc.value.status_code == 400
    assert exc.value.detail == "device_offline"

    storage.set_fault("living-light", "timeout")
    with pytest.raises(HTTPException) as exc:
        await perform_action("living-light", {"action": "on"})
    assert exc.value.status_code == 400
    assert exc.value.detail == "device_timeout"


def test_auto_simulate_skips_timeout_devices():
    from src.simulator import _auto_simulate_loop, _stop_simulation

    storage.reset()
    storage.set_fault("living-light", "timeout")

    calls = []
    iteration_count = 0

    def mock_publish_state(device_id):
        calls.append(device_id)

    def mock_wait(timeout):
        nonlocal iteration_count
        iteration_count += 1
        if iteration_count >= 5:
            _stop_simulation.set()

    _stop_simulation.clear()
    with (
        patch("src.simulator.publish_state", side_effect=mock_publish_state),
        patch.object(_stop_simulation, "wait", side_effect=mock_wait),
    ):
        _auto_simulate_loop()

    _stop_simulation.clear()
    assert "living-light" not in calls


def test_simulator_fault_schema_supports_error():
    from src.models.schemas import SimulatorFault

    fault = SimulatorFault(mode="error")
    assert fault.mode == "error"


def test_seed_sync_from_devices_json(tmp_path: Path):
    storage_file = tmp_path / "seed_test.json"
    sim_storage = SimulatorStorage(storage_path=storage_file)
    dev = sim_storage.get_device("entry-lock")
    assert dev is not None
    # Synced from data/devices.json which has "Lối vào"
    assert dev["room"] == "Lối vào"


def test_mqtt_command_echoes_command_id():
    from src.simulator import on_message

    storage.reset()
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "homing/devices/living-light/command"
    mock_msg.payload = json.dumps({"command_id": "test-cmd-456", "action": "on"}).encode("utf-8")

    with patch("src.simulator.publish_state") as mock_publish_state:
        on_message(mock_client, None, mock_msg)
        mock_publish_state.assert_called_with("living-light", command_id="test-cmd-456")


