"""Runtime tool aggregation and dynamic kind-based tool generation."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from src.agents.tools.aircon import control_aircon
from src.agents.tools.base import (
    ScalarValue,
    _get_registry,
    _tool_result,
)
from src.agents.tools.batch_control import batch_control_devices
from src.agents.tools.blind import control_blind
from src.agents.tools.display import control_display
from src.agents.tools.home_guides import search_home_guides
from src.agents.tools.internet_search import search_internet
from src.agents.tools.light import control_light
from src.agents.tools.lock import control_lock
from src.agents.tools.media_player import play_youtube_music
from src.agents.tools.air_quality_advisor import evaluate_air_quality
from src.agents.tools.energy_analytics import get_energy_analytics
from src.agents.tools.home_notes import add_family_note, delete_family_note, get_family_notes
from src.agents.tools.home_safety_audit import audit_home_safety
from src.agents.tools.preferences import get_user_preferences, save_user_preference
from src.agents.tools.room_devices import get_room_devices
from src.agents.tools.scene import activate_scene
from src.agents.tools.schedules import get_schedules
from src.agents.tools.security import get_security_report
from src.agents.tools.sensor_data import get_sensor_data
from src.agents.tools.shopping_list import manage_shopping_list
from src.agents.tools.sleep_optimizer import optimize_sleep_environment
from src.agents.tools.smart_calc_converter import smart_unit_and_cost_calculator
from src.agents.tools.smart_device import ControlSmartDeviceInput, control_smart_device
from src.agents.tools.speaker import control_speaker
from src.agents.tools.timer import cancel_device_timer, list_device_timers, set_device_timer
from src.agents.tools.unlock_approval import request_unlock_approval
from src.agents.tools.social_search import search_social_media
from src.agents.tools.weather_forecast import get_weather_forecast

CONTROL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "control_light",
        "control_aircon",
        "control_blind",
        "control_speaker",
        "control_display",
        "control_lock",
        "play_youtube_music",
        "batch_control_devices",
        "activate_scene",
        "optimize_sleep_environment",
        "request_unlock_approval",
        "set_device_timer",
        "cancel_device_timer",
    }
)

TOOLS = [
    control_light,
    control_aircon,
    control_blind,
    control_speaker,
    control_display,
    control_lock,
    play_youtube_music,
    batch_control_devices,
    activate_scene,
    optimize_sleep_environment,
    audit_home_safety,
    manage_shopping_list,
    smart_unit_and_cost_calculator,
    request_unlock_approval,
    set_device_timer,
    list_device_timers,
    cancel_device_timer,
    get_room_devices,
    get_sensor_data,
    get_security_report,
    get_schedules,
    search_home_guides,
    search_internet,
    search_social_media,
    get_weather_forecast,
    get_energy_analytics,
    evaluate_air_quality,
    add_family_note,
    get_family_notes,
    delete_family_note,
    save_user_preference,
    get_user_preferences,
]


def _control_for_kind(
    kind: str,
    device_id: str,
    action: str,
    value: dict[str, ScalarValue] | None = None,
) -> str:
    active_registry = _get_registry()
    device = active_registry.get(device_id)
    if device is None:
        return _tool_result("not_found", device_id=device_id, message="Không tìm thấy thiết bị.")
    if device.kind != kind:
        return _tool_result("invalid_request", device_id=device_id, message="Thiết bị không thuộc loại tool này.")
    return control_smart_device.invoke({"device_id": device_id, "action": action, "value": value})


def get_runtime_tools() -> list[StructuredTool | Any]:
    """Add a generic exact-ID controller for device kinds not covered by static tools."""
    active_registry = _get_registry()
    tools = list(TOOLS)
    names = {tool.name for tool in tools}
    for kind in sorted({device.kind for device in active_registry.list()}):
        name = f"control_{kind}"
        if name in names:
            continue
        tools.append(
            StructuredTool.from_function(
                func=lambda device_id, action, value=None, expected_kind=kind: _control_for_kind(
                    expected_kind, device_id, action, value
                ),
                name=name,
                description=f"Điều khiển thiết bị kind={kind} bằng device_id chính xác.",
                args_schema=ControlSmartDeviceInput,
            )
        )
    return tools
