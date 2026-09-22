"""LangChain tool for smart light control."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _execute_device_control,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)


class ControlLightInput(_StrictToolInput):
    room: str = Field(description="Tên phòng (ví dụ: 'Phòng khách', 'Phòng ngủ', 'Phòng bếp')")
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động: 'on' (bật), 'off' (tắt), 'toggle' (đổi trạng thái), 'set' (chỉnh độ sáng)"
    )
    brightness: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Độ sáng từ 0 đến 100% (bắt buộc khi action='set')",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của đèn nếu muốn chỉ định trực tiếp",
    )


@tool(args_schema=ControlLightInput)
def control_light(
    room: str,
    action: Literal["on", "off", "toggle", "set"],
    brightness: int | None = None,
    device_id: str | None = None,
) -> str:
    """Điều khiển đèn trong một phòng cụ thể (bật, tắt, đổi trạng thái hoặc điều chỉnh độ sáng)."""
    device, err = _resolve_device(room=room, kind="light", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy đèn.")

    value = {"brightness": brightness} if action == "set" and brightness is not None else None
    return _execute_device_control(device, action, value)
