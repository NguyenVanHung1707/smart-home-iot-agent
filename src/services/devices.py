"""Persistent device registry and runtime capability authority."""

from __future__ import annotations

import json
import logging
import math
import time
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from src.models.schemas import Device
from src.services.device_types import default_capabilities

logger = logging.getLogger(__name__)

_CURRENT_DATA_MODE: ContextVar[str] = ContextVar("current_data_mode", default="simulator")


def get_active_data_mode() -> str:
    return _CURRENT_DATA_MODE.get()


def set_active_data_mode(mode: str | None) -> None:
    norm = (mode or "simulator").strip().lower()
    _CURRENT_DATA_MODE.set("real" if norm in {"real", "live", "hardware"} else "simulator")


_VIRTUAL_DEVICE_IDS = {"hub-speaker", "living-aircon", "living-blind"}

_SENSOR_METRICS: dict[str, dict[str, Any]] = {
    "gas": {"fields": ("gas", "gas_level", "ppm"), "unit": "ppm", "alarm_fields": ("gas_detected", "alert")},
    "temperature": {"fields": ("temperature",), "unit": "°C", "alarm_fields": ()},
    "humidity": {"fields": ("humidity",), "unit": "%", "alarm_fields": ()},
    "motion": {"fields": ("motion",), "unit": None, "alarm_fields": ()},
    "light": {"fields": ("light", "light_level", "lux"), "unit": "lux", "alarm_fields": ()},
}


def sensor_reading(device: Device, metric: str) -> dict[str, Any] | None:
    """Return one semantic sensor reading from a device's telemetry contract.

    A device may declare ``capabilities.telemetry`` as a mapping from the
    semantic metric (for example ``gas``) to ``field``, ``unit`` and optional
    ``alarm_field``.  This is authoritative when present.  Older devices are
    read through compatible state-field contracts, so simulator and firmware
    telemetry can evolve independently of user-facing features.
    """
    if device.kind != "sensor" or metric not in _SENSOR_METRICS:
        return None

    state = device.state or {}
    defaults = _SENSOR_METRICS[metric]
    telemetry = device.capabilities.get("telemetry", {}) if isinstance(device.capabilities, dict) else {}
    declared = telemetry.get(metric) if isinstance(telemetry, dict) else None
    if isinstance(declared, str):
        declared = {"field": declared}
    declared = declared if isinstance(declared, dict) else {}

    field = declared.get("field") or declared.get("value_field")
    candidates = (str(field),) if isinstance(field, str) else defaults["fields"]
    value_field = next((candidate for candidate in candidates if candidate in state), None)
    if value_field is None:
        return None

    alarm_field = declared.get("alarm_field")
    if isinstance(alarm_field, str) and alarm_field in state:
        alarm: bool | None = bool(state[alarm_field])
    elif metric == "gas":
        alarm = next((bool(state[name]) for name in defaults["alarm_fields"] if name in state), None)
    else:
        alarm = None
    return {
        "metric": metric,
        "value": state[value_field],
        "field": value_field,
        "unit": declared.get("unit", defaults["unit"]),
        "alarm": alarm,
    }


def sensor_readings(device: Device) -> dict[str, dict[str, Any]]:
    """Return all semantic readings that can be resolved for a sensor."""
    return {metric: reading for metric in _SENSOR_METRICS if (reading := sensor_reading(device, metric)) is not None}

_HARDWARE_NODE_GROUPS: dict[str, set[str]] = {
    "esp32_home_appliances": {
        "living-light",
        "bedroom-light",
        "kitchen-light",
        "living-fan",
        "bedroom-fan",
        "kitchen-fan",
        "living-temperature",
        "kitchen-gas",
        "living-light-sensor",
        "living-motion",
        "living-display",
        "living-blind",
        "window-servo",
    },
    "esp32_main_entrance": {
        "entry-lock",
        "entry-sensor",
    },
}


def get_node_device_ids(device_id: str, existing_ids: Any | None = None) -> list[str]:
    """Return all device IDs sharing the same physical microcontroller node."""
    for node_name, group in _HARDWARE_NODE_GROUPS.items():
        if device_id == node_name or device_id in group:
            if existing_ids is not None:
                return [d for d in group if d in existing_ids]
            return list(group)
    return [device_id]


