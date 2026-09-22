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

    # Create approval ticket in ApprovalStore
    approval_item = approvals.create(
        device_id=device.id,
        command=DeviceCommand(action="unlock"),
        requested_by=reason,
    )

    return _tool_result(
        "success",
        ticket_id=approval_item.id,
        device_id=device.id,
        device_name=device.name,
        expires_at=approval_item.expires_at,
        requested_by=reason,
        approval_status="pending",
        message=(
            f"Đã tạo yêu cầu mở khóa cho '{device.name}' (Mã ticket: {approval_item.id[:8]}). "
            f"Chủ nhà vui lòng mở ứng dụng Homing Hub để phê duyệt mở cửa trong vòng 2 phút."
        ),
    )
