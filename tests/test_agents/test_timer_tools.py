import json

import pytest

from src.agents.tools import (
    cancel_device_timer,
    list_device_timers,
    set_device_timer,
)
from src.services.timer_service import timer_service


@pytest.fixture(autouse=True)
def clean_timers():
    timer_service.clear()
    yield
    timer_service.clear()


def test_set_device_timer_tool():
    """set_device_timer tool should resolve device and create timer successfully."""
    res = json.loads(
        set_device_timer.invoke(
            {
                "room": "Phòng khách",
                "kind": "light",
                "action": "off",
                "duration_minutes": 30.0,
            }
        )
    )

    assert res["status"] == "success"
    assert "timer_id" in res
    assert res["action"] == "off"
    assert res["duration_minutes"] == 30.0
    assert "Đã hẹn giờ" in res["message"]

    # Verify active timer list
    timers = timer_service.list_timers(active_only=True)
    assert len(timers) == 1
    assert timers[0].device_id == res["device_id"]


def test_list_device_timers_tool():
    """list_device_timers should return active timers."""
    timer_service.create_timer("living-light", "Đèn", "Phòng khách", "off", 300.0)
    timer_service.create_timer("bedroom-fan", "Quạt", "Phòng ngủ", "off", 600.0)

    res = json.loads(list_device_timers.invoke({"active_only": True}))
    assert res["status"] == "success"
    assert res["count"] == 2
    assert len(res["timers"]) == 2


def test_cancel_device_timer_by_id():
    """cancel_device_timer by timer_id should cancel target timer."""
    item = timer_service.create_timer("living-light", "Đèn", "Phòng khách", "off", 300.0)

    res = json.loads(cancel_device_timer.invoke({"timer_id": item.id}))
    assert res["status"] == "success"
    assert "Đã hủy thành công" in res["message"]
    assert len(timer_service.list_timers(active_only=True)) == 0


def test_cancel_device_timer_by_room():
    """cancel_device_timer by room should resolve devices and cancel their timers."""
    timer_service.create_timer("living-light", "Đèn phòng khách", "Phòng khách", "off", 300.0)

    res = json.loads(cancel_device_timer.invoke({"room": "Phòng khách", "kind": "light"}))
    assert res["status"] == "success"
    assert res["cancelled_count"] == 1
    assert len(timer_service.list_timers(active_only=True)) == 0
