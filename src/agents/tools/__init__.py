"""LangChain smart home tools package."""

from __future__ import annotations

from src.agents.tools.air_quality_advisor import EvaluateAirQualityInput, evaluate_air_quality
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
from src.agents.tools.energy_analytics import GetEnergyAnalyticsInput, get_energy_analytics
from src.agents.tools.home_guides import SearchHomeGuidesInput, search_home_guides
from src.agents.tools.home_notes import (
    AddFamilyNoteInput,
    DeleteFamilyNoteInput,
    GetFamilyNotesInput,
    add_family_note,
    delete_family_note,
    get_family_notes,
)
from src.agents.tools.home_safety_audit import AuditHomeSafetyInput, audit_home_safety
from src.agents.tools.internet_search import SearchInternetInput, search_internet
from src.agents.tools.light import ControlLightInput, control_light
from src.agents.tools.lock import ControlLockInput, control_lock
from src.agents.tools.media_player import PlayYoutubeMusicInput, parse_music_intent, play_youtube_music
from src.agents.tools.preferences import (
    GetUserPreferencesInput,
    SaveUserPreferenceInput,
    get_user_preferences,
    save_user_preference,
)
from src.agents.tools.room_devices import GetRoomDevicesInput, get_room_devices
from src.agents.tools.runtime import CONTROL_TOOL_NAMES, TOOLS, _control_for_kind, get_runtime_tools
from src.agents.tools.scene import ActivateSceneInput, activate_scene
from src.agents.tools.schedules import GetSchedulesInput, get_schedules
from src.agents.tools.security import GetSecurityReportInput, get_security_report
from src.agents.tools.sensor_data import GetSensorDataInput, get_sensor_data
from src.agents.tools.shopping_list import ManageShoppingListInput, manage_shopping_list
from src.agents.tools.sleep_optimizer import OptimizeSleepEnvironmentInput, optimize_sleep_environment
from src.agents.tools.smart_calc_converter import SmartCalculatorInput, smart_unit_and_cost_calculator
from src.agents.tools.smart_device import ControlSmartDeviceInput, control_smart_device
from src.agents.tools.social_search import SearchSocialMediaInput, search_social_media
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
from src.agents.tools.weather_forecast import GetWeatherForecastInput, get_weather_forecast

__all__ = [
    "ActivateSceneInput",
    "BatchControlDevicesInput",
    "AddFamilyNoteInput",
    "SearchSocialMediaInput",
    "search_social_media",
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
    "DeleteFamilyNoteInput",
    "EvaluateAirQualityInput",
    "GetEnergyAnalyticsInput",
    "GetFamilyNotesInput",
    "GetRoomDevicesInput",
    "GetSchedulesInput",
    "GetSecurityReportInput",
    "GetSensorDataInput",
    "GetUserPreferencesInput",
    "GetWeatherForecastInput",
    "ListDeviceTimersInput",
    "PlayYoutubeMusicInput",
    "RequestUnlockApprovalInput",
    "SaveUserPreferenceInput",
    "ScalarValue",
    "SearchHomeGuidesInput",
    "SearchInternetInput",
    "SetDeviceTimerInput",
    "TOOLS",
    "_StrictToolInput",
    "_control_for_kind",
    "_execute_device_control",
    "_normalize_text",
    "_resolve_device",
    "_tool_result",
    "activate_scene",
    "add_family_note",
    "batch_control_devices",
    "cancel_device_timer",
    "control_aircon",
    "control_blind",
    "control_display",
    "control_light",
    "control_lock",
    "control_smart_device",
    "control_speaker",
    "delete_family_note",
    "evaluate_air_quality",
    "get_energy_analytics",
    "get_family_notes",
    "get_room_devices",
    "get_runtime_tools",
    "get_schedules",
    "get_security_report",
    "get_sensor_data",
    "get_weather_forecast",
    "list_device_timers",
    "play_youtube_music",
    "parse_music_intent",
    "request_unlock_approval",
    "AuditHomeSafetyInput",
    "ManageShoppingListInput",
    "OptimizeSleepEnvironmentInput",
    "SmartCalculatorInput",
    "audit_home_safety",
    "manage_shopping_list",
    "optimize_sleep_environment",
    "smart_unit_and_cost_calculator",
    "search_home_guides",
    "search_internet",
    "set_device_timer",
]
