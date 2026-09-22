"""Deterministic Vietnamese command parsing for common smart-home requests."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import src.services.devices as devices_mod
from src.agents.tool_routing import is_absolute_calendar_schedule, is_prompt_injection_attempt
from src.models.schemas import Device
from src.services.conversation import MissingSlot, PendingClarification, conversations
from src.services.device_control import control_device
from src.services.devices import registry, sensor_reading
from src.services.information_routing import execute_information_route, route_information_request


def _active_registry(mode: str | None = None) -> Any:
    if mode is not None:
        return devices_mod.get_registry(mode)
    if registry is not devices_mod.registry:
        return registry
    return devices_mod.get_registry(devices_mod.get_active_data_mode())


@dataclass(frozen=True)
class ParsedCommand:
    device_id: str
    action: str
    value: dict[str, bool | int | float | str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"device_id": self.device_id, "action": self.action, "value": self.value}


@dataclass(frozen=True)
class ParsedHomeRequest:
    handled: bool
    commands: tuple[ParsedCommand, ...] = ()
    reply: str = ""
    missing_slot: MissingSlot | None = None
    referenced_device_ids: tuple[str, ...] = ()


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFC", text.lower()).replace("chớ", "đừng")
    decomposed = unicodedata.normalize("NFD", lowered).replace("đ", "d")
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%]+", " ", without_marks)).strip()


def _contains(text: str, *phrases: str) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


def _has_device_mention(text: str) -> bool:
    if any(_normalize(f"{device.name} {device.id} {device.room}") in text for device in _active_registry().list()):
        return True
    return any(
        _contains(text, *aliases)
        for aliases in (
            ("den", "bong den", "anh sang"),
            ("dieu hoa", "may lanh", "aircon"),
            ("quat", "fan"),
            ("rem", "man cua", "blind"),
            ("loa", "am luong", "speaker"),
            ("man hinh", "display", "monitor", "tv"),
            ("khoa cua", "cua chinh", "o khoa", "lock"),
            ("cam bien", "sensor"),
        )
    )


def _has_adjustment_cue(text: str) -> bool:
    return _contains(
        text,
        "dat",
        "dieu chinh",
        "chinh",
        "chuyen che do",
        "chuyen sang",
        "che do",
        "tang",
        "giam",
        "ha",
        "nang",
        "sang hon",
        "toi di",
        "mo hon",
        "to hon",
        "nho hon",
        "be lai",
        "be tieng",
        "nho tieng",
        "van nho",
        "van to",
        "van loa nho",
        "van loa to",
        "keo",
        "keo len",
        "keo xuong",
        "cuon len",
        "tha xuong",
    ) or bool(re.search(r"(?<!\d)\d{1,3}(?:\s*%|\s*do|\b)", text))


def _has_display_message_cue(text: str) -> bool:
    """Recognize display-content mutations without treating status questions as commands."""
    if re.search(
        r"\b(?:hien|hien thi)\s+(?:thong bao|chu|noi dung|tin nhan)\s+(?:gi|nao)\b",
        text,
    ) or _contains(text, "dang hien", "dang hien thi"):
        return False
    return bool(
        _contains(
            text,
            "hien thong bao",
            "hien chu",
            "hien thi",
            "dat thong bao",
            "dat noi dung",
            "cap nhat thong bao",
            "doi thong bao",
        )
        or re.search(r"\b(?:cho|de)\b.+\b(?:hien|hien thi)\b", text)
    )


def _display_message(text: str) -> str | None:
    """Extract display content only when the request supplies actual text."""
    match = re.search(
        r"\b(?:thong bao|tin nhan|noi dung)\b\s*(?:la\s+|:\s*)?(.+)$",
        text,
    )
    if match:
        content = match.group(1).strip()
        if content and content not in {"gi", "nao"}:
            return content[:500]

    match = re.search(
        r"\b(?:hien thi|hien)\s+(.+?)(?:\s+(?:tren|len)\s+man hinh(?:\s+.+)?|$)",
        text,
    )
    if match:
        content = match.group(1).strip()
        if content and content not in {"gi", "nao"}:
            return content[:500]
    return None


def _has_action_word(text: str) -> bool:
    return bool(re.search(r"\b(?:bat|tat|mo|dong|keo|cuon|tha|khoa|chot)\b", text))


def _number(text: str, minimum: int, maximum: int) -> int | None:
    for match in re.finditer(r"(?<!\d)(\d{1,3})(?:\s*%|\s*do|\b)", text):
        value = int(match.group(1))
        if minimum <= value <= maximum:
            return value
    return None


def _bounded_step(device_id: str, field: str, delta: int) -> int | None:
    device = _active_registry().get(device_id)
    current = device.state.get(field) if device else None
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    return max(0, min(100, round(current + delta)))


def _state_reply(text: str) -> str:
    ids = _device_ids(text)
    if len(ids) != 1:
        return "Đây là câu hỏi trạng thái; bạn vui lòng nói rõ một thiết bị để mình kiểm tra."
    device = _active_registry().get(ids[0])
    if not device:
        return "Mình chưa tìm thấy thiết bị cần kiểm tra."
    if device.kind in {"light", "aircon", "speaker", "fan"}:
        state = "bật" if bool(device.state.get("power")) else "tắt"
        return f"{device.name} hiện đang {state}."
    if device.kind == "lock":
        state = "khóa" if bool(device.state.get("locked")) else "mở"
        return f"{device.name} hiện đang {state}."
    if device.kind == "blind":
        return f"{device.name} hiện đang mở ở {device.state.get('position', 0)}%."
    return f"Trạng thái hiện tại của {device.name}: {device.state}."


def _format_device_brief(dev: Device) -> str:
    if not dev.online:
        return f"{dev.name} (ngoại tuyến)"
    if dev.kind in {"light", "aircon", "speaker"}:
        p = "đang bật" if bool(dev.state.get("power")) else "đang tắt"
        if dev.kind == "light" and dev.state.get("brightness") is not None and p == "đang bật":
            return f"{dev.name} ({p}, độ sáng {dev.state.get('brightness')}%)"
        if dev.kind == "aircon" and dev.state.get("target_temperature") is not None:
            return f"{dev.name} ({p}, {dev.state.get('target_temperature')}°C)"
        if dev.kind == "speaker" and dev.state.get("volume") is not None:
            return f"{dev.name} ({p}, âm lượng {dev.state.get('volume')}%)"
        return f"{dev.name} ({p})"
    if dev.kind == "blind":
        pos = dev.state.get("position", 0)
        return f"{dev.name} (mở {pos}%)" if (pos or 0) > 0 else f"{dev.name} (đang đóng)"
    if dev.kind == "lock":
        return f"{dev.name} (đang khóa)" if bool(dev.state.get("locked", True)) else f"{dev.name} (đang mở)"
    if dev.kind == "sensor":
        s = dev.state
        temperature = sensor_reading(dev, "temperature")
        humidity = sensor_reading(dev, "humidity")
        gas = sensor_reading(dev, "gas")
        light = sensor_reading(dev, "light")
        motion = sensor_reading(dev, "motion")
        if temperature:
            hum = f", độ ẩm {humidity['value']}%" if humidity else ""
            return f"{dev.name} ({temperature['value']}°C{hum})"
        if gas:
            return f"{dev.name} (khí gas {gas['value']} {gas['unit'] or ''})".rstrip()
        if light:
            dark_str = "trời tối" if s.get("is_dark") else "trời sáng"
            return f"{dev.name} ({dark_str})"
        if motion:
            return f"{dev.name} ({'có chuyển động' if motion['value'] else 'không có chuyển động'})"
        return f"{dev.name}"
    if dev.kind == "display":
        msg = dev.state.get("message")
        return f"{dev.name} ('{msg}')" if msg else f"{dev.name}"
    return f"{dev.name}"


def _room_topology_reply(text: str, mode: str | None = None) -> str | None:
    # If the text has a direct power/control command action (like "bật", "tắt", "đặt", "chỉnh", "khóa"),
    # it is a command, not a topology listing query.
    if _power_action(text) is not None or _has_adjustment_cue(text):
        return None
    if _contains(text, "tat het", "bat het", "khoa cua", "mo cua"):
        return None

    reg = devices_mod.get_registry(mode)
    devices = reg.list()
    if not devices:
        return None

    # 1. Asking all rooms / how many rooms
    asking_rooms_list = _contains(
        text,
        "bao nhieu phong",
        "nhung phong nao",
        "co phong nao",
        "co nhung phong",
        "danh sach phong",
        "cac phong trong nha",
        "trong nha co phong",
        "nha co phong gi",
        "tat ca cac phong",
        "tat ca phong",
        "co may phong",
    )
    if asking_rooms_list:
        grouped: dict[str, list[Device]] = {}
        for d in devices:
            grouped.setdefault(d.room, []).append(d)
        parts = [f"{r} ({len(devs)} thiết bị)" for r, devs in grouped.items()]
        return f"Ngôi nhà hiện có {len(grouped)} phòng: {', '.join(parts)}."

    # 2. Asking what devices are currently on
    asking_active_devices = _contains(
        text,
        "thiet bi nao dang bat",
        "thiet bi dang bat",
        "den nao dang bat",
        "co gi dang bat",
        "co thiet bi nao dang bat",
        "kiem tra thiet bi dang bat",
        "nhung den nao dang bat",
        "cac thiet bi dang bat",
    )
    if asking_active_devices:
        active = [
            d
            for d in devices
            if (d.kind in {"light", "aircon", "speaker"} and d.state.get("power"))
            or (d.kind == "blind" and (d.state.get("position", 0) or 0) > 0)
        ]
        if active:
            return f"Hiện có {len(active)} thiết bị đang bật: {', '.join(d.name for d in active)}."
        return "Hiện tại không có thiết bị nào đang bật trong nhà."

    # 3. Asking about devices in a specific room
    asking_room_devices = _contains(
        text,
        "co bao nhieu thiet bi",
        "bao nhieu thiet bi",
        "co may thiet bi",
        "may thiet bi",
        "co nhung thiet bi",
        "co thiet bi nao",
        "co thiet bi gi",
        "nhung thiet bi nao",
        "cac thiet bi nao",
        "thiet bi nao",
        "thiet bi gi",
        "co nhung gi",
        "co gi nao",
        "co nhung thu gi",
        "gom nhung gi",
        "danh sach thiet bi",
        "cac thiet bi trong",
        "kiem tra phong",
        "trong phong co gi",
        "o phong co gi",
    ) or bool(re.search(r"\bco\s+(?:nhung\s+)?(?:thiet\s+bi|gi|cai\s+gi)(?:\s+nao|\s+gi)?\b", text))

    if asking_room_devices:
        all_rooms = {d.room for d in devices}
        for room_name in all_rooms:
            norm_room = _normalize(room_name)
            short_room = norm_room.replace("phong ", "").strip()
            room_matched = _contains(text, norm_room) or (
                short_room
                and _contains(
                    text, f"phong {short_room}", f"o {short_room}", f"trong {short_room}", f"cua {short_room}"
                )
            )
            if room_matched:
                room_devs = [d for d in devices if d.room.strip().lower() == room_name.strip().lower()]
                if not room_devs:
                    return f"{room_name} hiện chưa có thiết bị nào."
                descs = [_format_device_brief(d) for d in room_devs]
                return f"{room_name} hiện có {len(room_devs)} thiết bị: {', '.join(descs)}."

    # 4. Asking about sensors (nhiệt độ, độ ẩm, khí gas, ánh sáng, chuyển động)
    if _contains(text, "nhiet do", "bao nhieu do", "nong khong", "lanh khong", "thoi tiet trong nha"):
        temp_sensors = [d for d in devices if d.kind == "sensor" and "temperature" in d.state]
        if temp_sensors:
            s = temp_sensors[0]
            temp = s.state.get("temperature", 0)
            hum = s.state.get("humidity")
            hum_str = f", độ ẩm {hum}%" if hum is not None else ""
            return f"Nhiệt độ hiện tại là {temp}°C{hum_str} (đo tại {s.room})."
        return "Hiện tại không tìm thấy cảm biến nhiệt độ nào trong nhà."

    if _contains(text, "do am"):
        hum_sensors = [d for d in devices if d.kind == "sensor" and "humidity" in d.state]
        if hum_sensors:
            s = hum_sensors[0]
            return f"Độ ẩm hiện tại là {s.state.get('humidity')}% tại {s.room}."
        return "Hiện tại không tìm thấy cảm biến độ ẩm nào trong nhà."

    if _contains(text, "khi gas", "ro ri gas", "nong do gas", "ro ri khi"):
        gas_sensors = [(d, sensor_reading(d, "gas")) for d in devices]
        gas_sensors = [(d, reading) for d, reading in gas_sensors if reading is not None]
        if gas_sensors:
            s, gas = gas_sensors[0]
            alert = gas["alarm"]
            status_text = "CẢNH BÁO: Phát hiện rò rỉ khí gas!" if alert else "Bình thường (an toàn)"
            return f"Nồng độ khí gas hiện tại: {gas['value']} {gas['unit'] or ''} — Trạng thái: {status_text}."
        return "Hiện tại không tìm thấy cảm biến khí gas nào trong nhà."

    return None


def _is_status_request(text: str) -> bool:
    state_action = r"(?:bat|tat|mo|dong|khoa)"
    status_suffix = r"(?:roi|chua|khong)(?:\s+(?:a|ha|vay|sao|nhi))?"
    if re.search(rf"\b{state_action}\s+{status_suffix}$", text):
        return True
    if _contains(text, "sao roi", "the nao roi", "hien gio", "hien tai"):
        return True
    observed = re.search(rf"\b(?:da|dang|con|hien dang)\s+{state_action}\b", text)
    if not observed:
        return False
    remaining = f"{text[: observed.start()]} {text[observed.end() :]}"
    remaining_without_question_particle = re.sub(r"\b(?:a|ha|vay|sao|nhi)\b", " ", remaining)
    return _power_action(remaining_without_question_particle) is None and not _has_adjustment_cue(remaining_without_question_particle)


def _is_deferred_request(text: str) -> bool:
    if _contains(text, "bay gio", "ngay bay gio", "lam ngay"):
        return False
    return _contains(
        text,
        "lat nua",
        "chut nua",
        "toi nay",
        "dem nay",
        "sang mai",
        "ngay mai",
        "trua mai",
        "chieu mai",
        "toi mai",
        "hom sau",
        "cuoi tuan",
    ) or bool(
        re.search(r"\b(?:luc|vao luc)\s+\d{1,2}(?:\s*gio)?\b", text)
        or re.search(r"\bsau\s+\d{1,3}\s+(?:phut|gio)\b", text)
        or re.search(r"\b(?:khi|den khi)\b.+\b(?:bat|tat|mo|dong|keo|khoa)\b", text)
        or re.search(r"\b(?:bat|tat|mo|dong|keo|khoa)\b.+\b(?:khi|den khi)\b", text)
    )


def _clarification_reply(text: str) -> str:
    if (
        _has_adjustment_cue(text)
        and _device_ids(text)
        and re.search(r"\b\d{1,3}\s*(?:%|phan\s+tram|do)\b", text)
        and _number(text, 0, 100) is None
    ):
        return "Mức hoặc giá trị yêu cầu chưa hợp lệ; bạn vui lòng chọn giá trị trong phạm vi thiết bị hỗ trợ."
    if _contains(text, "den", "bong den", "anh sang", "sang len", "toi di"):
        rooms = list(dict.fromkeys(device.room for device in _active_registry().list() if device.kind == "light"))
        if rooms:
            room_choices = rooms[0].lower() if len(rooms) == 1 else f"{rooms[0].lower()} hay {rooms[1].lower()}"
            if len(rooms) > 2:
                room_choices += f", hoặc {', '.join(room.lower() for room in rooms[2:])}"
            return f"Bạn muốn điều khiển đèn ở {room_choices}?"
        return "Bạn muốn điều khiển đèn nào?"
    if _contains(text, "cua chinh", "khoa cua", "o khoa"):
        return "Bạn muốn kiểm tra hay khóa cửa chính? Mở khóa cần xác nhận trong ứng dụng."
    if _has_display_message_cue(text):
        display_rooms = sorted({device.room for device in _active_registry().list() if device.kind == "display"})
        if not display_rooms:
            return "Mình chưa tìm thấy màn hình nào để hiển thị thông báo."
        return f"Bạn muốn hiển thị thông báo trên màn hình ở: {', '.join(display_rooms)}?"
    if _contains(text, "loa", "am luong", "speaker"):
        speaker_rooms = sorted({device.room for device in _active_registry().list() if device.kind == "speaker"})
        if not speaker_rooms:
            return "Registry hiện chưa có loa nào để điều khiển."
        return f"Mình không tìm thấy loa phù hợp. Loa hiện có ở: {', '.join(speaker_rooms)}."
    return "Mình chưa xác định đủ thiết bị, thao tác hoặc giá trị. Bạn vui lòng nói rõ hơn nhé."


def _missing_slot(text: str) -> MissingSlot:
    if not _device_ids(text):
        return "device"
    if _has_adjustment_cue(text):
        return "value"
    return "action"


def _is_cancel_request(text: str) -> bool:
    return _contains(text, "thoi", "bo di", "huy", "huy bo")


def _is_guide_request(text: str) -> bool:
    """Keep troubleshooting and manual questions on the retrieval-capable path."""
    guide_cue = _contains(
        text,
        "huong dan",
        "tai lieu",
        "so tay",
        "khac phuc",
        "sua loi",
        "loi",
        "cach dat lai",
        "cach reset",
        "ket noi lai",
    )
    question_cue = "?" in text or _contains(text, "cach", "lam sao", "the nao", "tai sao", "vi sao")
    retrieval_cue = _contains(text, "tim huong dan", "tim tai lieu", "tra cuu huong dan", "xem huong dan")
    return guide_cue and (question_cue or retrieval_cue)


def _has_context_reference(text: str) -> bool:
    return _contains(
        text,
        "no",
        "cai do",
        "thiet bi do",
        "den do",
        "loa do",
        "dieu hoa do",
        "may lanh do",
        "rem do",
    )


def _contextual_control_fragment(text: str) -> bool:
    return not _device_ids(text) and (
        _power_action(text) is not None
        or _has_action_word(text)
        or _has_adjustment_cue(text)
        or _is_status_request(text)
    )


def _matches_missing_slot(text: str, missing_slot: MissingSlot) -> bool:
    if missing_slot == "device":
        return bool(_device_ids(text)) or _contains(
            text,
            "phong khach",
            "phong ngu",
            "cho ngu",
            "phong ngoai",
            "cua chinh",
        )
    if missing_slot == "value":
        return _number(text, 0, 100) is not None or _contains(text, "mot nua", "phan nua")
    return _power_action(text) is not None or _has_action_word(text)


def _with_device_context(query: str, device_id: str) -> str | None:
    device = _active_registry().get(device_id)
    return f"{device.name} {query}" if device else None


def _unsafe_non_command(text: str) -> str | None:
    if _contains(text, "mo khoa", "mo chot", "mo cua", "unlock"):
        return "Mở khóa cần được tạo và xác nhận trong ứng dụng Homing Hub."
    if _contains(
        text,
        "neu",
        "gia su",
        "vi du",
        "cau lenh",
        "cau noi",
        "cum tu",
        "trich dan",
        "nghia la gi",
        "co nghia gi",
        "toi noi",
        "ban noi",
        "nhac lai",
        "doc lai",
        "viet lai",
        "se lam gi",
        "co the",
        "duoc khong",
    ):
        return "Mình chưa thực hiện vì đây là câu hỏi hoặc tình huống giả định."
    if _is_deferred_request(text):
        return "Mình chưa thực hiện ngay vì yêu cầu có thời điểm hoặc điều kiện trong tương lai. Bạn vui lòng dùng tính năng lịch tự động."
    if _is_status_request(text) or re.search(r"\b(?:da|co)\s+(?:bat|tat|mo|dong|khoa)\b", text):
        return _state_reply(text)
    if re.search(
        r"\b(?:dung|khong|chua|khoi)\s+(?:(?:co|can|duoc|hay)\s+)?(?:bat|tat|mo|dong|keo|khoa)\b",
        text,
    ):
        return "Mình hiểu đây là câu phủ định nên không thay đổi thiết bị."
    return None


def _power_action(text: str) -> str | None:
    action_text = re.sub(r"\bdang bat\b", "", text)
    off_match = re.search(r"\b(?:tat|ngung|dung lai|cho nghi|toi di)\b", action_text)
    on_match = re.search(r"\b(?:bat|mo|khoi dong|cho chay|kich hoat|sang len)\b", action_text)
    if off_match and not on_match:
        return "off"
    if on_match and not off_match:
        return "on"
    return None


def _room_scope_matches(text: str) -> set[str]:
    """Resolve only room names that are present in the active registry."""
    matches: set[str] = set()
    for room in {device.room for device in _active_registry().list()}:
        normalized = _normalize(room)
        short = normalized.removeprefix("phong ").strip()
        if _contains(text, normalized) or (short and _contains(text, f"phong {short}", f"o {short}", f"trong {short}")):
            matches.add(room)
    return matches


_TOPOLOGY_SCOPE_REFERENCE = re.compile(r"\b(?:phong|tang|floor|khu|area|zone)\s+[a-z0-9]+\b", re.I)


def _has_unknown_topology_scope(text: str) -> bool:
    """Reject an explicit area/floor reference that cannot be grounded in the registry."""
    known_rooms = {_normalize(room) for room in {device.room for device in _active_registry().list()}}
    for match in _TOPOLOGY_SCOPE_REFERENCE.finditer(text):
        scope = match.group(0)
        if scope in known_rooms:
            continue
        if scope.startswith("phong ") and f"phong {scope.removeprefix('phong ').strip()}" in known_rooms:
            continue
        return True
    return False


def _blind_action(text: str, device: Device) -> str | None:
    """Map curtain vocabulary to runtime open/close capabilities when available."""
    reg = _active_registry()
    if device.kind != "blind":
        return None
    if _contains(text, "dong", "dong lai", "dong kin", "keo xuong", "tha xuong"):
        return "close" if reg.supports(device, "close") else "set"
    if _contains(text, "mo", "mo ra", "mo het", "keo len", "cuon len") or re.search(r"\b(?:keo|cuon)\b.*\blen\b", text):
        return "open" if reg.supports(device, "open") else "set"
    return None


def _device_ids(text: str) -> list[str]:
    devices = _active_registry().list()
    direct = [
        device.id
        for device in devices
        if any(
            candidate and candidate in text
            for candidate in (
                _normalize(device.id),
                _normalize(device.name),
            )
        )
    ]
    if direct:
        return list(dict.fromkeys(direct))

    kind_aliases = {
        "light": ("den", "bong den", "anh sang"),
        "fan": ("quat", "fan"),
        "aircon": ("dieu hoa", "may lanh", "aircon"),
        "blind": ("rem", "man cua", "blind"),
        "speaker": ("loa", "am luong", "speaker"),
        "lock": ("khoa cua", "chot cua", "o khoa", "lock"),
        "sensor": ("cam bien", "sensor"),
        "display": ("man hinh", "display"),
    }
    mentioned_kinds = {kind for kind, aliases in kind_aliases.items() if _contains(text, *aliases)}
    mentioned_rooms = {
        device.room
        for device in devices
        if any(
            _contains(text, alias)
            for alias in {
                _normalize(device.room),
                *{part for part in _normalize(device.room).split() if part not in {"phong", "cho", "loi", "khu"}},
            }
        )
    }

    def matches_kind(device: Device) -> bool:
        if not mentioned_kinds or device.kind in mentioned_kinds:
            return True
        # A climate appliance can represent a fan only when its live
        # capability contract explicitly exposes the fan mode and there is no
        # actual fan entity in the requested scope.  This remains topology- and
        # capability-driven rather than assuming a particular device ID.
        if mentioned_kinds != {"fan"} or device.kind != "aircon":
            return False
        scoped = [candidate for candidate in devices if not mentioned_rooms or candidate.room in mentioned_rooms]
        if any(candidate.kind == "fan" for candidate in scoped):
            return False
        mode_schema = _active_registry().capabilities(device).get("set_fields", {}).get("mode", {})
        return isinstance(mode_schema, dict) and "fan" in mode_schema.get("enum", ())

    matches = [
        device.id
        for device in devices
        if matches_kind(device)
        and (not mentioned_rooms or device.room in mentioned_rooms)
    ]
    # A display message changes state and must have an explicit target.  Do
    # not silently pick the only currently registered screen: deployments may
    # discover more displays later, and the user-facing contract requires an
    # explicit room/device for this mutation.
    if mentioned_kinds == {"display"} and not mentioned_rooms and _has_display_message_cue(text):
        return []
    if not mentioned_rooms and len(matches) > 1:
        return []
    return matches if len(matches) == 1 else []


def _set_command(device_id: str, text: str) -> ParsedCommand | None:
    reg = _active_registry()
    device = reg.get(device_id)
    if device is None:
        return None

    if device.kind == "display" and reg.supports(device, "set"):
        message = _display_message(text)
        if message is not None:
            return ParsedCommand(device_id, "set", {"message": message})

    if device.kind == "aircon" and _contains(text, "quat", "fan"):
        scoped_devices = [candidate for candidate in reg.list() if candidate.room == device.room]
        mode_schema = reg.capabilities(device).get("set_fields", {}).get("mode", {})
        fan_mode_supported = isinstance(mode_schema, dict) and "fan" in mode_schema.get("enum", ())
        if fan_mode_supported and not any(candidate.kind == "fan" for candidate in scoped_devices):
            # Preserve the action contract for power commands.  The caller's
            # normal action branch below emits ``on``/``off``; mode=fan is only
            # needed when the request is explicitly about choosing a mode.
            if _power_action(text) is None:
                return ParsedCommand(device_id, "set", {"mode": "fan"})

    if device.kind == "aircon" and "target_temperature" in reg.capabilities(device).get("set_fields", {}):
        temperature = _number(text, 16, 30)
        if temperature is None:
            current = device.state.get("target_temperature")
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                if _contains(text, "lanh hon", "giam nhiet", "ha nhiet"):
                    temperature = max(16, round(current - 1))
                elif _contains(text, "am hon", "nong hon", "tang nhiet"):
                    temperature = min(30, round(current + 1))
        if temperature is not None:
            return ParsedCommand(device_id, "set", {"target_temperature": temperature})

    if device.kind == "light" and "brightness" in reg.capabilities(device).get("set_fields", {}):
        brightness_cue = _contains(
            text,
            "do sang",
            "muc sang",
            "phan tram",
            "sang hon",
            "mo hon",
            "giam sang",
            "giam xuong",
            "tang len",
            "con",
        )
        brightness = _number(text, 0, 100) if brightness_cue or "%" in text else None
        if brightness is None:
            if _contains(text, "mo hon", "giam sang", "bot sang"):
                brightness = _bounded_step(device_id, "brightness", -10)
            elif _contains(text, "sang hon", "tang sang"):
                brightness = _bounded_step(device_id, "brightness", 10)
        if brightness is not None:
            return ParsedCommand(device_id, "set", {"brightness": brightness})

    if device.kind == "speaker" and "volume" in reg.capabilities(device).get("set_fields", {}):
        volume_cue = _contains(
            text,
            "am luong",
            "muc",
            "nho hon",
            "to hon",
            "nho xuong",
            "be lai",
            "be tieng",
            "nho tieng",
            "van nho",
            "van to",
            "van loa nho",
            "van loa to",
            "to len",
            "giam am",
            "tang am",
        )
        volume = _number(text, 0, 100) if volume_cue or "%" in text else None
        if volume is None:
            if _contains(
                text,
                "nho hon",
                "nho xuong",
                "giam am",
                "be lai",
                "be tieng",
                "nho tieng",
                "van nho",
                "van loa nho",
            ):
                volume = _bounded_step(device_id, "volume", -10)
            elif _contains(text, "to hon", "to len", "tang am", "van to", "van loa to"):
                volume = _bounded_step(device_id, "volume", 10)
        if volume is not None:
            return ParsedCommand(device_id, "set", {"volume": volume})

    if device.kind == "blind" and "position" in reg.capabilities(device).get("set_fields", {}):
        if _contains(text, "mot nua", "phan nua", "50 phan tram"):
            position = 50
        else:
            position = _number(text, 0, 100) if "%" in text or _contains(text, "vi tri", "muc", "phan tram") else None
        if position is None:
            if _contains(text, "mo het", "mo rem", "mo man cua", "mo ra", "keo len", "cuon len"):
                position = 100
            elif _contains(text, "dong kin", "dong rem", "dong man cua", "dong lai", "keo xuong", "tha xuong"):
                position = 0
            elif _contains(text, "mo them", "len mot chut"):
                position = _bounded_step(device_id, "position", 10)
            elif _contains(text, "dong bot", "xuong mot chut"):
                position = _bounded_step(device_id, "position", -10)
        if position is not None:
            return ParsedCommand(device_id, "set", {"position": position})
    return None


def _commands_for_clause(text: str, fallback_ids: tuple[str, ...] = ()) -> list[ParsedCommand]:
    ids = _device_ids(text)
    if not ids and fallback_ids and (_power_action(text) is not None or _has_adjustment_cue(text)):
        ids = list(fallback_ids)
    commands: list[ParsedCommand] = []
    action = _power_action(text)
    reg = _active_registry()
    for device_id in ids:
        device = reg.get(device_id)
        if device is None:
            continue
        if device.kind == "lock":
            if _contains(text, "khoa", "khoa lai", "chot") and not _contains(text, "mo khoa", "mo chot"):
                commands.append(ParsedCommand(device_id, "lock"))
            continue
        set_command = _set_command(device_id, text)
        if set_command:
            commands.append(set_command)
            continue
        if blind_action := _blind_action(text, device):
            commands.append(ParsedCommand(device_id, blind_action))
            continue
        if action and reg.supports(device, action):
            commands.append(ParsedCommand(device_id, action))
    return commands


def _whole_home_commands(text: str) -> list[ParsedCommand] | None:
    action = _power_action(text)
    if action is None:
        return None
    all_lights = _contains(text, "tat ca den", "toan bo den", "het den", "moi den")
    all_devices = _contains(
        text,
        "tat ca thiet bi",
        "toan bo thiet bi",
        "moi thiet bi",
        "het thiet bi",
        "tat het",
        "bat het",
    )
    if not all_lights and not all_devices:
        return None
    reg = _active_registry()
    devices = reg.list()
    scoped_rooms = _room_scope_matches(text)
    if scoped_rooms:
        devices = [device for device in devices if device.room in scoped_rooms]
    if all_lights:
        devices = [device for device in devices if device.kind == "light"]
    else:
        devices = [device for device in devices if reg.supports(device, action)]
    if action == "off" and _contains(text, "dang bat"):
        devices = [device for device in devices if bool(device.state.get("power"))]
    return [ParsedCommand(device.id, action) for device in devices]


_CLAUSE_SEPARATOR = re.compile(r"[,;]|\b(?:và|va|rồi|roi|sau\s+đó|sau\s+do)\b", re.IGNORECASE)
_POWER_VERB_BOUNDARY = re.compile(
    r"\b(?:bật|bat|tắt|tat|mở|mo|đóng|dong|khởi\s+động|khoi\s+dong|dừng\s+lại|dung\s+lai|ngừng|ngung)\b",
    re.IGNORECASE,
)


def _split_control_clauses(query: str) -> list[str]:
    """Split independent imperative clauses before normalization removes punctuation."""
    clauses: list[str] = []
    for raw_clause in _CLAUSE_SEPARATOR.split(query):
        normalized = _normalize(raw_clause)
        if not normalized:
            continue
        if _is_status_request(normalized):
            clauses.append(normalized)
            continue
        starts = [
            match.start()
            for match in _POWER_VERB_BOUNDARY.finditer(normalized)
            if match.start() > 0 and normalized[: match.start()].strip() not in {"cho", "giup", "ho", "hay", "lam on"}
        ]
        boundaries = [0, *starts, len(normalized)]
        clauses.extend(
            normalized[boundaries[index] : boundaries[index + 1]].strip()
            for index in range(len(boundaries) - 1)
            if normalized[boundaries[index] : boundaries[index + 1]].strip()
        )
    return clauses


def _has_unresolved_explicit_control_target(clause: str, commands: list[ParsedCommand]) -> bool:
    """Prevent multi-command requests from applying only the resolvable subset."""
    if commands or (_power_action(clause) is None and not _has_adjustment_cue(clause)):
        return False
    if _has_device_mention(clause) or _has_unknown_topology_scope(clause):
        return True
    return bool(re.search(r"\b(?:den|quat|fan|may|loa|rem|blind|man|cua|thiet bi)\b", clause))


def parse_home_request(query: str, mode: str | None = None) -> ParsedHomeRequest:
    text = _normalize(query)
    if not text:
        return ParsedHomeRequest(False)

    if is_prompt_injection_attempt(query):
        return ParsedHomeRequest(
            True,
            reply="Mình không thể bỏ qua quy tắc an toàn hoặc thực hiện yêu cầu ghi đè chính sách.",
        )

    if is_absolute_calendar_schedule(query):
        return ParsedHomeRequest(
            True,
            reply=(
                "Mình không thể thực hiện lịch theo ngày hoặc giờ cụ thể qua chat. "
                "Bạn có thể dùng tính năng lịch tự động trong Homing Hub hoặc hẹn giờ đếm ngược."
            ),
        )

    if _is_guide_request(text):
        return ParsedHomeRequest(False)

    if topology_reply := _room_topology_reply(text, mode=mode):
        return ParsedHomeRequest(True, reply=topology_reply)

    has_control_language = (
        _power_action(text) is not None
        or _has_action_word(text)
        or _has_adjustment_cue(text)
        or (_has_device_mention(text) and _has_display_message_cue(text))
        or _is_status_request(text)
    )
    control_cue = (_has_device_mention(text) and has_control_language) or _contains(
        text,
        "tat ca thiet bi",
        "toan bo thiet bi",
        "het thiet bi",
        "tat ca den",
        "toan bo den",
        "het den",
        "tat het",
        "bat het",
        "mo khoa",
        "mo cua",
    )
    if not control_cue:
        return ParsedHomeRequest(False)
    if unsafe_reply := _unsafe_non_command(text):
        device_ids = tuple(_device_ids(text))
        status_request = _is_status_request(text) or bool(re.search(r"\b(?:da|co)\s+(?:bat|tat|mo|dong|khoa)\b", text))
        return ParsedHomeRequest(
            True,
            reply=unsafe_reply,
            missing_slot="device" if status_request and len(device_ids) != 1 else None,
            referenced_device_ids=device_ids if status_request and len(device_ids) == 1 else (),
        )

    if _has_unknown_topology_scope(text):
        return ParsedHomeRequest(
            True,
            reply=(
                "Mình không thể thực hiện vì khu vực được nêu không được hỗ trợ "
                "trong sơ đồ nhà hiện tại; chưa thay đổi thiết bị nào."
            ),
        )

    whole_home = _whole_home_commands(text)
    if whole_home is not None:
        reply = "Không có thiết bị nào đang bật." if not whole_home else ""
        return ParsedHomeRequest(
            True,
            tuple(whole_home),
            reply,
            referenced_device_ids=tuple(command.device_id for command in whole_home),
        )

    clauses = _split_control_clauses(query)
    commands: list[ParsedCommand] = []
    if len(clauses) > 1:
        sole_action = _power_action(text)
        previous_ids: tuple[str, ...] = ()
        unresolved_clause = False
        for clause in clauses:
            clause_text = clause
            if _contains(text, "den", "anh sang") and not _contains(clause, "den", "anh sang"):
                if _contains(clause, "phong ngu", "cho ngu", "phong khach", "phong ngoai"):
                    clause_text = f"den {clause_text}"
            if sole_action and _power_action(clause) is None:
                clause_text = f"{'bat' if sole_action == 'on' else 'tat'} {clause_text}"
            explicit_ids = tuple(_device_ids(clause_text))
            if not explicit_ids and _has_unresolved_explicit_control_target(clause_text, []):
                unresolved_clause = True
                continue
            clause_commands = _commands_for_clause(clause_text, previous_ids)
            commands.extend(clause_commands)
            if explicit_ids:
                previous_ids = explicit_ids
            elif clause_commands:
                previous_ids = tuple(dict.fromkeys(command.device_id for command in clause_commands))
        if unresolved_clause:
            return ParsedHomeRequest(
                True,
                reply="Mình chưa xác định được đầy đủ tất cả thiết bị trong yêu cầu nhiều thao tác nên chưa thay đổi thiết bị nào.",
            )
    else:
        commands = _commands_for_clause(text)

    deduplicated: list[ParsedCommand] = []
    seen: set[tuple[str, str, str]] = set()
    for command in commands:
        key = (command.device_id, command.action, repr(command.value))
        if key not in seen:
            deduplicated.append(command)
            seen.add(key)
    actions_by_device: dict[str, set[str]] = {}
    for command in deduplicated:
        if command.action in {"on", "off", "toggle"}:
            actions_by_device.setdefault(command.device_id, set()).add(command.action)
    if any(len(actions) > 1 for actions in actions_by_device.values()):
        return ParsedHomeRequest(
            True,
            reply="Yêu cầu có thao tác bật/tắt mâu thuẫn cho cùng một thiết bị. Bạn vui lòng nói rõ trạng thái cuối cùng.",
        )
    if not deduplicated:
        device_ids = tuple(_device_ids(text))
        return ParsedHomeRequest(
            True,
            reply=_clarification_reply(text),
            missing_slot=_missing_slot(text),
            referenced_device_ids=device_ids,
        )
    if len(deduplicated) > 5:
        return ParsedHomeRequest(True, reply="Mỗi lượt chỉ thay đổi tối đa 5 thiết bị; bạn vui lòng chia nhỏ yêu cầu.")
    return ParsedHomeRequest(
        True,
        tuple(deduplicated),
        referenced_device_ids=tuple(dict.fromkeys(command.device_id for command in deduplicated)),
    )


def informational_remainder(query: str) -> str:
    """Return question clauses that deterministic device handling cannot answer."""
    clauses = [
        part.strip() for part in re.split(r"\b(?:và|rồi|sau đó)\b|[,;]", query, flags=re.IGNORECASE) if part.strip()
    ]
    if len(clauses) < 2:
        return ""
    unanswered: list[str] = []
    for clause in clauses:
        normalized = _normalize(clause)
        is_question = "?" in clause or _contains(
            normalized,
            "la gi",
            "tai sao",
            "vi sao",
            "the nao",
            "bao nhieu",
            "o dau",
            "ai",
            "chua",
        )
        if is_question and not parse_home_request(clause).handled:
            unanswered.append(clause)
    return " và ".join(unanswered)


def should_handle_natural_home_request(
    query: str,
    session_id: str | None = None,
    mode: str | None = None,
) -> bool:
    if route_information_request(query, mode) is not None:
        return True
    plan = parse_home_request(query, mode=mode)
    if plan.handled or not session_id:
        return plan.handled
    text = _normalize(query)
    snapshot = conversations.snapshot(session_id, mode=mode)
    if snapshot.pending and (_is_cancel_request(text) or _matches_missing_slot(text, snapshot.pending.missing_slot)):
        return True
    return bool(snapshot.last_device_ids) and _contextual_control_fragment(text)


def _success_text(command: ParsedCommand, device_name: str) -> str:
    if command.action == "on":
        return f"Đã bật {device_name}"
    if command.action == "off":
        return f"Đã tắt {device_name}"
    if command.action == "lock":
        return f"Đã khóa {device_name}"
    value = command.value or {}
    if "target_temperature" in value:
        return f"Đã đặt {device_name} ở {value['target_temperature']}°C"
    if "brightness" in value:
        return f"Đã đặt độ sáng {device_name} ở {value['brightness']}%"
    if "volume" in value:
        return f"Đã đặt âm lượng {device_name} ở {value['volume']}%"
    if "position" in value:
        return f"Đã mở {device_name} ở {value['position']}%"
    return f"Đã cập nhật {device_name}"


async def handle_natural_home_request(
    query: str,
    session_id: str | None = None,
    mode: str | None = None,
) -> dict[str, Any] | None:
    if route := route_information_request(query, mode):
        return execute_information_route(route)
    plan = parse_home_request(query, mode=mode)
    pending_query = query
    if session_id:
        text = _normalize(query)
        snapshot = conversations.snapshot(session_id, mode=mode)
        if snapshot.pending and _is_cancel_request(text):
            conversations.set_pending(session_id, None, mode=mode)
            return {
                "response": "Mình đã hủy yêu cầu đang chờ; chưa thay đổi thiết bị.",
                "analysis": "deterministic_command_guard",
                "metadata": {"commands": []},
            }

        if snapshot.pending and not plan.handled and _matches_missing_slot(text, snapshot.pending.missing_slot):
            pending_query = snapshot.pending.query
            plan = parse_home_request(f"{snapshot.pending.query} {query}", mode=mode)

        use_last_device = (not plan.handled and _contextual_control_fragment(text)) or (
            plan.missing_slot == "device" and _has_context_reference(text)
        )
        if use_last_device and len(snapshot.last_device_ids) == 1:
            contextual_query = _with_device_context(query, snapshot.last_device_ids[0])
            if contextual_query:
                plan = parse_home_request(contextual_query, mode=mode)
        elif use_last_device and len(snapshot.last_device_ids) > 1:
            conversations.set_pending(session_id, PendingClarification(query, "device"), mode=mode)
            return {
                "response": "Mình đang có nhiều thiết bị trong ngữ cảnh; bạn vui lòng nói rõ thiết bị.",
                "analysis": "deterministic_command_guard",
                "metadata": {"commands": []},
            }

    if not plan.handled:
        return None
    if not plan.commands:
        if session_id:
            conversations.set_pending(
                session_id,
                PendingClarification(pending_query, plan.missing_slot) if plan.missing_slot else None,
                mode=mode,
            )
            if len(plan.referenced_device_ids) == 1:
                conversations.set_last_devices(session_id, plan.referenced_device_ids, mode=mode)
        return {
            "response": plan.reply or "Mình chưa xác định đủ thiết bị và thao tác để thực hiện.",
            "analysis": "deterministic_command_guard",
            "metadata": {"commands": []},
        }

    if session_id:
        conversations.set_pending(session_id, None, mode=mode)
        conversations.set_last_devices(session_id, plan.referenced_device_ids, mode=mode)

    successful: list[str] = []
    failed: list[str] = []
    devices: list[dict[str, Any]] = []
    # Preserve order for requests such as "bật điều hòa và đặt 24 độ".
    for command in plan.commands:
        if mode is not None:
            try:
                device, error = await asyncio.to_thread(
                    control_device,
                    command.device_id,
                    command.action,
                    command.value,
                    mode=mode,
                    registry=_active_registry(mode),
                )
            except TypeError:
                device, error = await asyncio.to_thread(
                    control_device,
                    command.device_id,
                    command.action,
                    command.value,
                )
        else:
            device, error = await asyncio.to_thread(
                control_device,
                command.device_id,
                command.action,
                command.value,
            )
        if error or not device:
            failed.append(f"{command.device_id}: {error or 'không có xác nhận'}")
            continue
        devices.append(device.model_dump())
        successful.append(_success_text(command, device.name))

    parts: list[str] = []
    if successful:
        parts.append("; ".join(successful) + ".")
    if failed:
        parts.append("Chưa thực hiện: " + "; ".join(failed) + ".")
    return {
        "response": " ".join(parts),
        "analysis": "deterministic_natural_language_control",
        "metadata": {
            "commands": [command.as_dict() for command in plan.commands],
            "devices": devices,
        },
    }
