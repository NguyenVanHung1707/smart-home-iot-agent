"""LangChain tool for analyzing smart home power consumption and providing energy-saving recommendations."""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _get_registry, _normalize_text, _StrictToolInput, _tool_result

logger = logging.getLogger(__name__)

# EVN Tiered Residential Electricity Price in Vietnam (average ~2,400 VND/kWh)
_AVG_ELECTRICITY_PRICE_VND_PER_KWH = 2450.0

# Nominal Wattage ratings for home devices
_DEVICE_WATTAGE_PROFILE: dict[str, float] = {
    "light": 20.0,         # LED lights avg 15-25W
    "fan": 60.0,           # Ceiling / stand fans avg 50-70W
    "aircon": 1100.0,      # Inverter air conditioner avg 700-1400W
    "display": 120.0,      # Smart TV / Monitor
    "speaker": 35.0,       # Smart Speaker / Soundbar
    "blind": 10.0,         # Motorized blind during motion
    "lock": 3.0,           # Smart lock standby
    "sensor": 2.0,         # Environment / motion sensors
    "generic": 50.0,       # Other appliances
}


class GetEnergyAnalyticsInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    period: Literal["realtime", "today", "month"] = Field(
        default="today",
        description="Khung thời gian phân tích: 'realtime' (công suất tức thời), 'today' (ước tính hôm nay), 'month' (ước tính cả tháng).",
    )
    room: str | None = Field(
        default=None,
        description="Tùy chọn: Giới hạn phân tích cho một phòng cụ thể (ví dụ: 'Phòng khách', 'Phòng ngủ').",
    )


def _estimate_device_watts(device: Any) -> float:
    """Calculate instantaneous active wattage for a device."""
    state = device.state if isinstance(device.state, dict) else {}
    kind = getattr(device, "kind", "generic")

    # If device is powered off or offline
    power = state.get("power")
    if power is False or power == 0 or power == "off":
        return _DEVICE_WATTAGE_PROFILE.get("sensor", 2.0) if kind in {"sensor", "lock"} else 0.5  # Standby 0.5W

    base_watts = _DEVICE_WATTAGE_PROFILE.get(kind, _DEVICE_WATTAGE_PROFILE["generic"])

    if kind == "light":
        brightness = state.get("brightness", 100)
        try:
            ratio = float(brightness) / 100.0
            return max(5.0, base_watts * ratio)
        except Exception:
            return base_watts

    if kind == "aircon":
        # Inverter load varies based on set temperature
        target_temp = state.get("temperature", 25)
        try:
            t = float(target_temp)
            if t <= 20:
                return 1350.0
            elif t <= 23:
                return 1100.0
            elif t <= 26:
                return 800.0
            else:
                return 600.0
        except Exception:
            return base_watts

    if kind == "fan":
        speed = state.get("speed", 2)
        try:
            s = int(speed)
            return 35.0 if s == 1 else (55.0 if s == 2 else 75.0)
        except Exception:
            return base_watts

    return base_watts


@tool("get_energy_analytics", args_schema=GetEnergyAnalyticsInput)
def get_energy_analytics(
    period: Literal["realtime", "today", "month"] = "today",
    room: str | None = None,
) -> str:
    """Phân tích mức tiêu thụ điện năng (Watts/kWh) của toàn bộ thiết bị trong nhà, ước tính tiền điện (VND) và đưa ra gợi ý tiết kiệm."""
    reg = _get_registry()
    all_devices = reg.list()

    if room:
        norm_room = _normalize_text(room)
        all_devices = [d for d in all_devices if _normalize_text(d.room) == norm_room or norm_room in _normalize_text(d.room)]

    if not all_devices:
        return _tool_result(
            "not_found",
            message=f"Không có thiết bị nào để phân tích điện năng{' trong ' + room if room else ''}.",
        )

    device_stats: list[dict[str, Any]] = []
    total_instant_watts = 0.0
    active_count = 0

    for dev in all_devices:
        watts = _estimate_device_watts(dev)
        total_instant_watts += watts
        is_active = watts > 2.0
        if is_active:
            active_count += 1
            device_stats.append({
                "id": dev.id,
                "name": dev.name,
                "room": dev.room,
                "kind": dev.kind,
                "active_watts": round(watts, 1),
            })

    # Sort biggest consumers first
    device_stats.sort(key=lambda x: x["active_watts"], reverse=True)

    # Timeframe projections
    daily_kwh = round((total_instant_watts * 8.0) / 1000.0, 2)  # Avg 8 active equivalent operating hours
    monthly_kwh = round(daily_kwh * 30.0, 1)

    cost_daily_vnd = round(daily_kwh * _AVG_ELECTRICITY_PRICE_VND_PER_KWH)
    cost_monthly_vnd = round(monthly_kwh * _AVG_ELECTRICITY_PRICE_VND_PER_KWH)

    # Energy savings recommendations
    tips: list[str] = []
    aircons = [d for d in device_stats if d["kind"] in {"aircon", "fan"} and d["active_watts"] >= 800]
    if aircons:
        tips.append("❄️ Điều hòa đang là thiết bị ngốn điện nhất: Đặt nhiệt độ ở mức 26°C kết hợp bật quạt gió sẽ tiết kiệm khoảng 15-20% điện năng.")

    high_lights = [d for d in device_stats if d["kind"] == "light"]
    if len(high_lights) >= 3:
        tips.append(f"💡 Hiện có {len(high_lights)} bóng đèn đang bật cùng lúc: Hãy tắt bớt đèn ở những phòng không có người để tránh lãng phí.")

    if not tips:
        tips.append("🌱 Ngôi nhà đang hoạt động ở mức tiết kiệm năng lượng rất tốt!")

    summary_msg = (
        f"Công suất tiêu thụ tức thời hiện tại: {round(total_instant_watts, 1)} W ({round(total_instant_watts/1000, 2)} kW) "
        f"với {active_count} thiết bị đang hoạt động. "
        f"Ước tính tiêu thụ hôm nay: {daily_kwh} kWh (~{cost_daily_vnd:,} VNĐ), cả tháng: {monthly_kwh} kWh (~{cost_monthly_vnd:,} VNĐ). "
        + " ".join(tips)
    )

    return _tool_result(
        "success",
        period=period,
        room=room or "Toàn bộ ngôi nhà",
        total_instant_watts=round(total_instant_watts, 1),
        active_devices_count=active_count,
        daily_kwh=daily_kwh,
        daily_cost_vnd=cost_daily_vnd,
        monthly_kwh=monthly_kwh,
        monthly_cost_vnd=cost_monthly_vnd,
        top_consumers=device_stats[:5],
        tips=tips,
        message=summary_msg,
    )
