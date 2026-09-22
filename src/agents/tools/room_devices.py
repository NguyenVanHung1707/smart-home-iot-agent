"""LangChain tool for room and device topology inspection."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _get_registry,
    _normalize_text,
    _StrictToolInput,
    _tool_result,
)


class GetRoomDevicesInput(_StrictToolInput):
    room: str | None = Field(
        default=None,
        description="Tên phòng cần kiểm tra. Để null để xem toàn bộ danh sách phòng và các thiết bị trong nhà.",
    )


@tool(args_schema=GetRoomDevicesInput)
def get_room_devices(room: str | None = None) -> str:
    """Tra cứu danh sách các phòng và thiết bị trong nhà, hoặc xem chi tiết các thiết bị trong một phòng cụ thể."""
    active_registry = _get_registry()
    devices = active_registry.list()
    grouped: dict[str, list[dict]] = {}
    for d in devices:
        grouped.setdefault(d.room, []).append(
            {
                "id": d.id,
                "name": d.name,
                "kind": d.kind,
                "online": d.online,
                "state": d.state,
            }
        )

    if room:
        norm_room = _normalize_text(room)
        matched_room_name = next(
            (r for r in grouped if _normalize_text(r) == norm_room or norm_room in _normalize_text(r)),
            None,
        )
        if not matched_room_name:
            return _tool_result(
                "not_found",
                requested_room=room,
                available_rooms=list(grouped.keys()),
                message=f"Không tìm thấy phòng '{room}'. Các phòng hiện có: {', '.join(grouped.keys())}.",
            )

        room_devices = grouped[matched_room_name]
        return _tool_result(
            "success",
            room=matched_room_name,
            device_count=len(room_devices),
            devices=room_devices,
        )

    return _tool_result(
        "success",
        total_rooms=len(grouped),
        total_devices=len(devices),
        rooms=list(grouped.keys()),
        topology=grouped,
    )