def _valid_field_value(value: Any, schema: dict[str, Any]) -> bool:
    expected_type = schema.get("type")
    if expected_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
    elif expected_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
    elif expected_type == "string":
        if not isinstance(value, str):
            return False
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            return False
    else:
        return False

    if isinstance(value, float) and not math.isfinite(value):
        return False
    if "minimum" in schema and value < schema["minimum"]:
        return False
    if "maximum" in schema and value > schema["maximum"]:
        return False
    if "max_length" in schema and isinstance(value, str) and len(value) > schema["max_length"]:
        return False
    return "enum" not in schema or value in schema["enum"]


_DEFAULT_REAL_DEVICES: list[dict[str, Any]] = [
    {
        "id": "living-light",
        "name": "Đèn phòng khách",
        "room": "Phòng khách",
        "kind": "light",
        "online": False,
        "state": {"power": False, "brightness": 100},
    },
    {
        "id": "living-fan",
        "name": "Quạt phòng khách",
        "room": "Phòng khách",
        "kind": "fan",
        "online": False,
        "state": {"power": False, "speed": 0},
    },
    {
        "id": "living-temperature",
        "name": "Cảm biến nhiệt độ",
        "room": "Phòng khách",
        "kind": "sensor",
        "online": False,
        "state": {"temperature": 28.0, "humidity": 65.0},
    },
    {
        "id": "living-light-sensor",
        "name": "Cảm biến ánh sáng",
        "room": "Phòng khách",
        "kind": "sensor",
        "online": False,
        "state": {"light_level": 500, "is_dark": False},
    },
    {
        "id": "living-motion",
        "name": "Cảm biến chuyển động",
        "room": "Phòng khách",
        "kind": "sensor",
        "online": False,
        "state": {"motion": False},
    },
    {
        "id": "living-display",
        "name": "Màn hình OLED phòng khách",
        "room": "Phòng khách",
        "kind": "display",
        "online": False,
        "state": {"power": True, "message": "Homing Hub Ready"},
    },
    {
        "id": "living-blind",
        "name": "Cửa sổ thông gió",
        "room": "Phòng khách",
        "kind": "blind",
        "online": False,
        "state": {"position": 0, "power": False},
    },
    {
        "id": "bedroom-light",
        "name": "Đèn phòng ngủ",
        "room": "Phòng ngủ",
        "kind": "light",
        "online": False,
        "state": {"power": False, "brightness": 100},
    },
    {
        "id": "bedroom-fan",
        "name": "Quạt phòng ngủ",
        "room": "Phòng ngủ",
        "kind": "fan",
        "online": False,
        "state": {"power": False, "speed": 0},
    },
    {
        "id": "kitchen-light",
        "name": "Đèn phòng bếp",
        "room": "Phòng bếp",
        "kind": "light",
        "online": False,
        "state": {"power": False, "brightness": 100},
    },
    {
        "id": "kitchen-fan",
        "name": "Quạt phòng bếp",
        "room": "Phòng bếp",
        "kind": "fan",
        "online": False,
        "state": {"power": False, "speed": 0},
    },
    {
        "id": "kitchen-gas",
        "name": "Cảm biến khí gas MQ2",
        "room": "Phòng bếp",
        "kind": "sensor",
        "online": False,
        "state": {"gas_level": 400, "alert": False, "ppm": 150},
    },
    {
        "id": "entry-lock",
        "name": "Khóa cửa chính",
        "room": "Lối vào",
        "kind": "lock",
        "online": False,
        "state": {"locked": True},
    },
]

