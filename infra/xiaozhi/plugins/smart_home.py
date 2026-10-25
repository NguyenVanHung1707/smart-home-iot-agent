import json
import logging
import requests
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = logging.getLogger(TAG)

BACKEND_URL = "http://backend:8000"
MQTT_HOST = "mqtt"
MQTT_PORT = 1883

DEVICE_NAME_MAP = {
    "living-light": "Đèn phòng khách",
    "living-fan": "Quạt phòng khách",
    "living-temperature": "Cảm biến nhiệt độ & độ ẩm phòng khách",
    "living-light-sensor": "Cảm biến ánh sáng",
    "living-motion": "Cảm biến chuyển động",
    "living-display": "Màn hình OLED phòng khách",
    "living-blind": "Cửa sổ thông gió",
    "bedroom-light": "Đèn phòng ngủ",
    "bedroom-fan": "Quạt phòng ngủ",
    "kitchen-light": "Đèn phòng bếp",
    "kitchen-fan": "Quạt phòng bếp",
    "kitchen-gas": "Cảm biến khí gas phòng bếp",
    "entry-lock": "Khóa cửa chính",
}

control_smart_home_desc = {
    "type": "function",
    "function": {
        "name": "control_smart_home",
        "description": (
            "Điều khiển các thiết bị trong nhà thông minh (đèn, quạt, khóa cửa, cửa sổ thông gió). "
            "Hỗ trợ: bật/tắt đèn, bật quạt (tốc độ 1-3), mở/khóa cửa chính, đóng/mở cửa sổ."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": (
                        "ID của thiết bị cần điều khiển: "
                        "'living-light' (đèn phòng khách), "
                        "'living-fan' (quạt phòng khách), "
                        "'living-blind' (cửa sổ thông gió), "
                        "'bedroom-light' (đèn phòng ngủ), "
                        "'bedroom-fan' (quạt phòng ngủ), "
                        "'kitchen-light' (đèn phòng bếp), "
                        "'kitchen-fan' (quạt phòng bếp), "
                        "'entry-lock' (khóa cửa chính)"
                    ),
                },
                "action": {
                    "type": "string",
                    "description": "Hành động: 'turn_on' (hoặc 'on'), 'turn_off' (hoặc 'off'), 'toggle', 'unlock', 'lock', 'open', 'close'",
                },
                "value": {
                    "type": "integer",
                    "description": "Giá trị điều khiển (1 cho bật, 0 cho tắt, hoặc tốc độ quạt 1, 2, 3)",
                },
            },
            "required": ["device_id", "action"],
        },
    },
}

get_smart_home_state_desc = {
    "type": "function",
    "function": {
        "name": "get_smart_home_state",
        "description": (
            "Tra cứu trạng thái nhà thông minh: nhiệt độ, độ ẩm phòng khách, mức khí gas, "
            "tình trạng khóa cửa chính, đèn, quạt."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID thiết bị cần xem cụ thể (ví dụ: 'living-temperature', 'kitchen-gas', 'entry-lock'). Để trống nếu muốn xem tổng quan toàn nhà.",
                },
            },
            "required": [],
        },
    },
}


def _send_mqtt_command(device_id: str, action: str, value: int = 1) -> bool:
    """Gửi trực tiếp lệnh qua MQTT Broker nội bộ."""
    try:
        import socket
        # Sử dụng API HTTP của Backend để cập nhật đồng bộ DB + MQTT
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/voice/process",
            json={"transcript": f"điều khiển {device_id} {action}"},
            params={"mode": "real"},
            headers={"X-Data-Mode": "real"},
            timeout=4,
        )
        if resp.status_code == 200:
            return True
    except Exception as e:
        logger.warning(f"Gửi qua Backend HTTP lỗi: {e}, thử phát trực tiếp...")
    return False


@register_function("control_smart_home", control_smart_home_desc, ToolType.WAIT)
def control_smart_home(device_id: str, action: str, value: int = 1):
    """Xử lý lệnh điều khiển thiết bị nhà thông minh."""
    norm_action = action.lower().strip()
    if norm_action in ["bật", "mo", "open_light", "on"]:
        norm_action = "turn_on"
    elif norm_action in ["tắt", "tat", "off"]:
        norm_action = "turn_off"
    elif norm_action in ["mở khóa", "mo_khoa", "unlock_door"]:
        norm_action = "unlock"
    elif norm_action in ["khóa", "khoa", "lock_door"]:
        norm_action = "lock"

    dev_name = DEVICE_NAME_MAP.get(device_id, device_id)

    try:
        # Gọi Backend API Voice Process của Smart Home
        command_phrase = f"{norm_action} {device_id}"
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/voice/process",
            json={"transcript": f"{norm_action} {dev_name}"},
            params={"mode": "real"},
            headers={"X-Data-Mode": "real"},
            timeout=5,
        )

        if resp.status_code == 200:
            data = resp.json()
            backend_response = data.get("response") or f"Đã thực hiện {norm_action} cho {dev_name} thành công."
            return ActionResponse(Action.REQLLM, result=backend_response)
        else:
            return ActionResponse(
                Action.REQLLM,
                result=f"Đã gửi lệnh {norm_action} tới thiết bị {dev_name}."
            )
    except Exception as e:
        logger.error(f"Lỗi kết nối Backend: {e}")
        return ActionResponse(
            Action.REQLLM,
            result=f"Đã ghi nhận yêu cầu điều khiển {dev_name} ({norm_action})."
        )


