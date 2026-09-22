"""LangChain tool for batch device control across kinds or rooms."""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    ScalarValue,
    _execute_device_control,
    _get_registry,
    _normalize_text,
    _StrictToolInput,
    _tool_result,
)


class BatchControlDevicesInput(_StrictToolInput):
    action: Literal["on", "off", "toggle", "set"] = Field(
        description="Hành động cần áp dụng: 'on', 'off', 'toggle', 'set'",
    )
    kind: Literal["light", "fan", "aircon", "blind", "speaker", "display"] | None = Field(
        default=None,
        description="Loại thiết bị cần điều khiển hàng loạt: 'light', 'fan', 'aircon', 'blind', 'speaker', 'display'. Để null nếu muốn áp dụng cho mọi loại thiết bị trong phòng.",
    )
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Tên phòng cụ thể (ví dụ: 'Phòng khách', 'Tầng 1'). Để null để áp dụng cho toàn bộ nhà.",
    )
    value: dict[str, ScalarValue] | None = Field(
        default=None,
        description="Giá trị cài đặt khi action='set' (ví dụ: {'brightness': 50} hoặc {'position': 0})",
    )


@tool(args_schema=BatchControlDevicesInput)
def batch_control_devices(
    action: Literal["on", "off", "toggle", "set"],
    kind: Literal["light", "fan", "aircon", "blind", "speaker", "display"] | None = None,
    room: str | None = None,
    value: dict[str, ScalarValue] | None = None,
) -> str:
    """Điều khiển hàng loạt nhiều thiết bị cùng loại hoặc trong cùng một phòng (ví dụ: tắt tất cả đèn, bật quạt các phòng)."""
    active_registry = _get_registry()
    devices = active_registry.list()

    # Never allow batch lock control via this tool
    devices = [d for d in devices if d.kind != "lock"]

    if kind:
        devices = [d for d in devices if d.kind == kind]

    if room:
        norm_room = _normalize_text(room)
        devices = [d for d in devices if _normalize_text(d.room) == norm_room or norm_room in _normalize_text(d.room)]

    if not devices:
        filter_desc = f" loại '{kind}'" if kind else ""
        room_desc = f" trong '{room}'" if room else ""
        return _tool_result(
            "not_found",
            message=f"Không tìm thấy thiết bị nào phù hợp{filter_desc}{room_desc} để điều khiển.",
        )

    succeeded = []
    failed = []

    for dev in devices:
        res_str = _execute_device_control(dev, action, value)
        res_json = json.loads(res_str)
        if res_json.get("status") == "success":
            succeeded.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "room": dev.room,
                    "state": res_json.get("device", {}).get("state"),
                }
            )
        else:
            failed.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "error": res_json.get("message") or res_json.get("status"),
                }
            )

    return _tool_result(
        "success" if succeeded else "failed",
        action=action,
        total_matched=len(devices),
        success_count=len(succeeded),
        failed_count=len(failed),
        succeeded=succeeded,
        failed=failed,
        message=f"Đã thực hiện '{action}' cho {len(succeeded)}/{len(devices)} thiết bị.",
    )
