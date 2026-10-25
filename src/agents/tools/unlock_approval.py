"""LangChain tool for requesting secure device unlock approval."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _get_registry,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)
from src.models.schemas import DeviceCommand
from src.services.approvals import approvals


class RequestUnlockApprovalInput(_StrictToolInput):
    reason: str = Field(
        description="Lý do hoặc tên người yêu cầu mở khóa (ví dụ: 'Chủ nhà nhờ mở cửa', 'Khách đến chơi')",
    )
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Phòng hoặc vị trí có khóa cửa (ví dụ: 'Lối vào', 'Cửa chính')",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của khóa cửa (mặc định là khóa chính)",
    )


@tool(args_schema=RequestUnlockApprovalInput)
def request_unlock_approval(
    reason: str,
    room: str | None = None,
    device_id: str | None = None,
) -> str:
    """Tạo yêu cầu phê duyệt mở khóa cửa an toàn trên ứng dụng Homing Hub khi người dùng muốn mở cửa."""
    active_registry = _get_registry()
    if device_id:
        device = active_registry.get(device_id)
    else:
        device, _ = _resolve_device(room=room or "Lối vào", kind="lock")
        if not device:
            # Fallback to first available lock
            locks = [d for d in active_registry.list() if d.kind == "lock"]
            device = locks[0] if locks else None

    if not device:
        return _tool_result(
            "not_found",
            message="Không tìm thấy thiết bị khóa cửa trong hệ thống để tạo yêu cầu.",
        )

    # Reject unlock request via AI directly according to strict security policy
    return _tool_result(
        "denied",
        device_id=device.id,
        device_name=device.name,
        message=(
            "Yêu cầu mở cửa qua AI bị từ chối vì lý do an ninh. "
            "Vui lòng nhập mật khẩu trên bàn phím, trên giao diện web hoặc quét thẻ từ RFID để mở cửa."
        ),
    )
