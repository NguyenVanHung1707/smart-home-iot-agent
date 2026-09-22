"""LangChain tool for activating smart home scenes and routines."""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _execute_device_control,
    _get_registry,
    _normalize_text,
    _StrictToolInput,
    _tool_result,
)


class ActivateSceneInput(_StrictToolInput):
    scene: Literal["good_night", "leave_home", "welcome_home", "movie_mode", "all_off"] = Field(
        description=(
            "Tên ngữ cảnh cần kích hoạt: "
            "'good_night' (chế độ đi ngủ - tắt đèn, đóng rèm, khóa cửa), "
            "'leave_home' (chế độ rời nhà - tắt tất cả thiết bị điện, khóa cửa), "
            "'welcome_home' (chế độ về nhà - bật đèn phòng khách, bật điều hòa mát, mở rèm), "
            "'movie_mode' (chế độ xem phim - giảm sáng đèn 20%, đóng rèm), "
            "'all_off' (tắt toàn bộ đèn, quạt, điều hòa, loa)"
        )
    )
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Phòng áp dụng cụ thể (nếu ngữ cảnh chỉ áp dụng cho một phòng nhất định)",
    )


@tool(args_schema=ActivateSceneInput)
def activate_scene(
    scene: Literal["good_night", "leave_home", "welcome_home", "movie_mode", "all_off"],
    room: str | None = None,
) -> str:
    """Kích hoạt một kịch bản nhà thông minh tự động (ví dụ: 'good_night', 'leave_home', 'welcome_home', 'movie_mode', 'all_off')."""
    active_registry = _get_registry()
    devices = active_registry.list()

    if room:
        norm_room = _normalize_text(room)
        target_devices = [
            d for d in devices if _normalize_text(d.room) == norm_room or norm_room in _normalize_text(d.room)
        ]
    else:
        target_devices = devices

    actions_executed: list[dict] = []

    def _exec(dev, action, val=None):
        res = json.loads(_execute_device_control(dev, action, val))
        actions_executed.append(
            {
                "device_id": dev.id,
                "device_name": dev.name,
                "room": dev.room,
                "action": action,
                "status": res.get("status"),
            }
        )

    if scene == "good_night":
        # Tắt toàn bộ đèn
        for d in [d for d in target_devices if d.kind == "light"]:
            _exec(d, "off")
        # Đóng rèm
        for d in [d for d in target_devices if d.kind == "blind"]:
            _exec(d, "set", {"position": 0})
        # Khóa cửa
        for d in [d for d in devices if d.kind == "lock"]:
            _exec(d, "lock")
        # Điều hòa phòng ngủ hoặc phòng áp dụng
        for d in [d for d in target_devices if d.kind == "aircon"]:
            _exec(d, "set", {"target_temperature": 26.0, "mode": "cool"})

    elif scene == "leave_home":
        # Tắt tất cả đèn, điều hòa, quạt, loa, màn hình
        for d in [d for d in devices if d.kind in {"light", "fan", "aircon", "speaker", "display"}]:
            _exec(d, "off")
        # Đóng toàn bộ rèm/cửa sổ
        for d in [d for d in devices if d.kind == "blind"]:
            _exec(d, "set", {"position": 0})
        # Khóa toàn bộ cửa
        for d in [d for d in devices if d.kind == "lock"]:
            _exec(d, "lock")

    elif scene == "welcome_home":
        # Bật đèn phòng khách
        for d in [d for d in devices if d.kind == "light" and "khách" in _normalize_text(d.room)]:
            _exec(d, "on")
        # Bật điều hòa phòng khách 24 độ
        for d in [d for d in devices if d.kind == "aircon" and "khách" in _normalize_text(d.room)]:
            _exec(d, "set", {"target_temperature": 24.0, "mode": "cool"})
        # Mở rèm 80%
        for d in [d for d in devices if d.kind == "blind"]:
            _exec(d, "set", {"position": 80})
        # Đổi thông điệp màn hình
        for d in [d for d in devices if d.kind == "display"]:
            _exec(d, "set", {"message": "Chào mừng bạn về nhà!"})

    elif scene == "movie_mode":
        # Giảm độ sáng đèn còn 20%
        for d in [d for d in target_devices if d.kind == "light"]:
            _exec(d, "set", {"brightness": 20})
        # Đóng rèm
        for d in [d for d in target_devices if d.kind == "blind"]:
            _exec(d, "set", {"position": 0})
        # Điều hòa mát dịu 23 độ
        for d in [d for d in target_devices if d.kind == "aircon"]:
            _exec(d, "set", {"target_temperature": 23.0, "mode": "cool"})

    elif scene == "all_off":
        # Tắt hết thiết bị điện
        for d in [d for d in target_devices if d.kind in {"light", "fan", "aircon", "speaker", "display"}]:
            _exec(d, "off")

    success_items = [a for a in actions_executed if a["status"] == "success"]
    failed_items = [a for a in actions_executed if a["status"] != "success"]

    scene_names = {
        "good_night": "Chế độ Đi ngủ",
        "leave_home": "Chế độ Rời nhà",
        "welcome_home": "Chế độ Về nhà",
        "movie_mode": "Chế độ Xem phim",
        "all_off": "Tắt toàn bộ thiết bị",
    }

    return _tool_result(
        "success" if success_items else "failed",
        scene=scene,
        scene_name=scene_names.get(scene, scene),
        total_actions=len(actions_executed),
        success_count=len(success_items),
        failed_count=len(failed_items),
        details=actions_executed,
        message=f"Đã kích hoạt {scene_names.get(scene, scene)} ({len(success_items)}/{len(actions_executed)} lệnh thành công).",
    )