_DEFAULT_SIMULATOR_DEVICES: list[dict[str, Any]] = [
    {
        "id": "living-light",
        "name": "Đèn phòng khách",
        "room": "Phòng khách",
        "kind": "light",
        "online": True,
        "state": {"power": False, "brightness": 80},
    },
    {
        "id": "bedroom-light",
        "name": "Đèn phòng ngủ",
        "room": "Phòng ngủ",
        "kind": "light",
        "online": True,
        "state": {"power": False, "brightness": 45},
    },
    {
        "id": "kitchen-light",
        "name": "Đèn phòng bếp",
        "room": "Phòng bếp",
        "kind": "light",
        "online": True,
        "state": {"power": True, "brightness": 90},
    },
    {
        "id": "living-aircon",
        "name": "Điều hòa phòng khách",
        "room": "Phòng khách",
        "kind": "aircon",
        "online": True,
        "state": {"power": True, "target_temperature": 25, "mode": "cool"},
    },
    {
        "id": "living-blind",
        "name": "Rèm phòng khách",
        "room": "Phòng khách",
        "kind": "blind",
        "online": True,
        "state": {"position": 0},
    },
    {
        "id": "hub-speaker",
        "name": "Loa Homing",
        "room": "Phòng khách",
        "kind": "speaker",
        "online": True,
        "state": {"power": False, "volume": 45, "playing": False},
    },
    {
        "id": "entry-lock",
        "name": "Khóa cửa chính",
        "room": "Lối vào",
        "kind": "lock",
        "online": True,
        "state": {"locked": False},
    },
    {
        "id": "entry-sensor",
        "name": "Cảm biến cửa",
        "room": "Lối vào",
        "kind": "sensor",
        "online": True,
        "state": {"open": False, "battery": 92},
    },
    {
        "id": "living-temperature",
        "name": "Cảm biến nhiệt độ",
        "room": "Phòng khách",
        "kind": "sensor",
        "online": True,
        "state": {"temperature": 27.8, "humidity": 56.0, "battery": 96},
    },
    {
        "id": "kitchen-gas",
        "name": "Cảm biến khí gas",
        "room": "Phòng bếp",
        "kind": "sensor",
        "online": True,
        "state": {"gas_detected": False, "ppm": 114, "battery": 98},
    },
    {
        "id": "living-motion",
        "name": "Cảm biến chuyển động",
        "room": "Phòng khách",
        "kind": "sensor",
        "online": True,
        "state": {"motion": True, "battery": 94},
    },
]


