"""LangChain tool for motorized blinds and windows control."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _execute_device_control,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)


class ControlBlindInput(_StrictToolInput):
    room: str = Field(description="Tên phòng có rèm cửa hoặc cửa sổ tự động")
    position: int = Field(
        ge=0,
        le=100,
        description="Mức độ mở rèm từ 0% (đóng hoàn toàn) đến 100% (mở hoàn toàn)",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của rèm/cửa sổ",
    )


@tool(args_schema=ControlBlindInput)
def control_blind(
    room: str,
    position: int,
    device_id: str | None = None,
) -> str:
    """Điều khiển rèm cửa hoặc cửa sổ tự động trong một phòng (chỉnh mức độ mở từ 0% đến 100%)."""
    device, err = _resolve_device(room=room, kind="blind", device_id=device_id)
    if err or not device:
        return _tool_result("not_found", room=room, action="set", message=err or "Không tìm thấy rèm/cửa sổ.")

    return _execute_device_control(device, "set", {"position": position})
