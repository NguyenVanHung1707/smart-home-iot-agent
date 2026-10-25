"""LangChain tool for bedtime environment optimization and sleep comfort setup."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result
from src.services.device_control import control_device
import src.services.devices as devices_mod

logger = logging.getLogger(__name__)


class OptimizeSleepEnvironmentInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    bedroom: str = Field(
        default="Phòng ngủ",
        description="Tên phòng ngủ cần tối ưu môi trường (mặc định: 'Phòng ngủ').",
    )
    keep_bedroom_fan: bool = Field(
        default=True,
        description="Bật quạt phòng ngủ phe phẩy thoang thoảng tạo gió êm khi ngủ.",
    )
    lock_front_door: bool = Field(
        default=True,
        description="Tự động khóa cửa chính để đảm bảo an ninh tuyệt đối suốt đêm.",
    )
    mode: str = Field(
        default="real",
        description="Chế độ dữ liệu: 'real' hoặc 'simulator'.",
    )


@tool(args_schema=OptimizeSleepEnvironmentInput)
def optimize_sleep_environment(
    bedroom: str = "Phòng ngủ",
    keep_bedroom_fan: bool = True,
    lock_front_door: bool = True,
    mode: str = "real",
) -> str:
    """Tự động chuẩn bị ngôi nhà vào chế độ ngủ ngon: khóa cửa chính, tắt toàn bộ đèn phòng khách & bếp, bật quạt ngủ êm ái và kiểm tra nhiệt độ lý tưởng."""
    reg = devices_mod.get_registry(mode)
    actions_taken: list[str] = []

    # 1. Tắt đèn các khu vực sinh hoạt chung (phòng khách, phòng bếp)
    for dev_id, room_label in [("living-light", "phòng khách"), ("kitchen-light", "phòng bếp")]:
        dev = reg.get(dev_id)
        if dev:
            control_device(dev_id, "off", mode=mode)
            actions_taken.append(f"Đã tắt đèn {room_label}")

    # 2. Khóa cửa chính an toàn
    if lock_front_door:
        lock_dev = reg.get("entry-lock")
        if lock_dev:
            control_device("entry-lock", "lock", mode=mode)
            actions_taken.append("Đã khóa chốt cửa chính an toàn")

    # 3. Chuẩn bị quạt phòng ngủ
    if keep_bedroom_fan:
        fan_dev = reg.get("bedroom-fan")
        if fan_dev:
            control_device("bedroom-fan", "on", 1, mode=mode)
            actions_taken.append("Đã bật quạt phòng ngủ mức êm ái")

    # 4. Màn hình OLED hiển thị lời chúc ngủ ngon
    disp_dev = reg.get("living-display")
    if disp_dev:
        control_device("living-display", "set_message", {"text": "Ngu ngon! An ninh da bat."}, mode=mode)
        actions_taken.append("Màn hình OLED chuyển sang chế độ ban đêm")

    # 5. Kiểm tra nhiệt độ và độ ẩm phòng
    temp_dev = reg.get("living-temperature")
    climate_advice = ""
    if temp_dev and isinstance(temp_dev.state, dict):
        temp = float(temp_dev.state.get("temperature", 28.0))
        hum = float(temp_dev.state.get("humidity", 65.0))
        if temp > 28.0:
            climate_advice = f" Nhiệt độ hiện tại {temp}°C hơi ấm, bạn nên mở hé cửa sổ hoặc bật quạt để phòng thông thoáng hơn."
        elif temp < 20.0:
            climate_advice = f" Nhiệt độ hiện tại {temp}°C se lạnh, bạn nên đắp chăn mỏng để giữ ấm cổ và ngực."
        else:
            climate_advice = f" Nhiệt độ {temp}°C và độ ẩm {hum}% đang ở mức lý tưởng cho giấc ngủ sâu."

    summary = (
        f"Đã kích hoạt chế độ ngủ ngon: {', '.join(actions_taken)}.{climate_advice} "
        f"Chúc bạn và gia đình có một giấc ngủ thật ngon và an lành!"
    )

    return _tool_result(
        "success",
        actions_taken=actions_taken,
        bedroom=bedroom,
        climate_advice=climate_advice.strip(),
        message=summary,
    )
