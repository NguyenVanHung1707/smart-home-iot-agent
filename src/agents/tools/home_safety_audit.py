"""LangChain tool for comprehensive smart home safety and anomaly audit."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result
import src.services.devices as devices_mod

logger = logging.getLogger(__name__)


class AuditHomeSafetyInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    scope: str = Field(
        default="all",
        description="Phạm vi kiểm tra: 'all' (toàn nhà), 'security' (cửa và đột nhập), 'fire_gas' (cháy nổ và rò rỉ gas), 'electrical' (thiết bị điện bật quên).",
    )
    mode: str = Field(
        default="real",
        description="Chế độ dữ liệu: 'real' (thiết bị phần cứng ESP32) hoặc 'simulator'.",
    )


@tool(args_schema=AuditHomeSafetyInput)
def audit_home_safety(
    scope: str = "all",
    mode: str = "real",
) -> str:
    """Quét và chẩn đoán toàn diện an toàn ngôi nhà: rò rỉ khí gas, khóa cửa, nhiệt độ bất thường, thiết bị bật quên và tình trạng mạng ESP32."""
    reg = devices_mod.get_registry(mode)
    devices = reg.list()

    anomalies: list[dict[str, Any]] = []
    safety_score = 100
    checks_performed = []

    # 1. Khí gas phòng bếp (kitchen-gas)
    gas_dev = reg.get("kitchen-gas")
    gas_level = 0
    if gas_dev and isinstance(gas_dev.state, dict):
        gas_level = gas_dev.state.get("gas", gas_dev.state.get("gas_level", 0))
        checks_performed.append(f"Cảm biến khí gas ({gas_level} ppm)")
        if gas_level >= 300:
            severity = "CRITICAL" if gas_level >= 600 else "WARNING"
            points = 40 if severity == "CRITICAL" else 20
            safety_score -= points
            anomalies.append({
                "category": "Khí gas",
                "severity": severity,
                "device": gas_dev.name,
                "detail": f"Nồng độ khí gas cao bất thường: {gas_level} ppm.",
                "action": "Khóa van bình gas ngay lập tức, mở cửa thông gió, không bật công tắc điện!",
            })

    # 2. Khóa cửa chính (entry-lock)
    lock_dev = reg.get("entry-lock")
    if lock_dev and isinstance(lock_dev.state, dict):
        is_locked = lock_dev.state.get("locked", True)
        checks_performed.append("Khóa cửa chính")
        if not is_locked:
            safety_score -= 15
            anomalies.append({
                "category": "An ninh cửa",
                "severity": "WARNING",
                "device": lock_dev.name,
                "detail": "Cửa chính hiện đang mở khóa.",
                "action": "Nên khóa cửa lại nếu bạn đang đi vắng hoặc chuẩn bị đi ngủ.",
            })

    # 3. Nhiệt độ & Độ ẩm phòng khách (living-temperature)
    temp_dev = reg.get("living-temperature")
    if temp_dev and isinstance(temp_dev.state, dict):
        temp = float(temp_dev.state.get("temperature", 28.0))
        hum = float(temp_dev.state.get("humidity", 65.0))
        checks_performed.append(f"Khí hậu trong nhà ({temp}°C, {hum}%)")
        if temp >= 38.0:
            safety_score -= 30
            anomalies.append({
                "category": "Nhiệt độ quá cao",
                "severity": "WARNING",
                "device": temp_dev.name,
                "detail": f"Nhiệt độ trong nhà lên tới {temp}°C (nguy cơ sốc nhiệt hoặc hỏa hoạn).",
                "action": "Bật quạt/điều hòa làm mát hoặc kiểm tra nguồn nhiệt gần cảm biến.",
            })
        if hum >= 85.0:
            safety_score -= 10
            anomalies.append({
                "category": "Độ ẩm cao",
                "severity": "NOTICE",
                "device": temp_dev.name,
                "detail": f"Độ ẩm không khí đạt {hum}% (nguy cơ nồm ẩm, nấm mốc).",
                "action": "Bật điều hòa chế độ Dry (hút ẩm) hoặc đóng kín cửa.",
            })

    # 4. Thiết bị điện bật quên (quạt, đèn khi không có chuyển động)
    active_lights = [d for d in devices if d.kind == "light" and isinstance(d.state, dict) and d.state.get("power")]
    active_fans = [d for d in devices if d.kind == "fan" and isinstance(d.state, dict) and d.state.get("power")]
    checks_performed.append(f"Thiết bị điện ({len(active_lights)} đèn, {len(active_fans)} quạt đang bật)")

    # 5. Kiểm tra kết nối mạng của các vi điều khiển ESP32
    offline_devs = [d for d in devices if not d.online]
    checks_performed.append(f"Kết nối ESP32 ({len(devices) - len(offline_devs)}/{len(devices)} trực tuyến)")
    if offline_devs:
        safety_score -= min(15, len(offline_devs) * 5)
        anomalies.append({
            "category": "Mất kết nối",
            "severity": "NOTICE",
            "device": ", ".join(d.name for d in offline_devs),
            "detail": f"Có {len(offline_devs)} thiết bị ngoại tuyến hoặc mất tín hiệu WiFi/MQTT.",
            "action": "Kiểm tra nguồn cấp adapter 5V và sóng WiFi của bo mạch ESP32.",
        })

    safety_score = max(0, min(100, safety_score))

    if safety_score >= 90:
        verdict = "AN TOÀN TUYỆT ĐỐI"
        verdict_icon = "🟢"
    elif safety_score >= 70:
        verdict = "CẦN LƯU Ý"
        verdict_icon = "🟡"
    else:
        verdict = "CẢNH BÁO NGUY HIỂM"
        verdict_icon = "🔴"

    # Xây dựng phản hồi báo cáo súc tích
    report_lines = [
        f"{verdict_icon} **Báo cáo an toàn ngôi nhà: {verdict} ({safety_score}/100 điểm)**",
        f"- Cảm biến khí gas: {gas_level} ppm ({'An toàn' if gas_level < 150 else 'Có mùi gas'})",
        f"- Khóa cửa chính: {'Đang khóa an toàn' if lock_dev and lock_dev.state.get('locked', True) else 'ĐANG MỞ KHÓA'}",
        f"- Thiết bị đang hoạt động: {len(active_lights)} đèn, {len(active_fans)} quạt.",
    ]

    if anomalies:
        report_lines.append("\n⚠️ **Vấn đề cần xử lý:**")
        for idx, a in enumerate(anomalies, 1):
            report_lines.append(f"{idx}. [{a['severity']}] {a['detail']} ➔ Khuyến nghị: {a['action']}")
    else:
        report_lines.append("Toàn bộ các thông số an ninh, cháy nổ và điện năng đều trong trạng thái tối ưu.")

    summary_msg = "\n".join(report_lines)

    return _tool_result(
        "success",
        safety_score=safety_score,
        verdict=verdict,
        anomalies_count=len(anomalies),
        anomalies=anomalies,
        checks=checks_performed,
        message=summary_msg,
    )
