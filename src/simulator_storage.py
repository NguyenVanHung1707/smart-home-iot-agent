import html
import json
import logging
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

DEVICE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
ALLOWED_FAULTS = {"none", "offline", "timeout", "error"}
ALLOWED_KINDS = {"light", "fan", "aircon", "blind", "speaker", "lock", "sensor", "display"}
MIN_COORD = 0.0
MAX_COORD = 5000.0


def validate_device_id(device_id: Any) -> str:
    if not isinstance(device_id, str):
        raise ValueError("invalid_device_id: must be a string")
    dev_id = device_id.strip()
    if not dev_id:
        raise ValueError("device_id_required")
    if not DEVICE_ID_REGEX.match(dev_id):
        raise ValueError("invalid_device_id: only alphanumeric, '-', and '_' are allowed")
    return dev_id


def validate_coordinate(val: Any, name: str = "coordinate") -> float:
    try:
        fval = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"invalid_{name}: must be a number")
    if not math.isfinite(fval):
        raise ValueError(f"invalid_{name}: must be a finite number")
    if not (MIN_COORD <= fval <= MAX_COORD):
        raise ValueError(f"invalid_{name}: out of bounds [{MIN_COORD}, {MAX_COORD}]")
    return round(fval, 2)


def sanitize_text(text: Any, max_length: int = 100) -> str:
    if text is None:
        return ""
    clean = html.escape(str(text).strip())
    return clean[:max_length]


DEFAULT_STORAGE_PATH = os.getenv("SIMULATOR_STORAGE_PATH", "runtime/simulator_state.json")

DEFAULT_WALLS: list[dict[str, float]] = [
    {"x1": 50.0, "y1": 50.0, "x2": 450.0, "y2": 50.0},
    {"x1": 450.0, "y1": 50.0, "x2": 450.0, "y2": 400.0},
    {"x1": 450.0, "y1": 400.0, "x2": 50.0, "y2": 400.0},
    {"x1": 50.0, "y1": 400.0, "x2": 50.0, "y2": 50.0},
    {"x1": 250.0, "y1": 50.0, "x2": 250.0, "y2": 400.0},
    {"x1": 250.0, "y1": 220.0, "x2": 450.0, "y2": 220.0},
]

DEFAULT_DEVICES: list[dict[str, Any]] = [
    {
        "id": "living-light",
        "name": "Đèn phòng khách",
        "kind": "light",
        "room": "Phòng khách",
        "x": 150.0,
        "y": 140.0,
        "state": {"power": True, "brightness": 80},
        "auto_simulate": False,
    },
    {
        "id": "bedroom-light",
        "name": "Đèn phòng ngủ",
        "kind": "light",
        "room": "Phòng ngủ",
        "x": 350.0,
        "y": 130.0,
        "state": {"power": False, "brightness": 45},
        "auto_simulate": False,
    },
    {
        "id": "kitchen-light",
        "name": "Đèn phòng bếp",
        "kind": "light",
        "room": "Phòng bếp",
        "x": 350.0,
        "y": 310.0,
        "state": {"power": True, "brightness": 90},
        "auto_simulate": False,
    },
    {
        "id": "living-aircon",
        "name": "Điều hòa phòng khách",
        "kind": "aircon",
        "room": "Phòng khách",
        "x": 90.0,
        "y": 80.0,
        "state": {"power": True, "target_temperature": 25, "mode": "cool"},
        "auto_simulate": False,
    },
    {
        "id": "living-blind",
        "name": "Rèm phòng khách",
        "kind": "blind",
        "room": "Phòng khách",
        "x": 70.0,
        "y": 380.0,
        "state": {"position": 0},
        "auto_simulate": False,
    },
    {
        "id": "hub-speaker",
        "name": "Loa Homing",
        "kind": "speaker",
        "room": "Phòng khách",
        "x": 220.0,
        "y": 150.0,
        "state": {"power": False, "volume": 45, "playing": False},
        "auto_simulate": False,
    },
    {
        "id": "entry-lock",
        "name": "Khóa cửa chính",
        "kind": "lock",
        "room": "Phòng khách",
        "x": 50.0,
        "y": 220.0,
        "state": {"locked": True},
        "auto_simulate": False,
    },
    {
        "id": "entry-sensor",
        "name": "Cảm biến cửa",
        "kind": "sensor",
        "room": "Phòng khách",
        "x": 60.0,
        "y": 240.0,
        "state": {"open": False, "battery": 92},
        "auto_simulate": True,
    },
    {
        "id": "living-temperature",
        "name": "Cảm biến nhiệt độ",
        "kind": "sensor",
        "room": "Phòng khách",
        "x": 150.0,
        "y": 280.0,
        "state": {"temperature": 27.0, "humidity": 65.0, "battery": 98},
        "auto_simulate": True,
    },
    {
        "id": "kitchen-gas",
        "name": "Cảm biến khí gas",
        "kind": "sensor",
        "room": "Phòng bếp",
        "x": 410.0,
        "y": 360.0,
        "state": {"gas_detected": False, "ppm": 120, "battery": 100},
        "auto_simulate": True,
    },
    {
        "id": "living-motion",
        "name": "Cảm biến chuyển động",
        "kind": "sensor",
        "room": "Phòng khách",
        "x": 100.0,
        "y": 330.0,
        "state": {"motion": False, "battery": 94},
        "auto_simulate": True,
    },
]


