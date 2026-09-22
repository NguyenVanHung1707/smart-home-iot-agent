"""LangChain tool for direct generic device control by device_id."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field, field_validator

from src.agents.tools.base import (
    ScalarValue,
    _execute_device_control,
    _get_registry,
    _StrictToolInput,
    _tool_result,
)


class ControlSmartDeviceInput(_StrictToolInput):
    device_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=64)
    value: dict[str, ScalarValue] | None = None

    @field_validator("action")
    @classmethod
    def reject_unlock(cls, action: str) -> str:
        if action == "unlock":
            raise ValueError("unlock requires the external approval flow")
        return action


@tool(args_schema=ControlSmartDeviceInput)
def control_smart_device(
    device_id: str,
    action: str,
    value: dict[str, ScalarValue] | None = None,
) -> str:
    """Control one exact device through the same validated controller as typed tools."""
    active_registry = _get_registry()
    device = active_registry.get(device_id)
    if device is None:
        return _tool_result("not_found", device_id=device_id, action=action, message="Không tìm thấy thiết bị.")
    return _execute_device_control(device, action, value)