class DeviceRegistry:
    def __init__(
        self,
        storage_path: str | Path | None = None,
        *,
        seed_defaults: bool | None = None,
        mode: str | None = None,
    ) -> None:
        if storage_path is None:
            from src.config import get_settings

            storage_path = get_settings().device_storage_path
            if seed_defaults is None:
                seed_defaults = True
        self.storage_path = Path(storage_path)
        self._seed_defaults = bool(seed_defaults)
        norm_mode = str(mode or "").strip().lower()
        if norm_mode in {"real", "live", "hardware"}:
            self.mode = "real"
        elif norm_mode == "simulator":
            self.mode = "simulator"
        else:
            self.mode = "real" if self.storage_path.name.lower().startswith("devices_real") or "real" in self.storage_path.name.lower() else "simulator"
        self._devices: dict[str, Device] = {}
        self._discovered: dict[str, dict[str, Any]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = RLock()
        self._io_lock = Lock()
        self._save_version: int = 0
        self._last_written_version: int = 0
        self.load()

    def load(self) -> None:
        with self._lock:
            source = self.storage_path if self.storage_path.exists() else None
            should_save_seed = False
            if source is None and self._seed_defaults:
                if self.mode == "real":
                    raw = _DEFAULT_REAL_DEVICES
                    should_save_seed = True
                else:
                    if Path("runtime/devices.json").exists():
                        try:
                            raw = json.loads(Path("runtime/devices.json").read_text(encoding="utf-8"))
                            should_save_seed = True
                        except Exception:
                            raw = _DEFAULT_SIMULATOR_DEVICES
                            should_save_seed = True
                    else:
                        raw = _DEFAULT_SIMULATOR_DEVICES
                        should_save_seed = True
            else:
                try:
                    raw = json.loads(source.read_text(encoding="utf-8")) if source else []
                    if not isinstance(raw, list):
                        raise ValueError("device storage must contain a list")
                except (OSError, ValueError, TypeError):
                    logger.warning("Failed to load device registry from %s", source or self.storage_path, exc_info=True)
                    raw = []
            self._devices = {
                item["id"]: Device.model_validate(item) for item in raw if isinstance(item, dict) and item.get("id")
            }
            now = time.monotonic()
            self._last_seen = {
                device_id: now
                for device_id, dev in self._devices.items()
                if dev.online and (self.mode == "real" or device_id not in _VIRTUAL_DEVICE_IDS)
            }
        if should_save_seed:
            self.save()

    def save(self) -> None:
        with self._lock:
            self._save_version += 1
            current_ver = self._save_version
            payload = [device.model_dump() for device in self._devices.values()]
        with self._io_lock:
            if current_ver < self._last_written_version:
                return
            try:
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = self.storage_path.with_suffix(".tmp")
                temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary_path.replace(self.storage_path)
                self._last_written_version = current_ver
            except OSError:
                logger.warning("Failed to persist device registry to %s", self.storage_path, exc_info=True)

    def list(self) -> list[Device]:
        with self._lock:
            return deepcopy(list(self._devices.values()))

    def get(self, device_id: str) -> Device | None:
        with self._lock:
            device = self._devices.get(device_id)
            return deepcopy(device) if device else None

    def add(self, device: Device, *, save: bool = True) -> Device:
        with self._lock:
            if device.id in self._devices:
                raise ValueError("device_id_exists")
            self._devices[device.id] = deepcopy(device)
            self._discovered.pop(device.id, None)
            is_real_reg = "real" in str(self.storage_path).lower()
            if device.online and (is_real_reg or device.id not in _VIRTUAL_DEVICE_IDS):
                self._last_seen[device.id] = time.monotonic()
            result = deepcopy(device)
        if save:
            self.save()
        return result

    def update(self, device_id: str, updates: dict[str, Any], *, save: bool = True) -> Device | None:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                return None
            for field in ("name", "room", "kind"):
                if updates.get(field) is not None:
                    setattr(device, field, str(updates[field]).strip())
            if isinstance(updates.get("state"), dict):
                device.state.update(deepcopy(updates["state"]))
            if isinstance(updates.get("capabilities"), dict):
                device.capabilities = deepcopy(updates["capabilities"])
            result = deepcopy(device)
        if save:
            self.save()
        return result

    def delete(self, device_id: str, *, save: bool = True) -> bool:
        with self._lock:
            deleted = self._devices.pop(device_id, None) is not None
        if deleted and save:
            self.save()
        return deleted

    def rename_room(self, old_name: str, new_name: str, *, save: bool = True) -> list[Device]:
        old_normalized = old_name.strip().casefold()
        new_value = new_name.strip()
        updated: list[Device] = []
        with self._lock:
            for device in self._devices.values():
                if device.room.strip().casefold() == old_normalized:
                    device.room = new_value
                    updated.append(deepcopy(device))
        if updated and save:
            self.save()
        return updated

    def delete_room(self, room_name: str, *, save: bool = True) -> list[str]:
        target_normalized = room_name.strip().casefold()
        deleted_ids: list[str] = []
        with self._lock:
            for device_id, device in list(self._devices.items()):
                if device.room.strip().casefold() == target_normalized:
                    self._devices.pop(device_id, None)
                    self._last_seen.pop(device_id, None)
                    deleted_ids.append(device_id)
        if deleted_ids and save:
            self.save()
        return deleted_ids

    def rooms(self) -> list[str]:
        return sorted({device.room for device in self.list()})

    def capabilities(self, device: Device) -> dict[str, Any]:
        if device.capabilities:
            capabilities = deepcopy(device.capabilities)
        else:
            capabilities = default_capabilities(device.kind)
        capabilities.setdefault(
            "requires_app_approval",
            list(capabilities.get("requires_approval", [])),
        )
        return capabilities

    def supports(self, device: Device, action: str) -> bool:
        return action in self.capabilities(device).get("actions", [])

    def requires_approval(self, device: Device, action: str) -> bool:
        capabilities = self.capabilities(device)
        return action in set(capabilities.get("requires_approval", [])) | set(
            capabilities.get("requires_app_approval", [])
        )

    def validate_command(
        self,
        device_id: str,
        action: str,
        value: Any = None,
        *,
        approved_sensitive: bool = False,
    ) -> tuple[Device | None, str | None]:
        device = self.get(device_id)
        if device is None:
            return None, "not_found"
        if not device.online:
            return None, "device_offline"
        capabilities = self.capabilities(device)
        if self.requires_approval(device, action):
            if not approved_sensitive:
                return None, "approval_required"
        elif not self.supports(device, action):
            return None, "unsupported_action"
        if action != "set":
            return (device, None) if value is None else (None, "unexpected_value")
        if not isinstance(value, dict) or not value:
            return None, "invalid_set_value"
        field_schemas = capabilities.get("set_fields", {})
        unknown_fields = sorted(set(value) - set(field_schemas))
        if unknown_fields:
            return None, f"unsupported_set_field:{','.join(unknown_fields)}"
        for field, field_value in value.items():
            if not _valid_field_value(field_value, field_schemas[field]):
                return None, f"invalid_set_value:{field}"
        return device, None

    def command(
        self,
        device_id: str,
        action: str,
        value: Any = None,
        *,
        approved_sensitive: bool = False,
    ) -> Device | None:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None or (
                not self.supports(device, action)
                and not (approved_sensitive and self.requires_approval(device, action))
            ):
                return None
            if action == "toggle":
                device.state["power"] = not bool(device.state.get("power", False))
            elif action in {"on", "off"}:
                device.state["power"] = action == "on"
            elif action == "open":
                device.state["position"] = 100
                device.state["power"] = True
            elif action == "close":
                device.state["position"] = 0
                device.state["power"] = False
            elif action == "play":
                device.state["playing"] = True
                device.state["power"] = True
            elif action == "pause":
                device.state["playing"] = False
            elif action == "stop":
                device.state["playing"] = False
                device.state["power"] = False
            elif action == "set" and isinstance(value, dict):
                device.state.update(deepcopy(value))
            elif action == "lock":
                device.state["locked"] = True
            elif action == "unlock":
                device.state["locked"] = False
            result = deepcopy(device)
        self.save()
        return result

    def _infer_kind(self, device_id: str, state: dict[str, Any] | None = None) -> str:
        s = state or {}
        if "locked" in s:
            return "lock"
        if "target_temperature" in s or "mode" in s:
            return "aircon"
        if "position" in s:
            return "blind"
        if "volume" in s or "playing" in s:
            return "speaker"
        if "text" in s or "message" in s:
            return "display"
        if "speed" in s:
            return "fan"
        if (
            any(k in s for k in ("gas_detected", "ppm", "motion", "humidity"))
            or ("temperature" in s and "target_temperature" not in s)
            or ("open" in s and "battery" in s)
        ):
            return "sensor"
        if "brightness" in s:
            return "light"

        dev_id_lower = device_id.lower()
        if "lock" in dev_id_lower:
            return "lock"
        if any(k in dev_id_lower for k in ("aircon", "climate", "hvac", "ac")):
            return "aircon"
        if "fan" in dev_id_lower:
            return "fan"
        if any(k in dev_id_lower for k in ("blind", "curtain", "shutter", "shade")):
            return "blind"
        if any(k in dev_id_lower for k in ("speaker", "audio", "music", "sound")):
            return "speaker"
        if any(k in dev_id_lower for k in ("display", "screen", "tv", "monitor")):
            return "display"
        if any(k in dev_id_lower for k in ("sensor", "temp", "gas", "motion", "door", "smoke", "humidity")):
            return "sensor"
        if any(k in dev_id_lower for k in ("light", "lamp", "led", "bulb")):
            return "light"

        return "light"

    def add_discovered(self, info: dict[str, Any]) -> None:
        device_id = str(info.get("device_id") or info.get("id") or "").strip()
        if not device_id or self.get(device_id):
            return
        existing = self._discovered.get(device_id, {})
        state = deepcopy(info.get("state") if info.get("state") is not None else existing.get("state", {}))
        kind = str(info.get("kind") or existing.get("kind") or self._infer_kind(device_id, state))
        name = str(info.get("name") or existing.get("name") or device_id)
        room = str(info.get("room") or existing.get("room") or "Chưa phân loại")
        capabilities = deepcopy(
            info.get("capabilities")
            if info.get("capabilities") is not None
            else existing.get("capabilities") or default_capabilities(kind)
        )
        if not capabilities:
            capabilities = default_capabilities(kind)
        self._discovered[device_id] = {
            "device_id": device_id,
            "name": name,
            "room": room,
            "kind": kind,
            "state": state,
            "capabilities": capabilities,
            "discovered_at": existing.get("discovered_at") or datetime.now(UTC).isoformat(),
        }

    def list_discovered(self) -> list[dict[str, Any]]:
        return deepcopy(list(self._discovered.values()))

    def dismiss_discovered(self, device_id: str) -> bool:
        return self._discovered.pop(device_id, None) is not None

    def clear_discovered(self) -> None:
        self._discovered.clear()

    def pair_discovered(self, device_id: str, *, name: str | None = None, room: str | None = None) -> Device | None:
        item = self._discovered.pop(device_id, None)
        if item is None:
            return None
        kind = item.get("kind") or self._infer_kind(device_id, item.get("state"))
        capabilities = deepcopy(item.get("capabilities") or default_capabilities(kind))
        device = Device(
            id=device_id,
            name=name or item["name"],
            room=room or item["room"],
            kind=kind,
            state=item["state"],
            capabilities=capabilities,
        )
        return self.add(device)

    def update_state(self, device_id: str, state: dict[str, Any], online: bool = True) -> Device | None:
        if online:
            self.record_heartbeat(device_id)
        return (
            self.update(device_id, {"state": state}, save=True)
            if self.set_online(device_id, online, save=False)
            else None
        )

    def set_online(self, device_id: str, online: bool, *, save: bool = True) -> Device | None:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                return None
            device.online = online
            if online:
                self._last_seen[device_id] = time.monotonic()
            else:
                self._last_seen.pop(device_id, None)
            result = deepcopy(device)
        if save:
            self.save()
        return result

    def set_node_online(self, node_or_device_id: str, online: bool, *, save: bool = True) -> list[Device]:
        target_ids = get_node_device_ids(node_or_device_id, self._devices)
        updated: list[Device] = []
        with self._lock:
            now = time.monotonic()
            for dev_id in target_ids:
                dev = self._devices.get(dev_id)
                if dev:
                    dev.online = online
                    if online:
                        self._last_seen[dev_id] = now
                    else:
                        self._last_seen.pop(dev_id, None)
                    updated.append(deepcopy(dev))
        if updated and save:
            self.save()
        return updated

    def record_heartbeat(self, device_id: str) -> None:
        now = time.monotonic()
        with self._lock:
            if device_id in _HARDWARE_NODE_GROUPS:
                target_ids = get_node_device_ids(device_id, self._devices)
            else:
                target_ids = [device_id] if device_id in self._devices else []
            for item in target_ids:
                if self.mode == "real" or item not in _VIRTUAL_DEVICE_IDS:
                    self._last_seen[item] = now
                    if item in self._devices:
                        self._devices[item].online = True

    def check_stale_devices(self, timeout_seconds: float = 30.0) -> list[str]:
        now = time.monotonic()
        stale: list[str] = []
        with self._lock:
            for device_id, device in self._devices.items():
                if self.mode != "real" and device_id in _VIRTUAL_DEVICE_IDS:
                    continue
                if device.online and now - self._last_seen.get(device_id, 0) > timeout_seconds:
                    device.online = False
                    stale.append(device_id)
        if stale:
            self.save()
        return stale


_REGISTRIES: dict[str, DeviceRegistry] = {}
_REGISTRY_LOCK = RLock()


def get_registry(mode: str | None = None) -> DeviceRegistry:
    """Return the DeviceRegistry instance for the requested data mode ('real' or 'simulator')."""
    from src.config import get_settings

    if mode is None:
        mode = get_active_data_mode()

    normalized = str(mode or "simulator").strip().lower()
    settings = get_settings()

    with _REGISTRY_LOCK:
        if normalized in {"real", "live", "hardware"}:
            path = settings.real_device_storage_path
            if not Path(path).exists() and Path("data/devices_real.json").exists():
                path = "data/devices_real.json"
            key = f"real:{path}"
            if key not in _REGISTRIES:
                _REGISTRIES[key] = DeviceRegistry(path, seed_defaults=True, mode="real")
            return _REGISTRIES[key]

        path = settings.device_storage_path
        if not Path(path).exists() and Path("data/devices.json").exists():
            path = "data/devices.json"
        elif not Path(path).exists() and Path("runtime/devices.json").exists():
            path = "runtime/devices.json"
        key = f"simulator:{path}"
        if key not in _REGISTRIES:
            if "registry" in globals() and registry.storage_path == Path(path):
                _REGISTRIES[key] = registry
            else:
                _REGISTRIES[key] = DeviceRegistry(path, seed_defaults=True, mode="simulator")
        return _REGISTRIES[key]


def list_all_active_registries() -> list[DeviceRegistry]:
    """Return all instantiated registries for shared MQTT updates and watchdog."""
    with _REGISTRY_LOCK:
        get_registry("simulator")
        get_registry("real")
        return list(_REGISTRIES.values())


registry = get_registry("simulator")
