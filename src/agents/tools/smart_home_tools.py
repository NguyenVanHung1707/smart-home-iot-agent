"""LangChain tool definitions for Homing Hub smart home control.

Device-type specific tools with dynamic room and topology resolution.
(Re-export facade for backwards compatibility with modular tool files).
"""

from __future__ import annotations

from src.agents.tools.aircon import ControlAirconInput, control_aircon
from src.agents.tools.base import (
    ControlAction,
    ScalarValue,
    _execute_device_control,
    _normalize_text,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)
from src.agents.tools.batch_control import BatchControlDevicesInput, batch_control_devices
from src.agents.tools.blind import ControlBlindInput, control_blind
from src.agents.tools.display import ControlDisplayInput, control_display
from src.agents.tools.home_guides import SearchHomeGuidesInput, search_home_guides
from src.agents.tools.light import ControlLightInput, control_light
from src.agents.tools.lock import ControlLockInput, control_lock
from src.agents.tools.room_devices import GetRoomDevicesInput, get_room_devices
from src.agents.tools.runtime import (
    CONTROL_TOOL_NAMES,
    TOOLS,
    _control_for_kind,
    get_runtime_tools,
)
from src.agents.tools.scene import ActivateSceneInput, activate_scene
from src.agents.tools.schedules import GetSchedulesInput, get_schedules
from src.agents.tools.security import GetSecurityReportInput, get_security_report
from src.agents.tools.sensor_data import GetSensorDataInput, get_sensor_data
from src.agents.tools.smart_device import ControlSmartDeviceInput, control_smart_device
from src.agents.tools.speaker import ControlSpeakerInput, control_speaker
from src.agents.tools.timer import (
    CancelDeviceTimerInput,
    ListDeviceTimersInput,
    SetDeviceTimerInput,
    cancel_device_timer,
    list_device_timers,
    set_device_timer,
)
from src.agents.tools.unlock_approval import RequestUnlockApprovalInput, request_unlock_approval
from src.services.device_control import control_device
from src.services.devices import registry

__all__ = [
    "ActivateSceneInput",
    "BatchControlDevicesInput",
    "CONTROL_TOOL_NAMES",
    "CancelDeviceTimerInput",
    "ControlAction",
    "ControlAirconInput",
    "ControlBlindInput",
    "ControlDisplayInput",
    "ControlLightInput",
    "ControlLockInput",
    "ControlSmartDeviceInput",
    "ControlSpeakerInput",
    "GetRoomDevicesInput",
    "GetSchedulesInput",
    "GetSecurityReportInput",
    "GetSensorDataInput",
    "ListDeviceTimersInput",
    "RequestUnlockApprovalInput",
    "ScalarValue",
    "SearchHomeGuidesInput",
    "SetDeviceTimerInput",
    "TOOLS",
    "_StrictToolInput",
    "_control_for_kind",
    "_execute_device_control",
    "_normalize_text",
    "_resolve_device",
    "_tool_result",
    "activate_scene",
    "batch_control_devices",
    "cancel_device_timer",
    "control_aircon",
    "control_blind",
    "control_device",
    "control_display",
    "control_light",
    "control_lock",
    "control_smart_device",
    "control_speaker",
    "get_room_devices",
    "get_runtime_tools",
    "get_schedules",
    "get_security_report",
    "get_sensor_data",
    "list_device_timers",
    "registry",
    "request_unlock_approval",
    "search_home_guides",
    "set_device_timer",
]
