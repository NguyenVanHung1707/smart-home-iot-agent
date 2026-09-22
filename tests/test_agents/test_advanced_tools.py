import json

import pytest

from src.agents.tools import (
    activate_scene,
    batch_control_devices,
    get_schedules,
    get_security_report,
    get_sensor_data,
    request_unlock_approval,
)
from src.models.schemas import Device
from src.services.approvals import approvals


@pytest.fixture(autouse=True)
def clean_approvals():
    approvals.clear()
    yield
    approvals.clear()


def test_batch_control_devices_lights(monkeypatch):
    """Batch control should execute command across all matching devices."""
    calls = []
    monkeypatch.setattr(
        "src.agents.tools.base.control_device",
        lambda device_id, action, value: (
            calls.append((device_id, action, value))
            or (Device(id=device_id, name="Test", room="Test", kind="light", state={"power": action == "on"}), None)
        ),
    )

    res = json.loads(batch_control_devices.invoke({"kind": "light", "action": "on"}))
    assert res["status"] == "success"
    assert res["success_count"] > 0
    assert len(calls) == res["success_count"]
    assert all(c[1] == "on" for c in calls)


def test_activate_scene_good_night(monkeypatch):
    """Good night scene should turn off lights, close blinds, and lock doors."""
    executed = []
    monkeypatch.setattr(
        "src.agents.tools.base.control_device",
        lambda device_id, action, value: (
            executed.append((device_id, action, value))
            or (Device(id=device_id, name="Dev", room="Room", kind="any", state={}), None)
        ),
    )

    res = json.loads(activate_scene.invoke({"scene": "good_night"}))
    assert res["status"] == "success"
    assert res["scene"] == "good_night"
    assert res["success_count"] > 0

    actions = [x[1] for x in executed]
    assert "off" in actions
    assert "lock" in actions
    assert "set" in actions


def test_request_unlock_approval():
    """Request unlock approval should create a pending approval in ApprovalStore."""
    res = json.loads(request_unlock_approval.invoke({"reason": "Khách đến chơi nhà", "room": "Lối vào"}))
    assert res["status"] == "success"
    assert "ticket_id" in res
    assert res["device_id"] == "entry-lock"

    # Verify ticket in approval store
    pending_list = approvals.list()
    assert len(pending_list) == 1
    assert pending_list[0].id == res["ticket_id"]
    assert pending_list[0].command.action == "unlock"
    assert pending_list[0].requested_by == "Khách đến chơi nhà"


def test_get_security_report():
    """Security report should inspect all locks and environmental sensors."""
    res = json.loads(get_security_report.invoke({}))
    assert res["status"] == "success"
    assert res["overall_status"] in {"SECURE", "WARNING", "ALERT"}
    assert "locks" in res
    assert "sensors" in res
    assert len(res["locks"]) > 0


def test_get_schedules():
    """Get schedules should list active routines and filter properly."""
    res_all = json.loads(get_schedules.invoke({}))
    assert res_all["status"] == "success"
    assert res_all["total"] > 0
    assert any("Mở rèm" in s["name"] for s in res_all["schedules"])

    res_blind = json.loads(get_schedules.invoke({"kind": "blind"}))
    assert res_blind["status"] == "success"
    assert all(s["kind"] == "blind" for s in res_blind["schedules"])


def test_get_sensor_data_with_assessment():
    """Get sensor data should return sensor health & comfort assessments."""
    res = json.loads(get_sensor_data.invoke({"room": "Phòng khách"}))
    assert res["status"] == "success"
    assert len(res["sensors"]) > 0
    for s in res["sensors"]:
        assert "assessment" in s
        assert isinstance(s["assessment"], dict)