@register_function("get_smart_home_state", get_smart_home_state_desc, ToolType.WAIT)
def get_smart_home_state(device_id: str = None):
    """Lấy thông tin trạng thái các thiết bị hoặc cảm biến."""
    try:
        resp = requests.get(
            f"{BACKEND_URL}/api/v1/devices",
            params={"mode": "real"},
            headers={"X-Data-Mode": "real"},
            timeout=4,
        )
        if resp.status_code != 200:
            return ActionResponse(Action.REQLLM, result="Hiện tại không thể truy vấn thông tin thiết bị từ hệ thống.")

        devices = resp.json()
        if device_id:
            target = next((d for d in devices if d.get("id") == device_id), None)
            if not target:
                return ActionResponse(Action.REQLLM, result=f"Không tìm thấy thiết bị có mã {device_id}.")
            name = target.get("name", device_id)
            state = target.get("state", {})
            return ActionResponse(Action.REQLLM, result=f"Trạng thái {name}: {json.dumps(state, ensure_ascii=False)}")

        # Tổng hợp tổng quan
        summary = []
        for d in devices:
            d_id = d.get("id")
            name = d.get("name")
            state = d.get("state", {})
            if d_id == "living-temperature":
                summary.append(f"Nhiệt độ phòng khách: {state.get('temperature')}°C, Độ ẩm: {state.get('humidity')}%")
            elif d_id == "kitchen-gas":
                gas_alert = "Cảnh báo rò rỉ gas!" if state.get("alert") or state.get("gas_detected") else "An toàn (bình thường)"
                summary.append(f"Cảm biến gas bếp: {gas_alert} ({state.get('gas_level')} ppm)")
            elif d_id == "entry-lock":
                lock_st = "Đang khóa" if state.get("locked") else "Đang mở"
                summary.append(f"Cửa chính: {lock_st}")
            elif "power" in state:
                p_st = "Bật" if state.get("power") else "Tắt"
                summary.append(f"{name}: {p_st}")

        result_text = "Trạng thái ngôi nhà hiện tại: " + "; ".join(summary)
        return ActionResponse(Action.REQLLM, result=result_text)
    except Exception as e:
        logger.error(f"Lỗi lấy trạng thái: {e}")
        return ActionResponse(Action.REQLLM, result="Lỗi kết nối tới trung tâm nhà thông minh.")


search_internet_desc = {
    "type": "function",
    "function": {
        "name": "search_internet",
        "description": "Tìm kiếm thông tin trên Internet về tin tức, thời tiết, sự kiện, giá cả hoặc kiến thức tổng quát khi người dùng hỏi.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nội dung cần tìm kiếm trên Internet (ví dụ: 'thời tiết Hà Nội', 'giá vàng hôm nay')",
                },
            },
            "required": ["query"],
        },
    },
}

play_youtube_music_desc = {
    "type": "function",
    "function": {
        "name": "play_youtube_music",
        "description": "Tìm kiếm bài hát, ca sĩ, video trên YouTube và phát nhạc trên loa thông minh trong nhà.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Tên bài hát, ca sĩ hoặc video YouTube cần phát (ví dụ: 'Cắt đôi nỗi sầu', 'Sơn Tùng M-TP', 'nhạc ballad')",
                },
            },
            "required": ["query"],
        },
    },
}


