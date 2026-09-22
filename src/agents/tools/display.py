"""LangChain tool for smart display control."""

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


class ControlDisplayInput(_StrictToolInput):
    room: str = Field(description="Tên phòng có màn hình hiển thị")
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động: 'on' (bật), 'off' (tắt), 'toggle' (đổi trạng thái), 'set' (đổi thông điệp)"
    )
    message: str | None = Field(
        default=None,
        max_length=200,
        description="Nội dung thông điệp cần hiển thị lên màn hình (khi action='set')",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của màn hình",
    )


@tool(args_schema=ControlDisplayInput)
def control_display(
    room: str,
    action: Literal["on", "off", "toggle", "set"],
    message: str | None = None,
    device_id: str | None = None,
) -> str:
    """Điều khiển màn hình hiển thị (bật/tắt màn hình hoặc cập nhật thông điệp hiển thị)."""
    device, err = _resolve_device(room=room, kind="display", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy màn hình.")

    value = {"message": message} if action == "set" and message is not None else None
    return _execute_device_control(device, action, value)
