"""LangChain tool for reading smart sensor data."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _get_registry,
    _normalize_text,
    _StrictToolInput,
    _tool_result,
)
from src.services.devices import sensor_reading, sensor_readings


class GetSensorDataInput(_StrictToolInput):
    room: str | None = Field(
        default=None,
        description="Tên phòng cần đọc dữ liệu cảm biến (ví dụ: 'Phòng khách', 'Phòng bếp'). Để null để đọc tất cả.",
    )
    sensor_type: Literal["temperature", "humidity", "gas", "motion", "light"] | None = Field(
        default=None,
        description="Loại dữ liệu cảm biến cụ thể cần đọc",
    )
    device_id: str | None = Field(
        default=None,
        description="Tùy chọn: ID chính xác của cảm biến",
    )


def _evaluate_sensor_health(readings: dict[str, dict]) -> dict[str, str]:
    """Helper to evaluate comfort index and hazard thresholds from sensor state."""
    evaluations: dict[str, str] = {}
    temp = readings.get("temperature", {}).get("value")
    if isinstance(temp, (int, float)):
        if temp >= 50.0:
            evaluations["temperature_status"] = "Nguy hiểm: Nhiệt độ quá cao (nguy cơ cháy)"
        elif temp >= 32.0:
            evaluations["temperature_status"] = "Nóng, nên bật quạt/điều hòa"
        elif temp >= 24.0:
            evaluations["temperature_status"] = "Dễ chịu, thoải mái"
        elif temp >= 18.0:
            evaluations["temperature_status"] = "Mát mẻ"
        else:
            evaluations["temperature_status"] = "Lạnh"

    hum = readings.get("humidity", {}).get("value")
    if isinstance(hum, (int, float)):
        if hum >= 75:
            evaluations["humidity_status"] = "Độ ẩm cao, nồm ẩm"
        elif hum >= 40:
            evaluations["humidity_status"] = "Độ ẩm lý tưởng"
        else:
            evaluations["humidity_status"] = "Khô hanh"

    gas_reading = readings.get("gas")
    gas = gas_reading.get("value") if gas_reading else None
    if isinstance(gas, (int, float)):
        if gas_reading and gas_reading.get("alarm") is True:
            evaluations["gas_status"] = "NGUY HIỂM: Rò rỉ khí gas vượt ngưỡng an toàn!"
        elif gas >= 150:
            evaluations["gas_status"] = "Cảnh báo: Nồng độ khí gas cao hơn bình thường"
        else:
            evaluations["gas_status"] = "An toàn"

    motion = readings.get("motion", {}).get("value")
    if motion is not None:
        evaluations["motion_status"] = "Có chuyển động" if motion else "Không có chuyển động"

    return evaluations


@tool(args_schema=GetSensorDataInput)
def get_sensor_data(
    room: str | None = None,
    sensor_type: Literal["temperature", "humidity", "gas", "motion", "light"] | None = None,
    device_id: str | None = None,
) -> str:
    """Đọc dữ liệu từ các cảm biến môi trường, an ninh và chuyển động trong nhà kèm đánh giá mức độ an toàn."""
    active_registry = _get_registry()
    devices = [d for d in active_registry.list() if d.kind == "sensor"]
    if device_id:
        devices = [d for d in devices if d.id == device_id]
    elif room:
        norm_room = _normalize_text(room)
        devices = [d for d in devices if _normalize_text(d.room) == norm_room or norm_room in _normalize_text(d.room)]

    if not devices:
        room_desc = f" trong '{room}'" if room else ""
        return _tool_result("not_found", message=f"Không tìm thấy cảm biến nào{room_desc}.")

    results = []
    for dev in devices:
        state = dev.state or {}
        readings = sensor_readings(dev)
        analysis = _evaluate_sensor_health(readings)
        sensor_item = {
            "id": dev.id,
            "name": dev.name,
            "room": dev.room,
            "online": dev.online,
            "state": state,
            "assessment": analysis,
        }
        if sensor_type and (reading := sensor_reading(dev, sensor_type)) is not None:
            sensor_item["requested_value"] = reading["value"]

        results.append(sensor_item)

    return _tool_result("success", count=len(results), sensors=results)
