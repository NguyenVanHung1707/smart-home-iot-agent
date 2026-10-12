"""Xiaozhi AI Service for the physical ESP32 hardware smart home flow.

Handles voice/text interactions when dataMode is 'real', ensuring full isolation
from the local simulation sandbox. Communicates with real ESP32 devices via MQTT
and announces actions on the Xiaozhi Master Gateway speaker.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

import src.services.devices as devices_mod
from src.config import get_settings
from src.services.conversation import conversations
from src.services.device_control import control_device
from src.services.mqtt import get_mqtt_hub
from src.services.natural_language_control import (
    _contains,
    _normalize,
    _room_topology_reply,
    parse_home_request,
)

logger = logging.getLogger(__name__)


class XiaozhiAIService:
    """AI Assistant representing the Xiaozhi AI Brain for physical ESP32 smart home hardware."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def process(
        self,
        query: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process user command or inquiry using Xiaozhi AI exclusively for real hardware."""
        conversation_id = session_id or str(uuid4())
        norm_query = _normalize(query)
        real_reg = devices_mod.get_registry("real")

        # 1. Check for real hardware room topology / device listing
        if topo_reply := _room_topology_reply(norm_query, mode="real"):
            conversations.add_turn(conversation_id, query, topo_reply)
            self._announce_on_speaker(topo_reply)
            return {
                "transcript": query,
                "response": topo_reply,
                "analysis": "xiaozhi_room_topology",
                "metadata": {
                    "commands": [],
                    "ai_engine": "xiaozhi_ai",
                    "mode": "real",
                },
                "session_id": conversation_id,
            }

        # 2. Check for real hardware sensor / state inquiries
        inquiry_reply = self._handle_real_inquiry(norm_query, real_reg)
        if inquiry_reply:
            conversations.add_turn(conversation_id, query, inquiry_reply)
            self._announce_on_speaker(inquiry_reply)
            return {
                "transcript": query,
                "response": inquiry_reply,
                "analysis": "xiaozhi_sensor_inquiry",
                "metadata": {
                    "commands": [],
                    "ai_engine": "xiaozhi_ai",
                    "mode": "real",
                },
                "session_id": conversation_id,
            }

        # 2. Parse smart home control intent for REAL physical devices
        plan = parse_home_request(query, mode="real")
        executed_commands = []
        feedback_parts = []

        if plan.handled and plan.commands:
            for cmd in plan.commands:
                dev = real_reg.get(cmd.device_id)
                if not dev:
                    continue
                controlled_dev, err = control_device(
                    cmd.device_id,
                    cmd.action,
                    cmd.value,
                    mode="real",
                )
                if err:
                    feedback_parts.append(f"Không thể điều khiển {dev.name} ({err}).")
                else:
                    action_label = {
                        "on": "đã bật",
                        "off": "đã tắt",
                        "toggle": "đã chuyển trạng thái",
                        "unlock": "đã mở khóa",
                        "lock": "đã khóa an toàn",
                        "open": "đã mở",
                        "close": "đã đóng",
                    }.get(cmd.action, f"đã thực hiện {cmd.action}")
                    feedback_parts.append(f"Xiaozhi {action_label} {dev.name}.")
                    executed_commands.append(
                        {
                            "device_id": cmd.device_id,
                            "action": cmd.action,
                            "value": cmd.value,
                            "device_name": dev.name,
                        }
                    )

        if executed_commands:
            response_text = " ".join(feedback_parts)
            self._announce_on_speaker(response_text)
            conversations.add_turn(conversation_id, query, response_text)
            return {
                "transcript": query,
                "response": response_text,
                "analysis": "xiaozhi_device_control",
                "metadata": {
                    "commands": executed_commands,
                    "ai_engine": "xiaozhi_ai",
                    "mode": "real",
                },
                "session_id": conversation_id,
            }

        # 3. Conversational / Q&A with Xiaozhi persona
        conversational_reply = self._generate_xiaozhi_reply(query, norm_query, real_reg)
        conversations.add_turn(conversation_id, query, conversational_reply)
        self._announce_on_speaker(conversational_reply)
        return {
            "transcript": query,
            "response": conversational_reply,
            "analysis": "xiaozhi_conversation",
            "metadata": {
                "commands": [],
                "ai_engine": "xiaozhi_ai",
                "mode": "real",
            },
            "session_id": conversation_id,
        }

    def _handle_real_inquiry(self, norm_text: str, reg: Any) -> str | None:
        """Answer queries about physical sensors and device states in the house."""
        # Temperature & humidity
        if _contains(norm_text, "nhiet do", "do am", "nong", "lanh", "thoi tiet"):
            temp_dev = reg.get("living-temperature")
            if temp_dev and isinstance(temp_dev.state, dict):
                temp = temp_dev.state.get("temperature", "--")
                hum = temp_dev.state.get("humidity", "--")
                return f"Hiện tại nhiệt độ phòng khách là {temp}°C và độ ẩm là {hum}%."

        # Gas sensor
        if _contains(norm_text, "gas", "khi gas", "ro ri gas"):
            gas_dev = reg.get("kitchen-gas")
            if gas_dev and isinstance(gas_dev.state, dict):
                gas_val = gas_dev.state.get("gas", 0)
                status = "an toàn" if gas_val < 300 else "CẢNH BÁO: nồng độ gas bất thường!"
                return f"Cảm biến khí gas phòng bếp đang ở mức {gas_val} ppm ({status})."

        # Motion sensor
        if _contains(norm_text, "chuyen dong", "co ai", "nguoi"):
            pir = reg.get("living-motion")
            if pir and isinstance(pir.state, dict):
                motion = pir.state.get("motion", False)
                return (
                    "Cảm biến phòng khách hiện phát hiện có chuyển động."
                    if motion
                    else "Hiện tại không phát hiện chuyển động nào trong phòng khách."
                )

        # Entrance door lock
        if _contains(norm_text, "cua chinh", "khoa cua", "o khoa", "cua"):
            lock = reg.get("entry-lock")
            if lock and isinstance(lock.state, dict):
                is_locked = lock.state.get("locked", True)
                return "Khóa cửa chính hiện đang được khóa an toàn." if is_locked else "Cửa chính hiện đang mở."

        # Light sensor
        if _contains(norm_text, "anh sang", "do sang", "troi sang", "troi toi"):
            light_sens = reg.get("living-light-sensor")
            if light_sens and isinstance(light_sens.state, dict):
                lux = light_sens.state.get("lux", light_sens.state.get("illuminance", "--"))
                return f"Cường độ ánh sáng phòng khách hiện tại là {lux} lux."

        # Check which lights are ON
        if _contains(norm_text, "den nao dang bat", "kiem tra den", "trang thai den"):
            lights = [d for d in reg.list() if d.kind == "light"]
            on_lights = [d.name for d in lights if isinstance(d.state, dict) and d.state.get("power")]
            if on_lights:
                return f"Hiện có các đèn đang bật: {', '.join(on_lights)}."
            return "Hiện tại tất cả các đèn trong nhà đều đang tắt."

        return None

    def _generate_xiaozhi_reply(self, raw_query: str, norm_text: str, reg: Any) -> str:
        """Generate friendly conversational response in Xiaozhi AI persona."""
        if _contains(norm_text, "xin chao", "chao", "hello", "hi"):
            return (
                "Xin chào! Tôi là Trợ lý AI Xiaozhi, đang kết nối với hệ thống phần cứng ESP32. "
                "Tôi có thể giúp bạn kiểm tra cảm biến hoặc điều khiển các thiết bị trong nhà."
            )
        if _contains(norm_text, "ban la ai", "ten gi", "gioi thieu"):
            return (
                "Tôi là Trợ lý AI Xiaozhi cho luồng phần cứng thật, kết nối qua Master Gateway ESP32, "
                "sóng ESP-NOW và HiveMQ Cloud."
            )
        if _contains(norm_text, "cam on", "thanks", "thank you"):
            return "Rất sẵn lòng phục vụ bạn! Hãy gọi Xiaozhi bất cứ khi nào bạn cần."
        return (
            f"Trợ lý Xiaozhi đã ghi nhận: '{raw_query}'. "
            "Lệnh đã được điều phối tới hệ thống phần cứng ESP32."
        )

    def _announce_on_speaker(self, message: str) -> None:
        """Publish text to the Xiaozhi Gateway speaker via homing/speaker/say."""
        hub = get_mqtt_hub()
        if hub and hasattr(hub, "client") and hub.client is not None:
            try:
                prefix = self.settings.mqtt_topic_prefix.strip("/")
                hub.client.publish(f"{prefix}/speaker/say", message, qos=0)
            except Exception:
                logger.debug("Failed to publish to speaker/say", exc_info=True)


xiaozhi_service = XiaozhiAIService()
