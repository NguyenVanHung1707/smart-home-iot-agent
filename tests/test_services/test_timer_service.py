import time

import pytest

from src.models.schemas import Device
from src.services.timer_service import timer_service


@pytest.fixture(autouse=True)
def clean_timers():
    timer_service.clear()
    yield
    timer_service.clear()


def test_create_and_execute_timer(monkeypatch):
    """Timer should countdown and trigger control_device upon completion."""
    called = []
    dummy = Device(id="living-light", name="Đèn", room="Phòng khách", kind="light", state={"power": False})
    monkeypatch.setattr(
        "src.services.timer_service.control_device",
        lambda device_id, action, value: called.append((device_id, action)) or (dummy, None),
    )

    # 0.1s timer
    item = timer_service.create_timer(
        device_id="living-light",
        device_name="Đèn phòng khách",
        room="Phòng khách",
        action="off",
        duration_seconds=0.1,
    )

    assert item.status == "pending"
    assert len(timer_service.list_timers(active_only=True)) == 1

    time.sleep(0.25)

    assert len(called) == 1
    assert called[0] == ("living-light", "off")
    assert item.status == "completed"
    assert len(timer_service.list_timers(active_only=True)) == 0


def test_cancel_timer():
    """Cancel timer should stop execution thread and set status to cancelled."""
    item = timer_service.create_timer(
        device_id="living-fan",
        device_name="Quạt phòng khách",
        room="Phòng khách",
        action="off",
        duration_seconds=10.0,
    )

    assert item.status == "pending"
    assert timer_service.cancel_timer(item.id) is True
    assert item.status == "cancelled"
    assert len(timer_service.list_timers(active_only=True)) == 0


def test_cancel_by_device():
    """Cancel by device should cancel all pending timers for that device."""
    timer_service.create_timer("dev-1", "Dev 1", "Room 1", "on", 10.0)
    timer_service.create_timer("dev-1", "Dev 1", "Room 1", "off", 15.0)
    timer_service.create_timer("dev-2", "Dev 2", "Room 2", "on", 20.0)

    cancelled = timer_service.cancel_by_device("dev-1")
    assert cancelled == 2
    active = timer_service.list_timers(active_only=True)
    assert len(active) == 1
    assert active[0].device_id == "dev-2"
