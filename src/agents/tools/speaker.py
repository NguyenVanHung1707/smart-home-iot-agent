"""LangChain tool for smart speaker control."""

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


class ControlSpeakerInput(_StrictToolInput):
    room: str = Field(description="Tên phòng có loa thông minh (ví dụ: 'Phòng khách')")
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động: 'on' (bật), 'off' (tắt), 'toggle' (đổi trạng thái), 'set' (chỉnh âm lượng)"
    )
    volume: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Mức âm lượng từ 0 đến 100% (dùng khi action='set')",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của loa",
    )


@tool(args_schema=ControlSpeakerInput)
def control_speaker(
    room: str,
    action: Literal["on", "off", "toggle", "set"],
    volume: int | None = None,
    device_id: str | None = None,
) -> str:
    """Điều khiển loa thông minh (bật/tắt phát nhạc, điều chỉnh âm lượng)."""
    device, err = _resolve_device(room=room, kind="speaker", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy loa.")

    value = {"volume": volume} if action == "set" and volume is not None else None
    return _execute_device_control(device, action, value)
