"""LangChain tool for evaluating indoor air quality, comfort index, and providing ventilation recommendations."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _get_registry, _normalize_text, _StrictToolInput, _tool_result

logger = logging.getLogger(__name__)


class EvaluateAirQualityInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    room: str | None = Field(
        default=None,
        description="Phòng cần đánh giá chất lượng không khí (ví dụ: 'Phòng khách', 'Phòng bếp', 'Phòng ngủ'). Mặc định là toàn nhà.",
    )


def _compute_iaq_score(temp: float | None, hum: float | None, gas: float | None) -> tuple[int, str, list[str]]:
    """Calculate Indoor Air Quality (IAQ) score (0-100), comfort status and action steps."""
    score = 100
    deductions: list[str] = []
    actions: list[str] = []

    # 1. Gas evaluation
    if gas is not None:
        if gas >= 300:
            score -= 60
            deductions.append(f"Cảnh báo khí gas nguy hiểm ({gas} ppm)!")
            actions.append("🚨 Mở ngay tất cả cửa sổ, ngắt van gas và bật quạt thông gió để thoát khí.")
        elif gas >= 150:
            score -= 25
            deductions.append(f"Nồng độ khí gas/mùi bếp cao ({gas} ppm).")
            actions.append("Bật quạt hút mùi nhà bếp và mở cửa sổ để không khí thoáng mát hơn.")

    # 2. Humidity evaluation
    if hum is not None:
        if hum >= 80:
            score -= 20
            deductions.append(f"Độ ẩm rất cao ({hum}%), dễ sinh ẩm mốc và vi khuẩn.")
            actions.append("Bật chế độ hút ẩm (Dry) trên điều hòa hoặc dùng máy hút ẩm để tránh nồm sàn.")
        elif hum <= 35:
            score -= 15
            deductions.append(f"Không khí hanh khô ({hum}%), dễ gây khô rát cổ họng.")
            actions.append("Nên bật máy phun sương bù ẩm hoặc đặt thêm chậu nước trong phòng điều hòa.")

    # 3. Temperature evaluation
    if temp is not None:
        if temp >= 32:
            score -= 20
            deductions.append(f"Nhiệt độ nóng bức ({temp}°C).")
            actions.append("Bật điều hòa ở mức 26°C kết hợp quạt để làm mát không gian.")
        elif temp <= 16:
            score -= 15
            deductions.append(f"Nhiệt độ phòng lạnh ({temp}°C).")
            actions.append("Đóng kín các khe cửa sổ để tránh gió lùa.")

    score = max(0, min(100, score))

    if score >= 85:
        status = "Không khí trong lành, rất thoải mái (Lý tưởng)"
    elif score >= 65:
        status = "Không khí mức khá, chấp nhận được"
    elif score >= 45:
        status = "Chất lượng không khí trung bình, cần thông gió"
    else:
        status = "CẢNH BÁO: Chất lượng không khí kém, cần can thiệp ngay"

    if not actions:
        actions.append("Chỉ số không khí đang rất tốt, tiếp tục duy trì thông gió tự nhiên.")

    return score, status, actions


@tool("evaluate_air_quality", args_schema=EvaluateAirQualityInput)
def evaluate_air_quality(room: str | None = None) -> str:
    """Đánh giá toàn diện chất lượng không khí trong nhà (điểm số IAQ 0-100, nhiệt ẩm, khí gas) và đưa ra giải pháp thanh lọc."""
    reg = _get_registry()
    sensors = [d for d in reg.list() if d.kind == "sensor"]

    if room:
        norm_room = _normalize_text(room)
        sensors = [s for s in sensors if _normalize_text(s.room) == norm_room or norm_room in _normalize_text(s.room)]

    if not sensors:
        return _tool_result(
            "not_found",
            message=f"Không tìm thấy cảm biến môi trường nào{' trong ' + room if room else ''}.",
        )

    # Extract readings
    temp_val: float | None = None
    hum_val: float | None = None
    gas_val: float | None = None
    lux_val: float | None = None

    for s in sensors:
        state = s.state if isinstance(s.state, dict) else {}
        if "temperature" in state and temp_val is None:
            try:
                temp_val = float(state["temperature"])
            except Exception:
                pass
        if "humidity" in state and hum_val is None:
            try:
                hum_val = float(state["humidity"])
            except Exception:
                pass
        if "gas" in state and gas_val is None:
            try:
                gas_val = float(state["gas"])
            except Exception:
                pass
        if "lux" in state and lux_val is None:
            try:
                lux_val = float(state["lux"])
            except Exception:
                pass

    score, status, actions = _compute_iaq_score(temp_val, hum_val, gas_val)

    readings_summary = []
    if temp_val is not None:
        readings_summary.append(f"nhiệt độ {temp_val}°C")
    if hum_val is not None:
        readings_summary.append(f"độ ẩm {hum_val}%")
    if gas_val is not None:
        readings_summary.append(f"khí gas {gas_val} ppm")
    if lux_val is not None:
        readings_summary.append(f"ánh sáng {lux_val} lux")

    readings_text = ", ".join(readings_summary) if readings_summary else "các chỉ số cảm biến"

    summary_msg = (
        f"Chỉ số chất lượng không khí (IAQ): {score}/100 điểm - {status}. "
        f"Ghi nhận ({readings_text}). Lời khuyên: " + " ".join(actions)
    )

    return _tool_result(
        "success",
        room=room or "Toàn nhà",
        iaq_score=score,
        iaq_status=status,
        readings={
            "temperature": temp_val,
            "humidity": hum_val,
            "gas_ppm": gas_val,
            "lux": lux_val,
        },
        actions=actions,
        message=summary_msg,
    )
