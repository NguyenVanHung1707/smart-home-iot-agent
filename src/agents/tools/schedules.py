"""LangChain tool for inspecting smart home automation schedules and timers."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _normalize_text,
    _StrictToolInput,
    _tool_result,
)


class GetSchedulesInput(_StrictToolInput):
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Lọc lịch trình theo phòng cụ thể",
    )
    kind: str | None = Field(
        default=None,
        description="Tùy chọn: Lọc lịch trình theo loại thiết bị (ví dụ: 'light', 'blind', 'lock')",
    )


# Standard system automated routines configured in Homing Hub
_DEFAULT_SCHEDULES = [
    {
        "id": "sched-morning-blind",
        "name": "Mở rèm chào buổi sáng",
        "time": "06:30",
        "days": "Thứ 2 - Chủ Nhật",
        "room": "Phòng khách",
        "kind": "blind",
        "action": "Mở rèm 80%",
        "enabled": True,
    },
    {
        "id": "sched-night-lockdown",
        "name": "Khóa an ninh ban đêm",
        "time": "23:00",
        "days": "Hàng ngày",
        "room": "Lối vào",
        "kind": "lock",
        "action": "Tự động khóa cửa chính và tắt đèn hành lang",
        "enabled": True,
    },
    {
        "id": "sched-energy-saving",
        "name": "Tiết kiệm điện ban ngày",
        "time": "08:30",
        "days": "Thứ 2 - Thứ 6",
        "room": "Toàn nhà",
        "kind": "aircon",
        "action": "Tắt các điều hòa và quạt khi không có người",
        "enabled": True,
    },
    {
        "id": "sched-gas-monitoring",
        "name": "Giám sát rò rỉ khí gas 24/7",
        "time": "Liên tục",
        "days": "Hàng ngày",
        "room": "Phòng bếp",
        "kind": "sensor",
        "action": "Kích hoạt còi báo động và gửi thông báo khẩn cấp khi gas >= 300 ppm",
        "enabled": True,
    },
]


@tool(args_schema=GetSchedulesInput)
def get_schedules(
    room: str | None = None,
    kind: str | None = None,
) -> str:
    """Tra cứu danh sách các lịch hẹn giờ và tự động hóa (automations) đang được thiết lập trong nhà."""
    schedules = list(_DEFAULT_SCHEDULES)

    if room:
        norm_room = _normalize_text(room)
        schedules = [
            s
            for s in schedules
            if _normalize_text(s["room"]) == norm_room
            or norm_room in _normalize_text(s["room"])
            or s["room"] == "Toàn nhà"
        ]

    if kind:
        schedules = [s for s in schedules if s.get("kind") == kind]

    if not schedules:
        return _tool_result(
            "not_found",
            message=f"Không tìm thấy lịch trình nào phù hợp với bộ lọc (room={room}, kind={kind}).",
        )

    return _tool_result(
        "success",
        total=len(schedules),
        schedules=schedules,
        message=f"Hệ thống đang có {len(schedules)} lịch trình/tự động hóa đang hoạt động.",
    )
