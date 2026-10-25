"""LangChain tool for EVN electricity tariff calculation, AC BTU sizing, and unit conversions."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result

logger = logging.getLogger(__name__)

# Biểu giá điện sinh hoạt 6 bậc EVN hiện hành (áp dụng mới nhất)
# Đơn vị: Đồng/kWh (chưa bao gồm VAT 8%)
EVN_TIERS = [
    {"tier": 1, "name": "Bậc 1 (0 - 50 kWh)", "max_kwh": 50, "price": 1893},
    {"tier": 2, "name": "Bậc 2 (51 - 100 kWh)", "max_kwh": 50, "price": 1956},
    {"tier": 3, "name": "Bậc 3 (101 - 200 kWh)", "max_kwh": 100, "price": 2271},
    {"tier": 4, "name": "Bậc 4 (201 - 300 kWh)", "max_kwh": 100, "price": 2860},
    {"tier": 5, "name": "Bậc 5 (301 - 400 kWh)", "max_kwh": 100, "price": 3197},
    {"tier": 6, "name": "Bậc 6 (Từ 401 kWh trở lên)", "max_kwh": float("inf"), "price": 3302},
]


def calculate_evn_bill(kwh: float) -> dict[str, Any]:
    """Calculate residential electricity bill with 6-tier EVN tariffs and 8% VAT."""
    if kwh <= 0:
        return {"kwh": 0, "subtotal": 0, "vat": 0, "total": 0, "tiers": []}

    remaining = kwh
    tier_details = []
    subtotal = 0.0

    for t in EVN_TIERS:
        if remaining <= 0:
            break
        used = min(remaining, t["max_kwh"])
        cost = used * t["price"]
        subtotal += cost
        tier_details.append({
            "tier": t["tier"],
            "name": t["name"],
            "kwh": used,
            "unit_price": t["price"],
            "cost": cost,
        })
        remaining -= used

    vat = subtotal * 0.08
    total = subtotal + vat

    return {
        "kwh": kwh,
        "subtotal": round(subtotal),
        "vat": round(vat),
        "total": round(total),
        "tier_details": tier_details,
    }


def calculate_ac_btu(area_m2: float, has_sun_exposure: bool = False) -> dict[str, Any]:
    """Recommend air conditioner BTU capacity based on room area in m2."""
    base_btu_per_m2 = 700 if has_sun_exposure else 600
    estimated_btu = area_m2 * base_btu_per_m2

    if estimated_btu <= 9500:
        recommended_btu = 9000
        hp = "1.0 HP (1 Ngựa)"
        notes = "Phù hợp cho phòng ngủ nhỏ, phòng làm việc cá nhân dưới 15 m²."
    elif estimated_btu <= 13000:
        recommended_btu = 12000
        hp = "1.5 HP (1.5 Ngựa)"
        notes = "Phù hợp cho phòng ngủ tiêu chuẩn hoặc phòng khách nhỏ 15 - 20 m²."
    elif estimated_btu <= 19000:
        recommended_btu = 18000
        hp = "2.0 HP (2 Ngựa)"
        notes = "Phù hợp cho phòng khách gia đình hoặc phòng sinh hoạt chung 20 - 30 m²."
    elif estimated_btu <= 26000:
        recommended_btu = 24000
        hp = "2.5 HP (2.5 Ngựa)"
        notes = "Phù hợp cho phòng rộng thông tầng hoặc không gian mở 30 - 40 m²."
    else:
        recommended_btu = int(estimated_btu)
        hp = f"~{estimated_btu / 9000:.1f} HP"
        notes = "Phòng diện tích lớn trên 40 m², khuyến nghị lắp 2 máy lạnh phân bổ đều hoặc máy công suất thương mại."

    return {
        "area_m2": area_m2,
        "recommended_btu": recommended_btu,
        "horsepower": hp,
        "notes": notes,
    }


class SmartCalculatorInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    calc_type: Literal["electricity_bill_evn", "ac_btu_recommendation", "temperature_converter", "math"] = Field(
        default="electricity_bill_evn",
        description="Loại tính toán: 'electricity_bill_evn' (tiền điện EVN 6 bậc), 'ac_btu_recommendation' (chọn công suất máy lạnh theo diện tích), 'temperature_converter' (đổi C sang F hoặc ngược lại), 'math' (tính toán số học).",
    )
    action: str | None = Field(default=None, description="Tên tương đương cho calc_type: 'evn_electricity', 'ac_btu', 'temp_convert'.")
    kwh: float | None = Field(default=None, description="Số điện tiêu thụ trong tháng (kWh) để tính tiền điện.")
    room_area_m2: float | None = Field(default=None, description="Diện tích phòng tính bằng mét vuông (m²).")
    area_sqm: float | None = Field(default=None, description="Alias cho room_area_m2.")
    temp_value: float | None = Field(default=None, description="Giá trị nhiệt độ cần đổi.")
    temp_unit: Literal["c_to_f", "f_to_c"] = Field(default="c_to_f", description="Chiều đổi: 'c_to_f' (C sang F) hoặc 'f_to_c' (F sang C).")
    expression: str | None = Field(default=None, description="Biểu thức toán học cần tính (ví dụ: '150 * 2500', '2500000 * 0.15').")


@tool(args_schema=SmartCalculatorInput)
def smart_unit_and_cost_calculator(
    calc_type: Literal["electricity_bill_evn", "ac_btu_recommendation", "temperature_converter", "math"] = "electricity_bill_evn",
    action: str | None = None,
    kwh: float | None = None,
    room_area_m2: float | None = None,
    area_sqm: float | None = None,
    temp_value: float | None = None,
    temp_unit: Literal["c_to_f", "f_to_c"] = "c_to_f",
    expression: str | None = None,
) -> str:
    """Công cụ tính toán chuyên gia nhà thông minh: tính tiền điện sinh hoạt 6 bậc EVN có thuế VAT, tư vấn chọn công suất BTU điều hòa theo diện tích phòng, và quy đổi nhiệt độ."""
    # Normalize aliases
    if action:
        if action in ("evn_electricity", "electricity_bill_evn"):
            calc_type = "electricity_bill_evn"
        elif action in ("ac_btu", "ac_btu_recommendation"):
            calc_type = "ac_btu_recommendation"
        elif action in ("temp_convert", "temperature_converter"):
            calc_type = "temperature_converter"

    if room_area_m2 is None and area_sqm is not None:
        room_area_m2 = area_sqm
    # 1. Tính tiền điện EVN
    if calc_type == "electricity_bill_evn" or (kwh is not None and kwh > 0):
        val = kwh if kwh is not None and kwh > 0 else 100.0
        bill = calculate_evn_bill(val)

        lines = [
            f"⚡ **Bảng tính tiền điện sinh hoạt EVN 6 bậc (Sản lượng: {val:g} kWh):**",
        ]
        for t in bill["tier_details"]:
            lines.append(f"- {t['name']}: {t['kwh']:g} kWh × {t['unit_price']:,} đ = **{t['cost']:,.0f} đ**")

        lines.append(f"\n- Tiền điện trước thuế: **{bill['subtotal']:,} đ**")
        lines.append(f"- Thuế GTGT (VAT 8%): **{bill['vat']:,} đ**")
        lines.append(f"➔ **TỔNG TIỀN PHẢI THANH TOÁN: {bill['total']:,} đ**")

        if val > 300:
            lines.append("\n💡 *Mẹo tiết kiệm điện: Lượng điện tiêu thụ đã chạm Bậc 5-6 (giá trên 3.100 đ/kWh). Bạn nên cài điều hòa ở 26°C kèm quạt phe phẩy để giảm 15-20% hóa đơn.*")

        msg = "\n".join(lines)
        return _tool_result("success", calc_type="electricity_bill_evn", result=bill, message=msg)

    # 2. Tư vấn công suất điều hòa BTU theo diện tích
    if calc_type == "ac_btu_recommendation" or (room_area_m2 is not None and room_area_m2 > 0):
        area = room_area_m2 if room_area_m2 is not None and room_area_m2 > 0 else 20.0
        btu_res = calculate_ac_btu(area)

        msg = (
            f"❄️ **Tư vấn chọn điều hòa cho phòng {area:g} m²:**\n"
            f"- Công suất khuyến nghị tối ưu: **{btu_res['recommended_btu']:,} BTU** ({btu_res['horsepower']}).\n"
            f"- Đặc điểm: {btu_res['notes']}\n"
            f"- Khuyến nghị: Bạn nên chọn dòng máy lạnh **Inverter** tiết kiệm điện và lắp đặt dàn lạnh tránh thổi trực tiếp vào đầu giường ngủ để bảo vệ đường hô hấp."
        )
        return _tool_result("success", calc_type="ac_btu_recommendation", result=btu_res, message=msg)

    # 3. Quy đổi nhiệt độ
    if calc_type == "temperature_converter" or temp_value is not None:
        t = temp_value if temp_value is not None else 30.0
        if temp_unit == "c_to_f":
            f_val = (t * 9 / 5) + 32
            msg = f"🌡️ **{t:g}°C** tương đương với **{f_val:.1f}°F**."
            return _tool_result("success", calc_type="temperature_converter", c=t, f=f_val, message=msg)
        else:
            c_val = (t - 32) * 5 / 9
            msg = f"🌡️ **{t:g}°F** tương đương với **{c_val:.1f}°C**."
            return _tool_result("success", calc_type="temperature_converter", f=t, c=c_val, message=msg)

    # 4. Tính toán số học an toàn
    if expression:
        clean_exp = re.sub(r"[^0-9+\-*/().% ]", "", expression)
        try:
            # Safe evaluation of basic mathematical arithmetic
            ans = eval(clean_exp, {"__builtins__": None}, {})
            msg = f"🔢 Kết quả tính toán: `{clean_exp}` = **{ans:g}**."
            return _tool_result("success", calc_type="math", expression=clean_exp, answer=ans, message=msg)
        except Exception:
            return _tool_result("error", message=f"Không thể tính biểu thức toán học: '{expression}'.")

    return _tool_result("invalid_request", message="Vui lòng cung cấp tham số tính toán hợp lệ (kWh, diện tích phòng m², hoặc nhiệt độ).")
