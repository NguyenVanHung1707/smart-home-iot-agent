"""Shared utilities, schemas, and helper functions for smart home tools."""

from __future__ import annotations

import json
import sys
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

import src.services.device_control as _dc
import src.services.devices as _sd
from src.models.schemas import Device
from src.services.device_control import control_device
from src.services.devices import registry

ControlAction = Literal["on", "off", "toggle", "set", "lock", "open", "close", "play", "pause", "stop"]
ScalarValue = bool | int | float | str


class _StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _get_registry():
    """Support monkeypatching in base or smart_home_tools module for backward compatibility."""
    if registry is not _sd.registry:
        return registry
    sht = sys.modules.get("src.agents.tools.smart_home_tools")
    if sht is not None and hasattr(sht, "registry"):
        if sht.registry is not _sd.registry:
            return sht.registry
    return _sd.get_registry(_sd.get_active_data_mode())


def _get_control_device():
    """Support monkeypatching in base or smart_home_tools module for backward compatibility."""
    if control_device is not _dc.control_device:
        return control_device
    sht = sys.modules.get("src.agents.tools.smart_home_tools")
    if sht is not None and hasattr(sht, "control_device"):
        if sht.control_device is not _dc.control_device:
            return sht.control_device
    return control_device


def _normalize_text(text: str) -> str:
    """Normalize text for accent-insensitive and case-insensitive comparison."""
    lowered = unicodedata.normalize("NFC", text.lower().strip())
    decomposed = unicodedata.normalize("NFD", lowered).replace("đ", "d")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").strip()


def _resolve_device_in_reg(
    reg: Any,
    room: str | None = None,
    kind: str | None = None,
    device_id: str | None = None,
    name: str | None = None,
) -> tuple[Device | None, str | None]:
    """Resolve a device within a specific registry."""
    devices = reg.list()
    if not devices:
        return None, "Hiện chưa có thiết bị nào được cấu hình trong hệ thống."

    # Direct lookup by ID if provided
    if device_id:
        dev = reg.get(device_id)
        if not dev:
            return None, f"Không tìm thấy thiết bị với ID '{device_id}'."
        return dev, None

    # Filter by room
    matched = devices
    if room:
        norm_room = _normalize_text(room)
        matched = [d for d in matched if _normalize_text(d.room) == norm_room or norm_room in _normalize_text(d.room)]
        if not matched:
            all_rooms = sorted({d.room for d in devices})
            rooms_str = ", ".join(all_rooms) if all_rooms else "chưa có"
            return None, f"Không tìm thấy phòng '{room}'. Các phòng hiện có trong nhà: {rooms_str}."

    # Filter by kind with fallback for climate appliances (aircon <-> fan)
    if kind:
        exact = [d for d in matched if d.kind == kind]
        if exact:
            matched = exact
        elif kind == "aircon":
            matched = [d for d in matched if d.kind in {"aircon", "fan"}]
        elif kind == "fan":
            matched = [d for d in matched if d.kind in {"fan", "aircon"}]
        else:
            matched = []

        if not matched:
            kind_labels = {
                "light": "đèn",
                "fan": "quạt",
                "aircon": "điều hòa/quạt",
                "blind": "rèm/cửa sổ",
                "speaker": "loa",
                "display": "màn hình",
                "lock": "khóa cửa",
                "sensor": "cảm biến",
            }
            kind_label = kind_labels.get(kind, kind)
            room_desc = f" trong '{room}'" if room else ""
            return None, f"Không tìm thấy {kind_label} nào{room_desc}."

    # Filter by name if provided
    if name:
        norm_name = _normalize_text(name)
        named_matches = [d for d in matched if norm_name in _normalize_text(d.name)]
        if named_matches:
            return named_matches[0], None

    # Return the first matched device
    return matched[0], None


def _resolve_device(
    room: str | None = None,
    kind: str | None = None,
    device_id: str | None = None,
    name: str | None = None,
) -> tuple[Device | None, str | None]:
    """Dynamically resolve a device from registry by ID, room, kind, or name.

    Strictly scoped to active registry without cross-fallback to isolate simulator and real modes.
    """
    active_registry = _get_registry()
    return _resolve_device_in_reg(active_registry, room, kind, device_id, name)


def _tool_result(status: str, **payload: object) -> str:
    return json.dumps({"status": status, **payload}, ensure_ascii=False, separators=(",", ":"))


def _execute_device_control(
    device: Device,
    action: str,
    value: dict[str, ScalarValue] | None = None,
) -> str:
    """Helper to execute device control and format the JSON tool response."""
    ctrl_fn = _get_control_device()
    active_registry = _get_registry()
    active_mode = getattr(active_registry, "mode", None) or _sd.get_active_data_mode()
    try:
        dev, error = ctrl_fn(device.id, action, value, registry=active_registry, mode=active_mode)
    except TypeError:
        dev, error = ctrl_fn(device.id, action, value)

    if error in {"timeout", "ack_timeout", "state_timeout"}:
        return _tool_result(
            "timeout",
            device_id=device.id,
            action=action,
            message=f"Thiết bị '{device.name}' không phản hồi; chưa xác nhận thay đổi.",
        )
    if error == "device_offline":
        return _tool_result(
            "offline",
            device_id=device.id,
            action=action,
            message=f"Thiết bị '{device.name}' đang offline; chưa thực hiện lệnh.",
        )
    if error == "unavailable":
        return _tool_result(
            "unavailable",
            device_id=device.id,
            action=action,
            message="Hub điều khiển hiện không khả dụng; chưa thực hiện lệnh.",
        )
    if error == "approval_required":
        return _tool_result(
            "denied",
            device_id=device.id,
            action=action,
            message="Thao tác cần được tạo và phê duyệt trong ứng dụng Homing Hub.",
        )
    if error == "not_found":
        return _tool_result(
            "not_found",
            device_id=device.id,
            action=action,
            message="Không tìm thấy thiết bị; chưa thực hiện.",
        )
    if error:
        return _tool_result(
            "invalid_request",
            device_id=device.id,
            action=action,
            error=error,
            message=f"Lệnh không hợp lệ cho '{device.name}'; chưa thực hiện.",
        )
    if not dev:
        return _tool_result(
            "failed",
            device_id=device.id,
            action=action,
            message="Hub không trả về trạng thái xác nhận.",
        )

    return _tool_result("success", action=action, value=value, device=dev.model_dump())
