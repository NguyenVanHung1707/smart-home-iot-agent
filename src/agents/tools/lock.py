"""LangChain tool for smart door lock control."""

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


class ControlLockInput(_StrictToolInput):
    room: str = Field(description="Tên phòng hoặc vị trí có khóa cửa (ví dụ: 'Lối vào', 'Cửa chính')")
    action: Literal["lock"] = Field(
        description="Hành động khóa cửa ('lock'). Mở khóa cửa không được phép qua AI tool vì lý do an toàn."
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của khóa cửa",
    )


@tool(args_schema=ControlLockInput)
def control_lock(
    room: str,
    action: Literal["lock"],
    device_id: str | None = None,
) -> str:
    """Khóa cửa an toàn. Lưu ý: Lệnh mở khóa không được hỗ trợ qua AI tool để đảm bảo an ninh."""
    device, err = _resolve_device(room=room, kind="lock", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy khóa cửa.")

    return _execute_device_control(device, "lock", None)