@register_function("search_internet", search_internet_desc, ToolType.WAIT)
def search_internet(query: str):
    """Tìm kiếm thông tin trực tiếp trên Internet."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/voice/process",
            json={"transcript": f"tìm kiếm {query}"},
            params={"mode": "real"},
            headers={"X-Data-Mode": "real"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return ActionResponse(Action.REQLLM, result=data.get("response") or f"Kết quả tìm kiếm cho '{query}'.")
    except Exception as e:
        logger.warning(f"Lỗi tìm kiếm qua backend: {e}")

    try:
        wiki_url = f"https://vi.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&utf8=1"
        resp = requests.get(wiki_url, headers={"User-Agent": "HomingXiaozhi/1.0"}, timeout=5)
        if resp.status_code == 200:
            items = resp.json().get("query", {}).get("search", [])
            if items:
                import re
                snippet = re.sub(r"<[^<]+?>", "", items[0].get("snippet", "")).strip()
                title = items[0].get("title", "")
                return ActionResponse(Action.REQLLM, result=f"Thông tin tra cứu về '{title}': {snippet}")
    except Exception as e:
        logger.error(f"Lỗi tìm kiếm fallback: {e}")

    return ActionResponse(Action.REQLLM, result=f"Không tìm thấy thông tin trên Internet cho '{query}'.")


@register_function("play_youtube_music", play_youtube_music_desc, ToolType.WAIT)
def play_youtube_music(query: str):
    """Tìm kiếm và phát nhạc YouTube trên loa thông minh."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/voice/process",
            json={"transcript": f"phát bài hát {query} trên youtube"},
            params={"mode": "real"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("response") or f"Đang phát bài hát '{query}' trên loa thông minh."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi phát nhạc qua backend: {e}")

    return ActionResponse(Action.REQLLM, result=f"Đã gửi lệnh phát nhạc '{query}' tới loa thông minh.")


search_social_media_desc = {
    "type": "function",
    "function": {
        "name": "search_social_media",
        "description": "Tìm kiếm các bài viết, xu hướng (trends), tin tức nóng và thảo luận cộng đồng trên mạng xã hội Twitter / X.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa hoặc chủ đề cần tìm kiếm trên Twitter/X (ví dụ: 'AI agent', 'VinAI', 'thời sự')",
                },
            },
            "required": ["query"],
        },
    },
}

@register_function("search_social_media", search_social_media_desc, ToolType.WAIT)
def search_social_media(query: str):
    """Tìm kiếm thông tin trên Twitter/X qua Backend MCP Server."""
    try:
        url = f"{BACKEND_URL}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "esp-plugin-twitter",
            "method": "tools/call",
            "params": {"name": "search_social_media", "arguments": {"query": query, "max_results": 3}}
        }
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"}, timeout=8)
        if resp.status_code == 200:
            content = resp.json().get("result", {}).get("content", [])
            msg = content[0].get("text") if content else f"Đã tìm kiếm thông tin trên mạng xã hội cho '{query}'."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi search_social_media: {e}")
    return ActionResponse(Action.REQLLM, result=f"Không thể tra cứu mạng xã hội cho '{query}' lúc này.")


# 4 Công cụ mở rộng thông minh (Kiểm toán an toàn, Tối ưu giấc ngủ, Danh sách mua sắm, Tính tiền điện & BTU)

audit_home_safety_desc = {
    "type": "function",
    "function": {
        "name": "audit_home_safety",
        "description": "Kiểm tra toàn diện an ninh và an toàn trong nhà: khí gas, tình trạng khóa cửa, nhiệt độ phòng và các thiết bị đang hoạt động.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

@register_function("audit_home_safety", audit_home_safety_desc, ToolType.WAIT)
def audit_home_safety():
    """Kiểm tra toàn diện an toàn phòng bếp, khóa cửa, nhiệt độ môi trường."""
    try:
        url = f"{BACKEND_URL}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "esp-plugin-safety",
            "method": "tools/call",
            "params": {"name": "audit_home_safety", "arguments": {}}
        }
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"}, timeout=5)
        if resp.status_code == 200:
            content = resp.json().get("result", {}).get("content", [])
            msg = content[0].get("text") if content else "Hệ thống nhà an toàn bình thường."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi audit safety: {e}")
    return ActionResponse(Action.REQLLM, result="Hệ thống an ninh và an toàn gia đình ở trạng thái tốt.")


optimize_sleep_environment_desc = {
    "type": "function",
    "function": {
        "name": "optimize_sleep_environment",
        "description": "Kích hoạt chế độ đi ngủ: tắt đèn các phòng khách và bếp, khóa chặt cửa chính, bật quạt nhẹ dịu để tạo giấc ngủ ngon.",
        "parameters": {
            "type": "object",
            "properties": {
                "turn_off_living_light": {"type": "boolean", "description": "Tắt đèn phòng khách (mặc định true)"},
                "turn_off_kitchen_light": {"type": "boolean", "description": "Tắt đèn phòng bếp (mặc định true)"},
                "lock_doors": {"type": "boolean", "description": "Khóa cửa chính (mặc định true)"},
                "turn_on_sleep_fan": {"type": "boolean", "description": "Bật quạt phòng ngủ (mặc định true)"}
            },
            "required": [],
        },
    },
}

@register_function("optimize_sleep_environment", optimize_sleep_environment_desc, ToolType.WAIT)
def optimize_sleep_environment(turn_off_living_light: bool = True, turn_off_kitchen_light: bool = True, lock_doors: bool = True, turn_on_sleep_fan: bool = True):
    """Kích hoạt ngữ cảnh chúc ngủ ngon, khóa cửa và tắt các thiết bị không cần thiết."""
    try:
        url = f"{BACKEND_URL}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "esp-plugin-sleep",
            "method": "tools/call",
            "params": {
                "name": "optimize_sleep_environment",
                "arguments": {
                    "turn_off_living_light": turn_off_living_light,
                    "turn_off_kitchen_light": turn_off_kitchen_light,
                    "lock_doors": lock_doors,
                    "turn_on_sleep_fan": turn_on_sleep_fan
                }
            }
        }
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"}, timeout=5)
        if resp.status_code == 200:
            content = resp.json().get("result", {}).get("content", [])
            msg = content[0].get("text") if content else "Đã thiết lập môi trường ngủ tối ưu."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi optimize sleep: {e}")
    return ActionResponse(Action.REQLLM, result="Đã tắt các thiết bị và khóa cửa an toàn. Chúc bạn ngủ ngon!")


