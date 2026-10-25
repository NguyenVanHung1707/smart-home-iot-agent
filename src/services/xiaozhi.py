"""Xiaozhi AI Service for the physical ESP32 hardware smart home flow.

Handles voice/text interactions when dataMode is 'real', ensuring full isolation
from the local simulation sandbox. Communicates with real ESP32 devices via MQTT
and announces actions on the Xiaozhi Master Gateway speaker.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

import src.services.devices as devices_mod
from src.agents.tools.air_quality_advisor import evaluate_air_quality
from src.agents.tools.energy_analytics import get_energy_analytics
from src.agents.tools.home_notes import add_family_note, get_family_notes
from src.agents.tools.home_safety_audit import audit_home_safety
from src.agents.tools.internet_search import search_internet
from src.agents.tools.media_player import play_youtube_music
from src.agents.tools.shopping_list import manage_shopping_list
from src.agents.tools.sleep_optimizer import optimize_sleep_environment
from src.agents.tools.smart_calc_converter import smart_unit_and_cost_calculator
from src.agents.tools.weather_forecast import get_weather_forecast
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

        # 0. Comprehensive Input Guardrails (Prompt Injection, Toxicity, Secret Exfiltration, Threats)
        from src.services.guardrails import guardrails
        input_guard = guardrails.inspect_input(query)
        if not input_guard.passed:
            reply = input_guard.suggested_response or "Yêu cầu bị từ chối bởi rào chắn an toàn của ngôi nhà."
            self._announce_on_speaker(reply)
            conversations.add_turn(conversation_id, query, reply)
            return {
                "transcript": query,
                "response": reply,
                "analysis": "guardrail_blocked",
                "metadata": {
                    "violation": input_guard.violation_type,
                    "reason": input_guard.reason,
                    "risk_level": input_guard.risk_level,
                    "ai_engine": "xiaozhi_ai",
                    "mode": "real",
                },
                "session_id": conversation_id,
            }

        # 0.1 Strict Door Security: All door unlock requests via AI are strictly rejected
        if _contains(norm_query, "mo cua", "mo khoa", "unlock") and not _contains(norm_query, "khoa cua", "dong cua"):
            deny_text = "Vì lý do an ninh, tôi không thể mở cửa. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ RFID."
            self._announce_on_speaker(deny_text)
            conversations.add_turn(conversation_id, query, deny_text)
            return {
                "transcript": query,
                "response": deny_text,
                "analysis": "xiaozhi_door_unlock_denied",
                "metadata": {
                    "commands": [],
                    "ai_engine": "xiaozhi_ai",
                    "mode": "real",
                },
                "session_id": conversation_id,
            }

        # 1. Parse smart home control intent for REAL physical devices first
        # Commands like "Bật đèn...", "Tắt quạt...", "Khóa cửa..."
        plan = parse_home_request(query, mode="real")
        executed_commands = []
        feedback_parts = []

        if plan.handled and plan.commands:
            for cmd in plan.commands:
                dev = real_reg.get(cmd.device_id)
                if not dev:
                    continue

                # Device Safety Guardrail (Anti-Flapping relay shield, door lock, parameter bounds)
                dev_guard = guardrails.inspect_device_command(cmd.device_id, cmd.action, cmd.value)
                if not dev_guard.passed:
                    feedback_parts.append(dev_guard.suggested_response or f"Lệnh bị chặn ({dev_guard.reason}).")
                    continue

                if cmd.action in {"unlock", "open"} and dev.kind in {"lock", "security"}:
                    feedback_parts.append("Vì lý do an ninh, tôi không thể mở cửa. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ RFID.")
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

        # 2. Check for real hardware sensor / state inquiries (local room sensors)
        # E.g. "Kiểm tra nhiệt độ phòng khách", "Khí gas có an toàn không?", "Cửa chính đóng hay mở?"
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

        # 3. Check for room topology / device listing (when asking specifically about rooms / devices)
        is_topology_query = _contains(
            norm_query,
            "bao nhieu phong",
            "nhung phong nao",
            "co phong nao",
            "danh sach phong",
            "co may phong",
            "co bao nhieu thiet bi",
            "danh sach thiet bi",
            "thiet bi nao dang bat",
            "phong khach co nhung thiet bi",
            "phong ngu co nhung thiet bi",
            "bep co nhung thiet bi",
        )
        if is_topology_query:
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

        # 4. Check for YouTube / Media playback
        if _contains(norm_query, "phat nhac", "mo nhac", "bat nhac", "nghe nhac", "youtube", "bai hat", "ca si", "album"):
            try:
                media_res = play_youtube_music.invoke({"query": query})
                res_data = json.loads(media_res) if isinstance(media_res, str) else media_res
                msg = res_data.get("message") or f"Đang phát nhạc trên loa thông minh: {query}"
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_media_playback",
                    "metadata": {
                        "commands": [{"device_id": "hub-speaker", "action": "play", "value": 1}],
                        "track": res_data.get("track"),
                        "url": res_data.get("url"),
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Media playback error: {e}")

        # 5. Check for Outdoor Weather Forecast & Climate Recommendations
        is_outside_weather = _contains(norm_query, "thoi tiet", "du bao", "ngoai troi", "troi mua", "co mua khong", "nang nong") and not _contains(norm_query, "phong", "trong nha")
        if is_outside_weather:
            try:
                target_city = "Hà Nội"
                if _contains(norm_query, "ho chi minh", "hcm", "sai gon"):
                    target_city = "TP. Hồ Chí Minh"
                elif _contains(norm_query, "da nang"):
                    target_city = "Đà Nẵng"
                elif _contains(norm_query, "hai phong"):
                    target_city = "Hải Phòng"

                weather_res = get_weather_forecast.invoke({"location": target_city, "days": 1})
                res_data = json.loads(weather_res) if isinstance(weather_res, str) else weather_res
                msg = res_data.get("message") or f"Thời tiết tại {target_city} hôm nay tương đối ổn định."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_weather_forecast",
                    "metadata": {
                        "commands": [],
                        "weather_data": res_data.get("current"),
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Weather tool error: {e}")

        # 5.5. Check for EVN Electricity Tariff or AC BTU Sizing Calculation (Smart Calculator)
        is_smart_calc_query = _contains(
            norm_query,
            "tinh tien dien",
            "bieu gia dien",
            "tien dien evn",
            "theo evn",
            "evn",
            "may lanh bao nhieu btu",
            "dieu hoa bao nhieu btu",
            "bao nhieu btu",
            "can lap may lanh",
            "quy doi nhiet do",
        ) or (_contains(norm_query, "btu") and _contains(norm_query, "may lanh", "dieu hoa", "met vuong", "m2"))
        if is_smart_calc_query:
            try:
                import re
                calc_type = "electricity_bill_evn"
                kwh_val = None
                area_val = None

                kwh_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kwh|so dien|so|ki|ky)", norm_query)
                if kwh_match:
                    kwh_val = float(kwh_match.group(1).replace(",", "."))
                    calc_type = "electricity_bill_evn"

                area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m2|met vuong|m vuong)", norm_query)
                if area_match:
                    area_val = float(area_match.group(1).replace(",", "."))
                    calc_type = "ac_btu_recommendation"
                elif _contains(norm_query, "btu", "may lanh", "dieu hoa") and not kwh_val:
                    calc_type = "ac_btu_recommendation"

                res = smart_unit_and_cost_calculator.invoke({"calc_type": calc_type, "kwh": kwh_val, "room_area_m2": area_val})
                res_data = json.loads(res) if isinstance(res, str) else res
                msg = res_data.get("message") or "Đã thực hiện tính toán chuyên gia nhà thông minh."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_smart_calculator",
                    "metadata": {"commands": [], "calc_data": res_data, "ai_engine": "xiaozhi_ai", "mode": "real"},
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Smart calculator tool error: {e}")

        # 6. Check for Power Consumption, Electricity Bill & Eco-saving Advisor
        if _contains(norm_query, "dien nang", "tieu thu dien", "tien dien", "tiet kiem dien", "ngon dien", "kwh", "cong suat", "ton dien"):
            try:
                energy_res = get_energy_analytics.invoke({"period": "today"})
                res_data = json.loads(energy_res) if isinstance(energy_res, str) else energy_res
                msg = res_data.get("message") or "Đã phân tích mức tiêu thụ điện năng của các thiết bị."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_energy_analytics",
                    "metadata": {
                        "commands": [],
                        "energy_data": res_data,
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Energy analytics tool error: {e}")

        # 7. Check for Air Quality (IAQ) & Indoor Ventilation Diagnosis
        if _contains(norm_query, "chat luong khong khi", "khong khi trong nha", "iaq", "khong khi co sach", "bi bach", "thong gio", "nguy co nom", "nom am"):
            try:
                air_res = evaluate_air_quality.invoke({})
                res_data = json.loads(air_res) if isinstance(air_res, str) else air_res
                msg = res_data.get("message") or "Đã kiểm tra chất lượng không khí trong nhà."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_air_quality",
                    "metadata": {
                        "commands": [],
                        "iaq_data": res_data,
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Air quality tool error: {e}")

        # 8. Check for Household Notes & Reminders
        if _contains(norm_query, "luu ghi chu", "tao ghi chu", "them ghi chu", "nhac nho", "luu loi nhac", "ghi nho"):
            try:
                note_text = query
                for prefix in ["lưu ghi chú", "tạo ghi chú", "thêm ghi chú", "nhắc tôi", "nhắc nhở", "ghi nhớ"]:
                    if prefix in query.lower():
                        parts = query.lower().split(prefix, 1)
                        if len(parts) > 1 and parts[1].strip():
                            note_text = parts[1].strip().lstrip(":")
                            break
                note_res = add_family_note.invoke({"content": note_text})
                res_data = json.loads(note_res) if isinstance(note_res, str) else note_res
                msg = res_data.get("message") or f"Đã lưu ghi chú: '{note_text}'."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_add_family_note",
                    "metadata": {
                        "commands": [],
                        "note_data": res_data.get("note"),
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Add family note tool error: {e}")

        if _contains(norm_query, "xem ghi chu", "danh sach ghi chu", "co ghi chu gi", "doc ghi chu", "loi nhac"):
            try:
                notes_res = get_family_notes.invoke({})
                res_data = json.loads(notes_res) if isinstance(notes_res, str) else notes_res
                msg = res_data.get("message") or "Không có ghi chú nào."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_get_family_notes",
                    "metadata": {
                        "commands": [],
                        "notes_data": res_data.get("notes"),
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Get family notes tool error: {e}")

        # 9. Check for Internet search (news, gold price, gasoline price, search keyword, read newspaper)
        is_explicit_search = _contains(
            norm_query,
            "tim kiem",
            "tra cuu",
            "tin tuc",
            "gia vang",
            "gia xang",
            "google",
            "search",
            "doc bao",
            "bao chi",
            "thoi su",
            "tin nong",
            "tin moi",
        )
        if is_explicit_search:
            try:
                search_res = search_internet.invoke({"query": query})
                res_data = json.loads(search_res) if isinstance(search_res, str) else search_res
                summary = res_data.get("summary") or res_data.get("message") or "Không tìm thấy thông tin phù hợp."
                conversations.add_turn(conversation_id, query, summary)
                self._announce_on_speaker(summary)
                return {
                    "transcript": query,
                    "response": summary,
                    "analysis": "xiaozhi_internet_search",
                    "metadata": {
                        "commands": [],
                        "ai_engine": "xiaozhi_ai",
                        "mode": "real",
                    },
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Internet search error: {e}")

        # 10. Check for Home Safety & Anomaly Audit
        is_home_safety_query = _contains(
            norm_query,
            "an toan ngoi nha",
            "an toan nha",
            "kiem tra an toan",
            "nha co gi bat thuong",
            "bat thuong",
            "audit an toan",
            "chan doan nha",
            "kiem tra an ninh",
            "an ninh nha",
            "an toan toan dien",
        ) or (
            _contains(norm_query, "an toan", "an ninh")
            and _contains(norm_query, "nha", "ngoi nha", "hien tai", "khong")
            and not _contains(norm_query, "khi gas", "gas")
        )
        if is_home_safety_query:
            try:
                res = audit_home_safety.invoke({"scope": "all", "mode": "real"})
                res_data = json.loads(res) if isinstance(res, str) else res
                msg = res_data.get("message") or "Đã hoàn thành chẩn đoán an toàn ngôi nhà."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_home_safety_audit",
                    "metadata": {"commands": [], "safety_score": res_data.get("safety_score"), "ai_engine": "xiaozhi_ai", "mode": "real"},
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Safety audit tool error: {e}")

        # 11. Check for Bedtime / Sleep Comfort Mode
        if _contains(norm_query, "di ngu", "chuan bi ngu", "che do ngu", "ngu ngon", "toi uu phong ngu", "sap ngu", "chuan bi di ngu"):
            try:
                res = optimize_sleep_environment.invoke({"bedroom": "Phòng ngủ", "mode": "real"})
                res_data = json.loads(res) if isinstance(res, str) else res
                msg = res_data.get("message") or "Đã kích hoạt chế độ ngủ ngon."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_sleep_optimizer",
                    "metadata": {"commands": [{"device_id": "entry-lock", "action": "lock"}], "ai_engine": "xiaozhi_ai", "mode": "real"},
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Sleep optimizer tool error: {e}")

        # 12. Check for Shopping List
        if _contains(norm_query, "mua sam", "mua do", "di cho", "can mua gi", "do can mua", "danh sach mua"):
            try:
                act = "get"
                item_name = None
                qty = None
                if _contains(norm_query, "them", "can mua", "nho mua"):
                    act = "add"
                    item_name = query
                    for kw in ["thêm vào danh sách mua sắm", "thêm vào danh sách mua", "thêm", "nhớ mua", "cần mua"]:
                        if kw in query.lower():
                            parts = query.lower().split(kw, 1)
                            if len(parts) > 1 and parts[1].strip():
                                item_name = parts[1].strip(": ")
                                break
                elif _contains(norm_query, "da mua xong", "da mua", "xong mon"):
                    act = "mark_bought"
                    item_name = query
                    for kw in ["đã mua xong", "đã mua", "mua xong"]:
                        if kw in query.lower():
                            parts = query.lower().split(kw, 1)
                            if len(parts) > 1 and parts[1].strip():
                                item_name = parts[1].strip(": ")
                                break
                elif _contains(norm_query, "xoa mon", "bo mon", "xoa do"):
                    act = "delete"

                res = manage_shopping_list.invoke({"action": act, "item": item_name, "quantity": qty})
                res_data = json.loads(res) if isinstance(res, str) else res
                msg = res_data.get("message") or "Đã cập nhật danh sách mua sắm gia đình."
                conversations.add_turn(conversation_id, query, msg)
                self._announce_on_speaker(msg)
                return {
                    "transcript": query,
                    "response": msg,
                    "analysis": "xiaozhi_shopping_list",
                    "metadata": {"commands": [], "shopping_data": res_data, "ai_engine": "xiaozhi_ai", "mode": "real"},
                    "session_id": conversation_id,
                }
            except Exception as e:
                logger.warning(f"Shopping list tool error: {e}")

        # 3. Conversational / Q&A with Xiaozhi persona
        conversational_reply = self._generate_xiaozhi_reply(query, norm_query, real_reg)
        conversational_reply = guardrails.sanitize_output(conversational_reply)
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
        """Answer queries about physical sensors, date/time and device states in the house."""
        WEEKDAYS_VI = {
            0: "Thứ Hai",
            1: "Thứ Ba",
            2: "Thứ Tư",
            3: "Thứ Năm",
            4: "Thứ Sáu",
            5: "Thứ Bảy",
            6: "Chủ Nhật",
        }
        from datetime import datetime, timedelta
        now = datetime.now()
        weekday = WEEKDAYS_VI.get(now.weekday(), "")

        if _contains(norm_text, "ngay mai thu may", "mai thu may", "ngay mai la thu may", "mai la thu may"):
            tom = now + timedelta(days=1)
            tom_wd = WEEKDAYS_VI.get(tom.weekday(), "")
            return f"Ngày mai là {tom_wd}, ngày {tom.day} tháng {tom.month} năm {tom.year}."

        if _contains(norm_text, "thu may", "hom nay thu may", "hom nay la thu may", "nay la thu may"):
            return f"Hôm nay là {weekday}, ngày {now.day} tháng {now.month} năm {now.year}."

        if _contains(norm_text, "ngay may", "ngay bao nhieu", "hom nay ngay may", "hom nay ngay bao nhieu", "hom nay ngay gi"):
            return f"Hôm nay là {weekday}, ngày {now.day} tháng {now.month} năm {now.year}."

        if _contains(norm_text, "may gio", "may gio roi", "thoi gian"):
            return f"Bây giờ là {now.hour} giờ {now.minute:02d} phút, {weekday}, ngày {now.day}/{now.month}/{now.year}."

        if _contains(norm_text, "btu", "tinh tien dien", "evn", "mua sam", "di ngu", "an toan toan dien", "kiem tra an toan") or (
            _contains(norm_text, "co an toan khong") and not _contains(norm_text, "gas", "khi gas")
        ):
            return None

        # Temperature & humidity (indoor)
        is_indoor_climate = _contains(norm_text, "nhiet do", "do am") or (
            _contains(norm_text, "nong", "lanh", "thoi tiet")
            and _contains(norm_text, "trong nha", "nha minh", "trong phong", "phong khach", "phong ngu", "phong")
        )
        if is_indoor_climate:
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

        if _contains(norm_text, "google", "tim kiem", "tra cuu", "doc bao", "tin tuc", "search", "wiki"):
            return None

        # Motion sensor
        if _contains(norm_text, "chuyen dong", "co ai trong phong", "co nguoi trong phong", "phat hien nguoi", "co trom"):
            pir = reg.get("living-motion")
            if pir and isinstance(pir.state, dict):
                motion = pir.state.get("motion", False)
                return (
                    "Cảm biến phòng khách hiện phát hiện có chuyển động."
                    if motion
                    else "Hiện tại không phát hiện chuyển động nào trong phòng khách."
                )

        # Entrance door lock
        if _contains(norm_text, "cua chinh", "khoa cua", "o khoa", "cua dong hay mo", "cua mo hay khoa", "kiem tra cua"):
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
        """Generate friendly conversational response in Xiaozhi AI persona using local GPU LLM."""
        if _contains(norm_text, "xin chao", "chao ban", "hello", "hi") and len(norm_text) < 16:
            return (
                "Xin chào! Tôi là Trợ lý AI Xiaozhi, đang kết nối với hệ sinh thái thông minh ESP32. "
                "Tôi có thể trò chuyện, trả lời kiến thức hoặc hỗ trợ cuộc sống của bạn."
            )
        if _contains(norm_text, "ban la ai", "ten gi", "gioi thieu") and len(norm_text) < 25:
            return (
                "Tôi là Trợ lý AI Xiaozhi, bộ não nhà thông minh kết hợp mô hình AI ngôn ngữ và vi điều khiển ESP32. "
                "Tôi luôn sẵn sàng trò chuyện và đồng hành cùng bạn."
            )
        if _contains(norm_text, "cam on", "thanks", "thank you"):
            return "Rất sẵn lòng phục vụ bạn! Hãy gọi Xiaozhi bất cứ khi nào bạn cần nhé."

        # Tận dụng LLM Qwen 2.5 chạy GPU để trả lời mọi câu hỏi trò chuyện, tâm sự, kiến thức
        try:
            from src.services.llm import get_llm
            from langchain_core.messages import SystemMessage, HumanMessage
            from datetime import datetime
            now = datetime.now()
            WEEKDAYS_VI = {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"}
            weekday_str = WEEKDAYS_VI.get(now.weekday(), "")
            time_context = f"Thời điểm hiện tại: {weekday_str}, {now.hour:02d}:{now.minute:02d}, ngày {now.day:02d}/{now.month:02d}/{now.year}. "

            llm = get_llm()
            system_prompt = (
                "Bạn là Xiaozhi (Tiểu Trí) - Trợ lý AI nhà thông minh độc quyền của HomeMind Hub. "
                f"{time_context}"
                "QUY TẮC BẮT BUỘC: Bạn PHẢI trả lời hoàn toàn 100% bằng TIẾNG VIỆT tự nhiên, ấm áp, ngắn gọn trong 1-2 câu. "
                "TUYỆT ĐỐI KHÔNG sử dụng tiếng Trung, chữ Hán hoặc tiếng Anh trong câu trả lời."
            )
            ai_res = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=raw_query)])
            if ai_res and ai_res.content and str(ai_res.content).strip():
                return str(ai_res.content).strip()
        except Exception as e:
            logger.warning(f"Xiaozhi LLM generation error: {e}")

        return f"Trợ lý Xiaozhi đã ghi nhận: '{raw_query}'. Tôi luôn lắng nghe và sẵn sàng chia sẻ cùng bạn!"

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