class SimulatorStorage:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or DEFAULT_STORAGE_PATH)
        self._lock = RLock()
        self._walls: list[dict[str, float]] = []
        self._devices: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, str] = {}
        self.load()

    def _default_state(self) -> dict[str, Any]:
        devices: list[dict[str, Any]] = []
        seed_file = Path("data/devices.json")
        if not seed_file.exists():
            seed_file = Path(__file__).resolve().parent.parent / "data" / "devices.json"

        if seed_file.exists():
            try:
                raw_seed = json.loads(seed_file.read_text(encoding="utf-8"))
                if isinstance(raw_seed, list) and raw_seed:
                    coords_and_sim = {
                        d["id"]: {
                            "x": d.get("x", 100.0),
                            "y": d.get("y", 100.0),
                            "auto_simulate": d.get("auto_simulate", False),
                        }
                        for d in DEFAULT_DEVICES
                    }
                    for item in raw_seed:
                        if isinstance(item, dict) and item.get("id"):
                            dev_id = str(item["id"]).strip()
                            meta = coords_and_sim.get(
                                dev_id,
                                {
                                    "x": 100.0,
                                    "y": 100.0,
                                    "auto_simulate": item.get("kind") == "sensor",
                                },
                            )
                            devices.append(
                                {
                                    "id": dev_id,
                                    "name": str(item.get("name") or dev_id),
                                    "kind": str(item.get("kind") or "light"),
                                    "room": str(item.get("room") or "Phòng khách"),
                                    "x": float(meta.get("x", 100.0)),
                                    "y": float(meta.get("y", 100.0)),
                                    "state": deepcopy(item.get("state") or {}),
                                    "auto_simulate": bool(meta.get("auto_simulate", False)),
                                }
                            )
            except Exception:
                logger.warning("Failed to load seed devices from %s", seed_file, exc_info=True)

        if not devices:
            devices = deepcopy(DEFAULT_DEVICES)

        return {
            "walls": deepcopy(DEFAULT_WALLS),
            "devices": devices,
            "faults": {dev["id"]: "none" for dev in devices},
        }

    def load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                state = self._default_state()
                self._walls = state["walls"]
                self._devices = {dev["id"]: dev for dev in state["devices"]}
                self._faults = state["faults"]
                self._save_unlocked()
                return

            try:
                raw_text = self.storage_path.read_text(encoding="utf-8")
                raw = json.loads(raw_text) if raw_text.strip() else {}
                if not isinstance(raw, dict):
                    raise ValueError("State must be a JSON object")

                self._walls = [
                    {
                        "x1": float(w.get("x1", 0.0)),
                        "y1": float(w.get("y1", 0.0)),
                        "x2": float(w.get("x2", 0.0)),
                        "y2": float(w.get("y2", 0.0)),
                    }
                    for w in raw.get("walls", [])
                    if isinstance(w, dict)
                ]
                if not self._walls:
                    self._walls = deepcopy(DEFAULT_WALLS)

                devices_list = raw.get("devices", [])
                if not isinstance(devices_list, list) or not devices_list:
                    devices_list = deepcopy(DEFAULT_DEVICES)

                self._devices = {}
                for item in devices_list:
                    if isinstance(item, dict) and item.get("id"):
                        dev_id = str(item["id"]).strip()
                        self._devices[dev_id] = {
                            "id": dev_id,
                            "name": str(item.get("name") or dev_id),
                            "kind": str(item.get("kind") or "light"),
                            "room": str(item.get("room") or "Phòng khách"),
                            "x": float(item.get("x", 100.0)),
                            "y": float(item.get("y", 100.0)),
                            "state": deepcopy(item.get("state") or {}),
                            "auto_simulate": bool(item.get("auto_simulate", False)),
                        }

                faults_dict = raw.get("faults", {})
                self._faults = {dev_id: faults_dict.get(dev_id, "none") for dev_id in self._devices}
            except Exception:
                logger.warning(
                    "Failed to parse simulator state from %s, initializing default state",
                    self.storage_path,
                    exc_info=True,
                )
                state = self._default_state()
                self._walls = state["walls"]
                self._devices = {dev["id"]: dev for dev in state["devices"]}
                self._faults = state["faults"]
                self._save_unlocked()

    def _save_unlocked(self) -> None:
        payload = {
            "walls": self._walls,
            "devices": list(self._devices.values()),
            "faults": self._faults,
        }
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.storage_path.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_file.replace(self.storage_path)
        except OSError:
            logger.warning("Failed to write simulator state to %s", self.storage_path, exc_info=True)

    def save(self) -> None:
        with self._lock:
            self._save_unlocked()

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "walls": deepcopy(self._walls),
                "devices": deepcopy(list(self._devices.values())),
                "faults": deepcopy(self._faults),
            }

    def get_walls(self) -> list[dict[str, float]]:
        with self._lock:
            return deepcopy(self._walls)

    def save_walls(self, walls: list[dict[str, Any]]) -> list[dict[str, float]]:
        clean_walls = [
            {
                "x1": validate_coordinate(w.get("x1", 0.0), "x1"),
                "y1": validate_coordinate(w.get("y1", 0.0), "y1"),
                "x2": validate_coordinate(w.get("x2", 0.0), "x2"),
                "y2": validate_coordinate(w.get("y2", 0.0), "y2"),
            }
            for w in walls
            if isinstance(w, dict)
        ]
        with self._lock:
            self._walls = clean_walls
            self._save_unlocked()
            return deepcopy(self._walls)

    def get_devices(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self._devices.values()))

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        dev_id = validate_device_id(device_id)
        with self._lock:
            dev = self._devices.get(dev_id)
            return deepcopy(dev) if dev else None

    def add_device(self, device: dict[str, Any]) -> dict[str, Any]:
        dev_id = validate_device_id(device.get("id"))
        with self._lock:
            if dev_id in self._devices:
                raise ValueError("device_id_exists")
            item = {
                "id": dev_id,
                "name": sanitize_text(device.get("name") or dev_id),
                "kind": sanitize_text(device.get("kind") or "light"),
                "room": sanitize_text(device.get("room") or "Phòng khách"),
                "x": validate_coordinate(device.get("x", 100.0), "x"),
                "y": validate_coordinate(device.get("y", 100.0), "y"),
                "state": deepcopy(device.get("state") or {}),
                "auto_simulate": bool(device.get("auto_simulate", False)),
            }
            self._devices[dev_id] = item
            self._faults.setdefault(dev_id, "none")
            self._save_unlocked()
            return deepcopy(item)

    def update_device(self, device_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        dev_id = validate_device_id(device_id)
        with self._lock:
            dev = self._devices.get(dev_id)
            if dev is None:
                return None
            for field in ("name", "kind", "room"):
                if updates.get(field) is not None:
                    dev[field] = sanitize_text(updates[field])
            for coord in ("x", "y"):
                if updates.get(coord) is not None:
                    dev[coord] = validate_coordinate(updates[coord], coord)
            if "auto_simulate" in updates:
                dev["auto_simulate"] = bool(updates["auto_simulate"])
            if isinstance(updates.get("state"), dict):
                dev["state"].update(deepcopy(updates["state"]))
            self._save_unlocked()
            return deepcopy(dev)

    def delete_device(self, device_id: str) -> bool:
        dev_id = validate_device_id(device_id)
        with self._lock:
            deleted = self._devices.pop(dev_id, None) is not None
            self._faults.pop(dev_id, None)
            if deleted:
                self._save_unlocked()
            return deleted

    def get_faults(self) -> dict[str, str]:
        with self._lock:
            return deepcopy(self._faults)

    def get_fault(self, device_id: str) -> str:
        dev_id = validate_device_id(device_id)
        with self._lock:
            return self._faults.get(dev_id, "none")

    def set_fault(self, device_id: str, mode: str) -> str:
        dev_id = validate_device_id(device_id)
        mode_str = str(mode or "none").lower().strip()
        if mode_str not in ALLOWED_FAULTS:
            raise ValueError("invalid_fault_mode: must be one of none, offline, timeout, error")
        with self._lock:
            self._faults[dev_id] = mode_str
            self._save_unlocked()
            return mode_str

    def apply_action(self, device_id: str, action: str, value: Any = None) -> dict[str, Any]:
        dev_id = validate_device_id(device_id)
        with self._lock:
            dev = self._devices.get(dev_id)
            if dev is None:
                raise ValueError("device_not_found")
            state = dev["state"]
            if action == "toggle":
                if dev.get("kind") == "blind":
                    if state.get("position", 0) > 0:
                        state["position"] = 0
                        state["power"] = False
                    else:
                        state["position"] = 100
                        state["power"] = True
                else:
                    state["power"] = not bool(state.get("power", False))
            elif action in {"on", "off"}:
                state["power"] = action == "on"
            elif action == "lock":
                state["locked"] = True
            elif action == "unlock":
                state["locked"] = False
            elif action == "open":
                state["position"] = 100
                state["power"] = True
            elif action == "close":
                state["position"] = 0
                state["power"] = False
            elif action == "play":
                state["playing"] = True
                state["power"] = True
            elif action == "pause":
                state["playing"] = False
            elif action == "stop":
                state["playing"] = False
                state["power"] = False
            elif action == "set":
                if isinstance(value, dict):
                    state.update(deepcopy(value))
                else:
                    raise ValueError("invalid_set_value")
            else:
                raise ValueError(f"unsupported_action:{action}")
            self._save_unlocked()
            return deepcopy(dev)

    def reset(self) -> dict[str, Any]:
        with self._lock:
            state = self._default_state()
            self._walls = state["walls"]
            self._devices = {dev["id"]: dev for dev in state["devices"]}
            self._faults = state["faults"]
            self._save_unlocked()
            return self.get_state()


storage = SimulatorStorage()
