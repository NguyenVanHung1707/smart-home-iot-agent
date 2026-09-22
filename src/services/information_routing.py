"""Registry-grounded, read-only routing for high-confidence home questions."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from src.agents.tool_routing import is_prompt_injection_attempt
from src.agents.tools.runtime import get_runtime_tools
from src.services.devices import get_registry


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9?]+", " ", plain)).strip()


def _contains(text: str, *phrases: str) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


@dataclass(frozen=True, slots=True)
class InformationRoute:
    name: str
    args: dict[str, Any]


def _mentioned_room(text: str, mode: str | None) -> str | None:
    for room in {device.room for device in get_registry(mode).list()}:
        normalized = _normalize(room)
        if normalized and normalized in text:
            return room
    return None


def route_information_request(query: str, mode: str | None = None) -> InformationRoute | None:
    """Select one read-only runtime tool only for unambiguous query families."""
    text = _normalize(query)
    if not text or is_prompt_injection_attempt(query):
        return None
    if _contains(text, "hen gio", "timer") and _contains(text, "dang", "hien tai", "con chay", "hoat dong"):
        return InformationRoute("list_device_timers", {"active_only": True})
    if _contains(text, "an ninh", "bao mat", "bao cao an toan", "kiem tra an toan"):
        return InformationRoute("get_security_report", {"include_sensors": True, "include_locks": True})
    guide = _contains(text, "huong dan", "tai lieu", "so tay", "khac phuc", "sua loi", "cach reset", "cach dat lai")
    retrieve = _contains(text, "tim huong dan", "tim tai lieu", "tra cuu", "cach", "lam sao", "the nao", "tai sao") or "?" in text
    if guide and retrieve:
        return InformationRoute("search_home_guides", {"query": query.strip()})
    if _contains(text, "rem", "man cua", "blind") and _contains(text, "dang", "trang thai", "mo bao nhieu", "dong chua", "mo chua", "?"):
        if room := _mentioned_room(text, mode):
            return InformationRoute("get_room_devices", {"room": room})
    inventory = _contains(text, "danh sach thiet bi", "thiet bi nao", "co nhung thiet bi", "nha co bao nhieu phong", "toan bo thiet bi") and not _contains(
        text, "dang bat", "dang tat", "bat chua", "tat chua"
    )
    if inventory:
        return InformationRoute("get_room_devices", {"room": _mentioned_room(text, mode)})
    return None


def execute_information_route(route: InformationRoute) -> dict[str, Any]:
    """Invoke exactly the selected read-only runtime tool and retain its evidence."""
    tool = next((candidate for candidate in get_runtime_tools() if candidate.name == route.name), None)
    if tool is None:
        payload: dict[str, Any] = {"status": "invalid_request", "message": "Read-only tool is unavailable."}
    else:
        try:
            payload = json.loads(str(tool.invoke(route.args)))
        except Exception as error:
            payload = {"status": "failed", "message": str(error)}
    message = str(payload.get("message", ""))
    if route.name == "get_room_devices" and payload.get("room") and isinstance(payload.get("devices"), list):
        room = str(payload["room"])
        devices = payload["devices"]
        names = ", ".join(str(device.get("name", "")) for device in devices if isinstance(device, dict))
        message = f"{room} hiện có {len(devices)} thiết bị: {names}."
    elif route.name == "get_room_devices" and isinstance(payload.get("topology"), dict):
        topology = payload["topology"]
        rooms = ", ".join(f"{room} ({len(devices)} thiết bị)" for room, devices in topology.items())
        message = f"Ngôi nhà hiện có {len(topology)} phòng: {rooms}."
    if route.name == "search_home_guides" and payload.get("results"):
        message = str(payload["results"][0].get("content", message))
    result = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "response": message or "Đã tra cứu thông tin theo yêu cầu.",
        "metadata": {
            "commands": [],
            "tool_calls": [{"name": route.name, "args": route.args}],
            "tool_results": [{"name": route.name, "args": route.args, "result": result}],
        },
    }
