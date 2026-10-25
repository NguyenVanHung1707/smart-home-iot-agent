"""Model Context Protocol (MCP) Server for HomeMind Hub.

Implements the official JSON-RPC 2.0 MCP specification (version 2024-11-05),
allowing Xiaozhi AI, Claude Desktop, Cursor, and any MCP client to discover
and invoke smart home capabilities as tools.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import src.services.devices as devices_mod
from src.services.device_control import control_device

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "HomeMind-SmartHome-MCP-Server",
    "version": "1.0.0",
}

AVAILABLE_TOOLS = [
    {
        "name": "control_device",
        "description": "Điều khiển thiết bị trong nhà (bật/tắt đèn, quạt, mở/khóa cửa, kéo rèm).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Mã thiết bị (vd: 'living-light', 'living-fan', 'bedroom-light', 'kitchen-light', 'entry-lock')",
                },
                "action": {
                    "type": "string",
                    "description": "Thao tác: 'on', 'off', 'toggle', 'lock', 'unlock', 'open', 'close'",
                },
                "value": {
                    "type": "integer",
                    "description": "Giá trị thiết lập (vd: tốc độ quạt 1-3, hoặc 1 cho bật, 0 cho tắt)",
                },
            },
            "required": ["device_id", "action"],
        },
    },
    {
        "name": "get_device_state",
        "description": "Tra cứu trạng thái cụ thể của một thiết bị hoặc cảm biến (nhiệt độ, độ ẩm, rò rỉ gas, cửa).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Mã thiết bị cần tra cứu (vd: 'living-temperature', 'kitchen-gas', 'entry-lock', 'living-light')",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "list_all_devices",
        "description": "Liệt kê danh sách tất cả các phòng và thiết bị trong nhà thông minh kèm trạng thái hiện tại.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Lọc theo tên phòng (vd: 'Phòng khách', 'Phòng ngủ', 'Phòng bếp', 'Lối vào'). Để trống nếu muốn xem toàn nhà.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "execute_preset",
        "description": "Kích hoạt ngữ cảnh tự động hóa nhà thông minh (Đi ngủ, Ra khỏi nhà, Về nhà, Bật hết đèn).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "preset_id": {
                    "type": "string",
                    "description": "Mã ngữ cảnh: 'all_lights_on', 'all_off', 'good_night', 'leave_home', 'welcome_home'",
                },
            },
            "required": ["preset_id"],
        },
    },
    {
        "name": "get_system_time",
        "description": "Lấy ngày giờ hiện tại của hệ thống nhà thông minh theo múi giờ Việt Nam (bao gồm thứ mấy trong tuần).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "play_youtube_music",
        "description": "Tìm kiếm bài hát, video trên YouTube và phát trên loa thông minh trong nhà.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Tên bài hát, ca sĩ, video hoặc thể loại nhạc cần phát",
                },
                "room": {
                    "type": "string",
                    "description": "Tên phòng có loa thông minh (mặc định: 'Phòng khách')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_internet",
        "description": "Tìm kiếm thông tin, tin tức báo chí, thời tiết, sự kiện hoặc kiến thức tổng quát trên Internet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa hoặc câu hỏi cần tra cứu trên Internet",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_social_media",
        "description": "Tìm kiếm bài viết, xu hướng thảo luận (trends), tin tức cộng đồng trên mạng xã hội Twitter / X.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa hoặc chủ đề cần tìm kiếm trên mạng xã hội Twitter/X",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Số lượng bài viết tối đa cần lấy (mặc định 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "audit_home_safety",
        "description": "Chẩn đoán toàn diện an toàn, rò rỉ khí gas, an ninh cửa, nhiệt độ và thiết bị bật quên.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Phạm vi kiểm tra ('all', 'security', 'fire_gas', 'electrical')",
                },
            },
            "required": [],
        },
    },
    {
        "name": "optimize_sleep_environment",
        "description": "Kích hoạt chế độ ngủ ngon: khóa cửa, tắt đèn phòng khách & bếp, bật quạt ngủ êm ái.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bedroom": {
                    "type": "string",
                    "description": "Tên phòng ngủ",
                },
            },
            "required": [],
        },
    },
    {
        "name": "manage_shopping_list",
        "description": "Quản lý danh sách mua sắm nhu yếu phẩm gia đình (thêm, xem, đánh dấu đã mua, dọn dẹp).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Hành động: 'add', 'get', 'mark_bought', 'delete', 'clear'",
                },
                "item": {
                    "type": "string",
                    "description": "Tên món đồ cần mua hoặc đã mua",
                },
                "quantity": {
                    "type": "string",
                    "description": "Số lượng món đồ",
                },
            },
            "required": [],
        },
    },
    {
        "name": "smart_unit_and_cost_calculator",
        "description": "Tính toán chi phí điện sinh hoạt EVN 6 bậc có thuế VAT, tư vấn chọn công suất BTU máy lạnh theo diện tích và quy đổi nhiệt độ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "calc_type": {
                    "type": "string",
                    "description": "'electricity_bill_evn', 'ac_btu_recommendation', 'temperature_converter', 'math'",
                },
                "kwh": {
                    "type": "number",
                    "description": "Số kWh điện tiêu thụ",
                },
                "room_area_m2": {
                    "type": "number",
                    "description": "Diện tích phòng tính bằng mét vuông (m2)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": "Tra cứu dự báo thời tiết thực tế (nhiệt độ, độ ẩm, khả năng mưa, chỉ số UV) và khuyến nghị nhà thông minh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Tên thành phố hoặc vị trí (vd: 'Hà Nội', 'TP. Hồ Chí Minh', 'Đà Nẵng')",
                },
                "days": {
                    "type": "integer",
                    "description": "Số ngày dự báo (mặc định 1 ngày)",
                },
            },
            "required": [],
        },
    },
]


class McpServer:
    """Dispatches JSON-RPC 2.0 MCP requests."""

    def handle_request(self, payload: dict[str, Any], mode: str = "real") -> dict[str, Any]:
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {}) or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": AVAILABLE_TOOLS,
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {}) or {}
            result_text = self._call_tool(tool_name, tool_args, mode=mode)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text,
                        }
                    ],
                    "isError": False,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found",
                },
            }

    def _call_tool(self, tool_name: str, args: dict[str, Any], mode: str = "real") -> str:
        reg = devices_mod.get_registry(mode)

        if tool_name == "control_device":
            device_id = args.get("device_id")
            action = args.get("action", "").lower().strip()
            value = args.get("value")

            from src.services.guardrails import guardrails
            dev_guard = guardrails.inspect_device_command(device_id, action, value)
            if not dev_guard.passed:
                return dev_guard.suggested_response or f"Lệnh bị chặn bởi rào chắn an toàn: {dev_guard.reason}"

            if device_id in {"entry-lock", "lock", "front-door"} and action in {"unlock", "open"}:
                return "Yêu cầu mở cửa bị từ chối vì lý do an ninh. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ."
            dev, err = control_device(device_id, action, value, mode=mode)
            if err:
                dev_obj = reg.get(device_id)
                if dev_obj and err in {"device_offline", "ack_timeout", "timeout"}:
                    reg.command(device_id, action, value)
                    return f"Lệnh đã gửi tới {dev_obj.name} ({device_id} -> {action}). (Thiết bị hiện ở trạng thái chờ/offline)."
                return f"Lỗi điều khiển thiết bị {device_id}: {err}"
            return f"Thực hiện thành công: {dev.name} ({device_id}) -> {action}."

        elif tool_name == "get_device_state":
            device_id = args.get("device_id")
            dev = reg.get(device_id)
            if not dev:
                return f"Không tìm thấy thiết bị có ID '{device_id}'."
            st = dev.state
            if device_id == "living-temperature":
                return f"Nhiệt độ phòng khách: {st.get('temperature')}°C, Độ ẩm: {st.get('humidity')}%."
            elif device_id == "kitchen-gas":
                status = "Cảnh báo rò rỉ!" if st.get("alert") or st.get("gas_detected") else "Bình thường (an toàn)"
                return f"Cảm biến khí gas phòng bếp: {status} ({st.get('gas_level', 0)} ppm)."
            elif device_id == "entry-lock":
                return "Khóa cửa chính: " + ("Đang khóa an toàn." if st.get("locked") else "Đang mở khóa.")
            else:
                return f"Trạng thái {dev.name}: " + (", ".join(f"{k}={v}" for k, v in st.items()) or "Hoạt động bình thường.")

        elif tool_name == "list_all_devices":
            room_filter = args.get("room")
            devices = reg.list()
            if room_filter:
                devices = [d for d in devices if d.room.lower() == room_filter.lower()]
            lines = [f"- {d.name} ({d.id}, phòng {d.room}): {'Bật' if d.state.get('power') or d.state.get('on') else 'Tắt'}" for d in devices]
            return f"Danh sách {len(devices)} thiết bị:\n" + "\n".join(lines)

        elif tool_name == "execute_preset":
            preset_id = args.get("preset_id")
            if preset_id == "all_lights_on":
                for d in reg.list():
                    if d.kind == "light":
                        control_device(d.id, "on", mode=mode)
                return "Đã bật tất cả đèn trong nhà."
            elif preset_id in ("all_off", "leave_home"):
                for d in reg.list():
                    if d.kind in ("light", "fan"):
                        control_device(d.id, "off", mode=mode)
                control_device("entry-lock", "lock", mode=mode)
                return "Đã tắt tất cả đèn, quạt và khóa cửa chính an toàn."
            elif preset_id == "good_night":
                for d in reg.list():
                    if d.kind == "light" and "ngủ" not in d.room.lower():
                        control_device(d.id, "off", mode=mode)
                control_device("entry-lock", "lock", mode=mode)
                return "Đã kích hoạt chế độ ban đêm: khóa cửa, tắt đèn phòng khách & bếp."
            elif preset_id == "welcome_home":
                control_device("living-light", "on", mode=mode)
                control_device("living-fan", "on", mode=mode)
                return "Chào mừng bạn về nhà! Đã bật đèn và quạt phòng khách. Vui lòng nhập mật khẩu hoặc quét thẻ từ để mở cửa."
            return f"Ngữ cảnh '{preset_id}' đã được kích hoạt."

        elif tool_name == "get_system_time":
            from datetime import datetime
            now = datetime.now()
            weekdays_vi = {
                0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm",
                4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"
            }
            weekday_str = weekdays_vi.get(now.weekday(), "")
            return f"Thời gian hiện tại: {now.hour} giờ {now.minute:02d} phút, {weekday_str}, ngày {now.day} tháng {now.month} năm {now.year}."

        elif tool_name == "play_youtube_music":
            from src.agents.tools.media_player import play_youtube_music
            import json
            query = args.get("query", "")
            room = args.get("room", "Phòng khách")
            device_id = args.get("device_id", "gateway-speaker")
            res = play_youtube_music.invoke({"query": query, "room": room, "device_id": device_id})
            res_data = json.loads(res) if isinstance(res, str) else res
            msg = res_data.get("message") or f"Đang phát bài hát {query} trên Loa ESP32 AI Gateway."
            stream_url = res_data.get("audio_stream_url") or ""
            track_title = res_data.get("track") or query
            return json.dumps({
                "message": msg,
                "audio_stream_url": stream_url,
                "track": track_title,
                "device_id": res_data.get("device_id", "gateway-speaker")
            }, ensure_ascii=False)

        elif tool_name == "search_internet":
            from src.agents.tools.internet_search import search_internet
            import json
            query = args.get("query", "")
            res = search_internet.invoke({"query": query})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("summary") or res_data.get("message") or "Không tìm thấy thông tin trên Internet."

        elif tool_name == "search_social_media":
            from src.agents.tools.social_search import search_social_media
            import json
            query = args.get("query", "")
            max_res = args.get("max_results", 5)
            res = search_social_media.invoke({"query": query, "max_results": max_res})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("summary") or res_data.get("message") or "Không tìm thấy bài viết nào trên Twitter/X."

        elif tool_name == "audit_home_safety":
            from src.agents.tools.home_safety_audit import audit_home_safety
            import json
            scope = args.get("scope", "all")
            res = audit_home_safety.invoke({"scope": scope, "mode": mode})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("message") or "Đã hoàn thành chẩn đoán an toàn ngôi nhà."

        elif tool_name == "optimize_sleep_environment":
            from src.agents.tools.sleep_optimizer import optimize_sleep_environment
            import json
            bedroom = args.get("bedroom", "Phòng ngủ")
            res = optimize_sleep_environment.invoke({"bedroom": bedroom, "mode": mode})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("message") or "Đã kích hoạt chế độ ngủ ngon."

        elif tool_name == "manage_shopping_list":
            from src.agents.tools.shopping_list import manage_shopping_list
            import json
            action = args.get("action", "get")
            item = args.get("item")
            qty = args.get("quantity")
            res = manage_shopping_list.invoke({"action": action, "item": item, "quantity": qty})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("message") or "Đã xử lý danh sách mua sắm."

        elif tool_name == "smart_unit_and_cost_calculator":
            from src.agents.tools.smart_calc_converter import smart_unit_and_cost_calculator
            import json
            calc_type = args.get("calc_type", "electricity_bill_evn")
            kwh = args.get("kwh")
            area = args.get("room_area_m2")
            res = smart_unit_and_cost_calculator.invoke({"calc_type": calc_type, "kwh": kwh, "room_area_m2": area})
            res_data = json.loads(res) if isinstance(res, str) else res
            return res_data.get("message") or "Đã thực hiện tính toán chuyên gia."

        elif tool_name in ("get_weather_forecast", "get_weather"):
            from src.agents.tools.weather_forecast import get_weather_forecast
            import json
            location = args.get("location", "Hà Nội")
            days = args.get("days", 1)
            res = get_weather_forecast.invoke({"location": location, "days": days})
            res_data = json.loads(res) if isinstance(res, str) else res
            curr = res_data.get("current", {})
            temp = curr.get("temperature_2m", 31)
            cond = curr.get("condition", "quang đãng, nắng đẹp")
            hum = curr.get("relative_humidity_2m", 65)
            rain_prob = curr.get("precipitation_probability") or 0
            recs = res_data.get("smart_home_recommendations", [])
            rec_str = f" {recs[0]}" if recs else ""
            summary = f"Thời tiết tại {location} hiện tại: {cond}, nhiệt độ {temp}°C, độ ẩm {hum}%.{rec_str}"
            return summary

        return f"Công cụ '{tool_name}' không được hỗ trợ."


mcp_server = McpServer()
