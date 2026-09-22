"""LangChain tools for scheduling device delay timers and countdown actions."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    ScalarValue,
    _get_registry,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)
from src.services.timer_service import timer_service


class SetDeviceTimerInput(_StrictToolInput):
    duration_minutes: float = Field(
        ge=0.01,
        le=1440.0,
        description="Thời gian hẹn giờ đếm ngược tính theo phút (ví dụ: 0.5 cho 30 giây, 15, 30, 60, 120)",
    )
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động sẽ thực thi khi hết thời gian: 'on' (bật), 'off' (tắt), 'toggle' (đổi trạng thái), 'set' (cài đặt thông số)",
    )
    room: str | None = Field(
        default=None,
        description="Tên phòng chứa thiết bị (ví dụ: 'Phòng khách', 'Phòng ngủ')",
    )
    kind: str | None = Field(
        default=None,
        description="Loại thiết bị: 'light' (đèn), 'aircon' (quạt/điều hòa), 'blind' (rèm), 'speaker' (loa), 'display' (màn hình)",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của thiết bị nếu muốn chỉ định trực tiếp",
    )
    value: dict[str, ScalarValue] | None = Field(
        default=None,
        description="Giá trị cài đặt khi action='set' (ví dụ: {'target_temperature': 24.0} hoặc {'brightness': 50})",
    )
    label: str | None = Field(
        default=None,
        description="Tùy chọn: Ghi chú hoặc nhãn cho bộ hẹn giờ",
    )


@tool(args_schema=SetDeviceTimerInput)
def set_device_timer(
    duration_minutes: float,
    action: Literal["on", "off", "toggle", "set"],
    room: str | None = None,
    kind: str | None = None,
    device_id: str | None = None,
    value: dict[str, ScalarValue] | None = None,
    label: str | None = None,
) -> str:
    """Hẹn giờ đếm ngược để tự động bật, tắt hoặc điều chỉnh thiết bị sau một khoảng thời gian (ví dụ: tắt quạt sau 30 phút, hẹn 1 tiếng nữa bật điều hòa)."""
    device, err = _resolve_device(room=room, kind=kind, device_id=device_id)
    if err or not device:
        return _tool_result(
            "not_found",
            message=err or f"Không tìm thấy thiết bị phù hợp để hẹn giờ (room={room}, kind={kind}).",
        )

    duration_seconds = duration_minutes * 60.0
    item = timer_service.create_timer(
        device_id=device.id,
        device_name=device.name,
        room=device.room,
        action=action,
        duration_seconds=duration_seconds,
        value=value,
        label=label or f"{action} {device.name}",
    )

    formatted_time = (
        f"{duration_minutes:.1f}".rstrip("0").rstrip(".") if duration_minutes < 1 else f"{int(duration_minutes)}"
    )

    return _tool_result(
        "success",
        timer_id=item.id,
        device_id=device.id,
        device_name=device.name,
        room=device.room,
        action=action,
        value=value,
        duration_minutes=duration_minutes,
        execute_at=item.execute_at,
        message=(
            f"Đã hẹn giờ: Tự động {action} '{device.name}' ({device.room}) sau {formatted_time} phút "
            f"(vào lúc {item.execute_at[11:19]})."
        ),
    )


class ListDeviceTimersInput(_StrictToolInput):
    active_only: bool = Field(
        default=True,
        description=(
            "Bắt buộc True cho câu hỏi về hẹn giờ đang hoạt động/hiện tại/còn chạy. "
            "Chỉ đặt False khi người dùng nói rõ muốn lịch sử, hẹn giờ đã hết hạn hoặc quá khứ."
        ),
    )


@tool(args_schema=ListDeviceTimersInput)
def list_device_timers(active_only: bool = True) -> str:
    """Tra cứu timer: dùng active_only=True mặc định; False chỉ cho lịch sử được yêu cầu rõ."""
    timers = timer_service.list_timers(active_only=active_only)
    if not timers:
        return _tool_result(
            "success",
            count=0,
            timers=[],
            message="Hiện không có bộ hẹn giờ nào đang đếm ngược.",
        )

    timer_dicts = [t.to_dict() for t in timers]
    return _tool_result(
        "success",
        count=len(timers),
        timers=timer_dicts,
        message=f"Đang có {len(timers)} bộ hẹn giờ đang hoạt động.",
    )


class CancelDeviceTimerInput(_StrictToolInput):
    timer_id: str | None = Field(
        default=None,
        description="Mã ID của bộ hẹn giờ cần hủy",
    )
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Hủy tất cả hẹn giờ trong phòng này",
    )
    kind: str | None = Field(
        default=None,
        description="Tùy chọn: Hủy tất cả hẹn giờ cho loại thiết bị này",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: Hủy tất cả hẹn giờ của thiết bị này",
    )


@tool(args_schema=CancelDeviceTimerInput)
def cancel_device_timer(
    timer_id: str | None = None,
    room: str | None = None,
    kind: str | None = None,
    device_id: str | None = None,
) -> str:
    """Hủy một hoặc nhiều bộ hẹn giờ đếm ngược đang hoạt động."""
    if timer_id:
        success = timer_service.cancel_timer(timer_id)
        if success:
            return _tool_result("success", message=f"Đã hủy thành công bộ hẹn giờ {timer_id[:8]}.")
        return _tool_result("not_found", message=f"Không tìm thấy bộ hẹn giờ còn hiệu lực với ID {timer_id}.")

    active_registry = _get_registry()
    if device_id:
        target_ids = [device_id]
    elif room or kind:
        device, _ = _resolve_device(room=room, kind=kind)
        target_ids = [device.id] if device else []
    else:
        target_ids = [d.id for d in active_registry.list()]

    total_cancelled = 0
    for dev_id in target_ids:
        total_cancelled += timer_service.cancel_by_device(dev_id)

    if total_cancelled > 0:
        return _tool_result(
            "success",
            cancelled_count=total_cancelled,
            message=f"Đã hủy thành công {total_cancelled} bộ hẹn giờ.",
        )

    return _tool_result(
        "not_found",
        message="Không tìm thấy bộ hẹn giờ nào phù hợp để hủy.",
    )