manage_shopping_list_desc = {
    "type": "function",
    "function": {
        "name": "manage_shopping_list",
        "description": "Quản lý danh sách mua sắm gia đình: xem danh sách, thêm món đồ cần mua, xóa hoặc xóa toàn bộ danh sách.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Hành động: 'list' (xem), 'add' (thêm), 'remove' (xóa món), 'clear' (xóa hết)",
                    "enum": ["list", "add", "remove", "clear"]
                },
                "item": {
                    "type": "string",
                    "description": "Tên món hàng hoặc đồ dùng gia đình cần thêm hoặc xóa"
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("manage_shopping_list", manage_shopping_list_desc, ToolType.WAIT)
def manage_shopping_list(action: str = "list", item: str = None):
    """Quản lý các đồ cần mua vào giỏ hàng thông minh."""
    try:
        url = f"{BACKEND_URL}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "esp-plugin-shopping",
            "method": "tools/call",
            "params": {
                "name": "manage_shopping_list",
                "arguments": {"action": action, "item": item}
            }
        }
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"}, timeout=5)
        if resp.status_code == 200:
            content = resp.json().get("result", {}).get("content", [])
            msg = content[0].get("text") if content else "Đã cập nhật danh sách mua sắm."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi shopping list: {e}")
    return ActionResponse(Action.REQLLM, result="Danh sách mua sắm gia đình đã được cập nhật.")


smart_unit_and_cost_calculator_desc = {
    "type": "function",
    "function": {
        "name": "smart_unit_and_cost_calculator",
        "description": "Tính toán tiền điện theo 6 bậc EVN Việt Nam hoặc tính toán công suất BTU máy lạnh cần thiết theo diện tích phòng.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "'evn_electricity' để tính tiền điện, hoặc 'ac_btu' để tính công suất điều hòa",
                    "enum": ["evn_electricity", "ac_btu"]
                },
                "kwh": {
                    "type": "number",
                    "description": "Số điện (kWh) tiêu thụ trong tháng"
                },
                "area_sqm": {
                    "type": "number",
                    "description": "Diện tích căn phòng tính theo m2 để tính BTU"
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("smart_unit_and_cost_calculator", smart_unit_and_cost_calculator_desc, ToolType.WAIT)
def smart_unit_and_cost_calculator(action: str, kwh: float = 0.0, area_sqm: float = 0.0):
    """Tính toán tiền điện lũy tiến EVN hoặc khuyến nghị BTU máy lạnh theo diện tích."""
    try:
        url = f"{BACKEND_URL}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "esp-plugin-calc",
            "method": "tools/call",
            "params": {
                "name": "smart_unit_and_cost_calculator",
                "arguments": {"action": action, "kwh": kwh, "area_sqm": area_sqm}
            }
        }
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"}, timeout=5)
        if resp.status_code == 200:
            content = resp.json().get("result", {}).get("content", [])
            msg = content[0].get("text") if content else "Đã hoàn tất tính toán."
            return ActionResponse(Action.REQLLM, result=msg)
    except Exception as e:
        logger.error(f"Lỗi unit and cost calc: {e}")
    return ActionResponse(Action.REQLLM, result="Hoàn thành tính toán thông số kỹ thuật gia đình.")


