"""Strict runtime-driven protocol for local smart-home tool calls."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final

from langchain_core.messages import ToolMessage
from pydantic import BaseModel, ConfigDict, ValidationError

from src.agents.tools import ScalarValue, control_smart_device
from src.services.devices import registry

_FENCE: Final = re.compile(r"```homeassistant\n(?P<payload>.*?)\n```", re.DOTALL)
_PROTOCOL_MARKER: Final = "```homeassistant"
LocalAction = str


@dataclass(frozen=True, slots=True)
class _ServiceMapping:
    kind: str
    action: LocalAction
    source_field: str | None = None
    local_field: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    scale: int = 1
    fixed_value: int | None = None


_SERVICE_ACTIONS: Final[dict[str, _ServiceMapping]] = {
    "light.turn_on": _ServiceMapping("light", "on"),
    "light.turn_off": _ServiceMapping("light", "off"),
    "light.toggle": _ServiceMapping("light", "toggle"),
    "climate.turn_on": _ServiceMapping("aircon", "on"),
    "climate.turn_off": _ServiceMapping("aircon", "off"),
    "climate.set_temperature": _ServiceMapping("aircon", "set", "temperature", "target_temperature", 16, 30),
    "cover.open_cover": _ServiceMapping("blind", "set", fixed_value=100),
    "cover.close_cover": _ServiceMapping("blind", "set", fixed_value=0),
    "cover.set_cover_position": _ServiceMapping("blind", "set", "position", "position", 0, 100),
    "media_player.turn_on": _ServiceMapping("speaker", "on"),
    "media_player.turn_off": _ServiceMapping("speaker", "off"),
    "media_player.volume_set": _ServiceMapping("speaker", "set", "volume_level", "volume", 0, 1, 100),
    "lock.lock": _ServiceMapping("lock", "lock"),
}


class _RawCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service: str | None = None
    target_device: str | None = None
    service_data: dict[str, ScalarValue] | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantCall:
    device_id: str
    action: LocalAction
    value: dict[str, ScalarValue] | None


@dataclass(frozen=True, slots=True)
class HomeAssistantProtocolError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


def _validate_runtime_call(
    device_id: str, action: str, value: Any, expected_kind: str | None = None
) -> HomeAssistantCall:
    device = registry.get(device_id)
    if device is None:
        raise HomeAssistantProtocolError(reason="target_device is not an exact registry ID")
    if expected_kind and device.kind != expected_kind:
        raise HomeAssistantProtocolError(reason="target_device is not compatible with the selected tool")
    if value is not None and not isinstance(value, dict):
        raise HomeAssistantProtocolError(reason="tool value must be an object or null")
    _, validation_error = registry.validate_command(device.id, action, value)
    if validation_error:
        raise HomeAssistantProtocolError(reason=f"invalid local command: {validation_error}")
    return HomeAssistantCall(device_id=device.id, action=action, value=value)


def _normalize_service_data(
    mapping: _ServiceMapping, service_data: dict[str, ScalarValue] | None
) -> dict[str, ScalarValue] | None:
    if mapping.fixed_value is not None:
        if service_data is not None:
            raise HomeAssistantProtocolError(reason="fixed service does not accept service_data")
        return {"position": mapping.fixed_value}
    if mapping.source_field is None:
        if service_data is not None:
            raise HomeAssistantProtocolError(reason="service does not accept service_data")
        return None
    if service_data is None or set(service_data) != {mapping.source_field}:
        raise HomeAssistantProtocolError(reason="service_data has wrong fields")
    source_value = service_data[mapping.source_field]
    if isinstance(source_value, bool) or not isinstance(source_value, (int, float)):
        raise HomeAssistantProtocolError(reason="service_data value has wrong type")
    if mapping.minimum is None or mapping.maximum is None or not mapping.minimum <= source_value <= mapping.maximum:
        raise HomeAssistantProtocolError(reason="service_data value is outside range")
    if mapping.local_field is None:
        raise HomeAssistantProtocolError(reason="service mapping has no local field")
    return {mapping.local_field: round(source_value * mapping.scale)}


def parse_homeassistant_call(content: str) -> HomeAssistantCall | None:
    """Parse one complete fenced call and validate it against runtime registry."""
    trimmed = content.strip()
    match = _FENCE.fullmatch(trimmed)
    if match is None:
        if _PROTOCOL_MARKER in trimmed:
            raise HomeAssistantProtocolError(reason="protocol block must be entire output")
        return None
    try:
        raw = _RawCall.model_validate_json(match.group("payload"))
    except ValidationError as error:
        raise HomeAssistantProtocolError(reason="malformed protocol payload") from error

    if raw.tool is not None:
        if raw.tool not in {"control_device", "control_smart_device"} and not raw.tool.startswith("control_"):
            raise HomeAssistantProtocolError(reason="unknown tool")
        arguments = raw.arguments or {}
        device_id = arguments.get("device_id")
        action = arguments.get("action")
        if not isinstance(device_id, str) or not isinstance(action, str):
            raise HomeAssistantProtocolError(reason="tool arguments require device_id and action")
        expected_kind = (
            raw.tool.removeprefix("control_") if raw.tool not in {"control_device", "control_smart_device"} else None
        )
        return _validate_runtime_call(device_id, action, arguments.get("value"), expected_kind)

    if raw.service is None or raw.target_device is None:
        raise HomeAssistantProtocolError(reason="protocol requires tool or service and target_device")
    mapping = _SERVICE_ACTIONS.get(raw.service)
    if mapping is None:
        raise HomeAssistantProtocolError(reason="unknown or forbidden service")
    value = _normalize_service_data(mapping, raw.service_data)
    return _validate_runtime_call(raw.target_device, mapping.action, value, mapping.kind)


def execute_homeassistant_call(call: HomeAssistantCall) -> ToolMessage:
    """Execute through the existing safety authority and retain its result."""
    content = control_smart_device.invoke({"device_id": call.device_id, "action": call.action, "value": call.value})
    return ToolMessage(name="control_smart_device", tool_call_id="homeassistant-local-call", content=str(content))


def protocol_example() -> str:
    """Render one valid example from the current registry, never a fixed device ID."""
    device = next((item for item in registry.list() if registry.capabilities(item).get("actions")), None)
    if device is None:
        payload = {"service": "device.control", "target_device": "<runtime-device-id>"}
    else:
        action = registry.capabilities(device)["actions"][0]
        service_by_kind = {
            "light": {"on": "light.turn_on", "off": "light.turn_off", "toggle": "light.toggle"},
            "aircon": {"on": "climate.turn_on", "off": "climate.turn_off", "toggle": "climate.toggle"},
            "blind": {"set": "cover.set_cover_position"},
            "speaker": {"on": "media_player.turn_on", "off": "media_player.turn_off", "toggle": "media_player.toggle"},
            "lock": {"lock": "lock.lock"},
        }
        payload = {
            "service": service_by_kind.get(device.kind, {}).get(action, "device.control"),
            "target_device": device.id,
        }
    return f"```homeassistant\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n```"
