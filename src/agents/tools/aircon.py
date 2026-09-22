"""LangChain tool for air conditioner and fan control."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    ScalarValue,
    _execute_device_control,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)


class ControlAirconInput(_StrictToolInput):
    room: str = Field(description="Tên phòng có điều hòa hoặc quạt (ví dụ: 'Phòng khách', 'Phòng ngủ')")
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động: 'on' (bật), 'off' (tắt), 'toggle' (đổi trạng thái), 'set' (chỉnh nhiệt độ/chế độ)"
    )
    target_temperature: float | None = Field(
        default=None,
        ge=16.0,
        le=30.0,
        description="Nhiệt độ mục tiêu từ 16 đến 30 độ C (dùng khi action='set')",
    )
    mode: Literal["auto", "cool", "dry", "fan"] | None = Field(
        default=None,
        description="Chế độ làm mát: 'auto', 'cool', 'dry', 'fan' (dùng khi action='set')",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của thiết bị",
    )


@tool(args_schema=ControlAirconInput)
def control_aircon(
    room: str,
    action: Literal["on", "off", "toggle", "set"],
    target_temperature: float | None = None,
    mode: Literal["auto", "cool", "dry", "fan"] | None = None,
    device_id: str | None = None,
) -> str:
    """Điều khiển điều hòa hoặc quạt trong một phòng (bật, tắt, đặt nhiệt độ mục tiêu, chế độ)."""
    device, err = _resolve_device(room=room, kind="aircon", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy điều hòa/quạt.")

    value: dict[str, ScalarValue] | None = None
    if action == "set":
        value = {}
        if target_temperature is not None:
            value["target_temperature"] = target_temperature
        if mode is not None:
            value["mode"] = mode
        if not value:
            return _tool_result(
                "invalid_request", message="Cần cung cấp target_temperature hoặc mode khi action='set'."
            )

    return _execute_device_control(device, action, value)
