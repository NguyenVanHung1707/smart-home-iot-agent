"""LangChain tool for comprehensive home security and hazard inspection."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import (
    _get_registry,
    _StrictToolInput,
    _tool_result,
)
from src.services.devices import sensor_reading


class GetSecurityReportInput(_StrictToolInput):
    include_sensors: bool = Field(
        default=True,
        description="Kiểm tra dữ liệu các cảm biến an ninh (gas, khói, nhiệt độ cao, chuyển động)",
    )
    include_locks: bool = Field(
        default=True,
        description="Kiểm tra trạng thái các khóa cửa trong nhà",
    )


@tool(args_schema=GetSecurityReportInput)
def get_security_report(
    include_sensors: bool = True,
    include_locks: bool = True,
) -> str:
    """Báo cáo tổng hợp tình trạng an ninh, các cảnh báo nguy hiểm (rò rỉ gas, cửa chưa khóa, nhiệt độ bất thường, thiết bị mất kết nối)."""
    active_registry = _get_registry()
    devices = active_registry.list()

    alerts: list[str] = []
    warnings: list[str] = []
    lock_statuses: list[dict] = []
    sensor_statuses: list[dict] = []

    # 1. Check Door Locks
    if include_locks:
        locks = [d for d in devices if d.kind == "lock"]
        for lock in locks:
            is_locked = lock.state.get("locked", False)
            lock_statuses.append(
                {
                    "id": lock.id,
                    "name": lock.name,
                    "room": lock.room,
                    "locked": is_locked,
                    "online": lock.online,
                }
            )
            if not is_locked:
                warnings.append(f"Khóa '{lock.name}' tại '{lock.room}' đang MỞ.")
            if not lock.online:
                warnings.append(f"Khóa '{lock.name}' đang NGOẠI TUYẾN.")

    # 2. Check Environmental & Security Sensors
    if include_sensors:
        sensors = [d for d in devices if d.kind == "sensor"]
        for sensor in sensors:
            state = sensor.state or {}
            online = sensor.online

            gas = sensor_reading(sensor, "gas")
            temp = sensor_reading(sensor, "temperature")
            motion = sensor_reading(sensor, "motion")

            sensor_info = {
                "id": sensor.id,
                "name": sensor.name,
                "room": sensor.room,
                "online": online,
                "state": state,
            }
            sensor_statuses.append(sensor_info)

            if not online:
                warnings.append(f"Cảm biến '{sensor.name}' tại '{sensor.room}' đang ngoại tuyến.")
                continue

            # Gas leak detection
            if gas and isinstance(gas["value"], (int, float)):
                if gas["alarm"] is True:
                    alerts.append(f"CẢNH BÁO NGUY HIỂM: Phát hiện rò rỉ khí Gas tại '{sensor.room}' (Mức: {gas['value']} {gas['unit'] or ''})!")
                elif gas["value"] >= 150:
                    warnings.append(f"Nồng độ khí gas tại '{sensor.room}' cao hơn bình thường ({gas['value']} {gas['unit'] or ''}).")

            # High temperature / Fire risk
            if temp and isinstance(temp["value"], (int, float)) and temp["value"] >= 50.0:
                alerts.append(f"CẢNH BÁO CHÁY/NHIỆT ĐỘ CAO: Nhiệt độ tại '{sensor.room}' đạt {temp['value']}°C!")

            # Unexpected motion
            if motion and motion["value"] is True:
                sensor_info["motion_alert"] = True

    # 3. Overall Level
    if alerts:
        overall_status: Literal["ALERT", "WARNING", "SECURE"] = "ALERT"
        summary_msg = f"PHÁT HIỆN {len(alerts)} NGUY CƠ AN NINH NGUY HIỂM! Cần xử lý ngay."
    elif warnings:
        overall_status = "WARNING"
        summary_msg = f"Hệ thống an ninh ghi nhận {len(warnings)} vấn đề cần lưu ý."
    else:
        overall_status = "SECURE"
        summary_msg = "Tất cả cửa đã khóa an toàn, các cảm biến môi trường hoạt động bình thường."

    return _tool_result(
        "success",
        overall_status=overall_status,
        summary=summary_msg,
        alerts=alerts,
        warnings=warnings,
        locks=lock_statuses,
        sensors=sensor_statuses,
    )
