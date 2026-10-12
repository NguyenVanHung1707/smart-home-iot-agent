"""Floorplan service separating Real and Simulator 3D architectures."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

from src.services.devices import get_registry

logger = logging.getLogger(__name__)

REAL_FLOORPLAN_PATH = Path("data/floorplan_real.json")
SIMULATOR_FLOORPLAN_PATH = Path("runtime/simulator_state.json")

DEFAULT_WALLS: list[dict[str, float]] = [
    {"x1": 50.0, "y1": 50.0, "x2": 550.0, "y2": 50.0},
    {"x1": 550.0, "y1": 50.0, "x2": 550.0, "y2": 350.0},
    {"x1": 550.0, "y1": 350.0, "x2": 50.0, "y2": 350.0},
    {"x1": 50.0, "y1": 350.0, "x2": 50.0, "y2": 50.0},
    {"x1": 215.0, "y1": 50.0, "x2": 215.0, "y2": 350.0},
    {"x1": 385.0, "y1": 50.0, "x2": 385.0, "y2": 350.0},
]

DEFAULT_REAL_DEVICE_COORDS: dict[str, dict[str, Any]] = {
    "bedroom-light": {"x": 132.5, "y": 65.0, "room": "Phòng ngủ"},
    "bedroom-fan": {"x": 65.0, "y": 140.0, "room": "Phòng ngủ"},
    "living-display": {"x": 260.0, "y": 65.0, "room": "Phòng khách"},
    "living-light": {"x": 300.0, "y": 65.0, "room": "Phòng khách"},
    "living-fan": {"x": 355.0, "y": 75.0, "room": "Phòng khách"},
    "living-motion": {"x": 228.0, "y": 200.0, "room": "Phòng khách"},
    "living-temperature": {"x": 372.0, "y": 125.0, "room": "Phòng khách"},
    "living-light-sensor": {"x": 355.0, "y": 140.0, "room": "Phòng khách"},
    "living-blind": {"x": 300.0, "y": 170.0, "room": "Phòng khách"},
    "entry-lock": {"x": 300.0, "y": 350.0, "room": "Lối vào"},
    "kitchen-light": {"x": 467.5, "y": 65.0, "room": "Phòng bếp"},
    "kitchen-fan": {"x": 535.0, "y": 140.0, "room": "Phòng bếp"},
    "kitchen-gas": {"x": 398.0, "y": 125.0, "room": "Phòng bếp"},
}

_lock = RLock()


def _normalize_mode(mode: str | None) -> str:
    norm = str(mode or "simulator").strip().lower()
    return "real" if norm in {"real", "live", "hardware"} else "simulator"


def get_floorplan_state(mode: str | None = None) -> dict[str, Any]:
    """Retrieve the distinct floorplan state for real hardware or simulator sandbox."""
    active_mode = _normalize_mode(mode)
    with _lock:
        if active_mode == "real":
            return _get_real_floorplan()
        return _get_simulator_floorplan()


def _get_real_floorplan() -> dict[str, Any]:
    walls = deepcopy(DEFAULT_WALLS)
    dev_coords: dict[str, dict[str, float]] = {}

    if REAL_FLOORPLAN_PATH.exists():
        try:
            data = json.loads(REAL_FLOORPLAN_PATH.read_text(encoding="utf-8"))
            if isinstance(data.get("walls"), list) and data["walls"]:
                walls = data["walls"]
            if isinstance(data.get("devices"), list):
                for d in data["devices"]:
                    dev_id = d.get("id")
                    if dev_id:
                        dev_coords[dev_id] = {
                            "x": float(d.get("x", 250.0)),
                            "y": float(d.get("y", 200.0)),
                        }
        except Exception:
            logger.warning("Error reading real floorplan from %s, using defaults", REAL_FLOORPLAN_PATH, exc_info=True)

    # Sync live state from real device registry
    real_reg = get_registry("real")
    real_devices = real_reg.list()

    devices_list: list[dict[str, Any]] = []
    for d in real_devices:
        dev_id = d.id
        default_pos = DEFAULT_REAL_DEVICE_COORDS.get(dev_id, {"x": 250.0, "y": 200.0})
        x = dev_coords.get(dev_id, {}).get("x", default_pos["x"])
        y = dev_coords.get(dev_id, {}).get("y", default_pos["y"])
        devices_list.append({
            "id": d.id,
            "name": d.name,
            "room": d.room,
            "kind": d.kind,
            "x": x,
            "y": y,
            "online": d.online,
            "state": deepcopy(d.state),
            "capabilities": deepcopy(d.capabilities),
            "auto_simulate": False,
        })

    return {
        "walls": walls,
        "devices": devices_list,
        "faults": {},
        "mode": "real",
    }


def _get_simulator_floorplan() -> dict[str, Any]:
    if SIMULATOR_FLOORPLAN_PATH.exists():
        try:
            data = json.loads(SIMULATOR_FLOORPLAN_PATH.read_text(encoding="utf-8"))
            return {
                "walls": data.get("walls", deepcopy(DEFAULT_WALLS)),
                "devices": data.get("devices", []),
                "faults": data.get("faults", {}),
                "mode": "simulator",
            }
        except Exception:
            logger.warning("Error reading simulator floorplan from %s", SIMULATOR_FLOORPLAN_PATH, exc_info=True)

    from src.simulator_storage import storage
    sim_state = storage.get_state()
    sim_state["mode"] = "simulator"
    return sim_state


def save_floorplan_walls(walls: list[dict[str, Any]], mode: str | None = None) -> list[dict[str, float]]:
    active_mode = _normalize_mode(mode)
    clean_walls = [
        {
            "x1": round(float(w["x1"]), 2),
            "y1": round(float(w["y1"]), 2),
            "x2": round(float(w["x2"]), 2),
            "y2": round(float(w["y2"]), 2),
        }
        for w in walls
        if all(k in w for k in ("x1", "y1", "x2", "y2"))
    ]

    with _lock:
        if active_mode == "real":
            current = {}
            if REAL_FLOORPLAN_PATH.exists():
                try:
                    current = json.loads(REAL_FLOORPLAN_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass
            current["walls"] = clean_walls
            REAL_FLOORPLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
            REAL_FLOORPLAN_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
            return clean_walls
        else:
            from src.simulator_storage import storage
            return storage.save_walls(clean_walls)


def update_floorplan_device(
    device_id: str, updates: dict[str, Any], mode: str | None = None
) -> dict[str, Any] | None:
    active_mode = _normalize_mode(mode)
    with _lock:
        if active_mode == "real":
            current: dict[str, Any] = {"walls": deepcopy(DEFAULT_WALLS), "devices": []}
            if REAL_FLOORPLAN_PATH.exists():
                try:
                    current = json.loads(REAL_FLOORPLAN_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass

            dev_found = False
            devices = current.get("devices", [])
            for d in devices:
                if d.get("id") == device_id:
                    for k in ("x", "y", "room", "name"):
                        if k in updates:
                            d[k] = updates[k]
                    dev_found = True
                    break

            if not dev_found:
                devices.append({
                    "id": device_id,
                    "x": updates.get("x", 250.0),
                    "y": updates.get("y", 200.0),
                    "room": updates.get("room", "Phòng khách"),
                })
            current["devices"] = devices
            REAL_FLOORPLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
            REAL_FLOORPLAN_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

            # Also update room/name in device registry if requested
            if any(k in updates for k in ("name", "room")):
                get_registry("real").update(device_id, updates)

            return {"success": True, "device_id": device_id}
        else:
            from src.simulator_storage import storage
            return storage.update_device(device_id, updates)


def reset_floorplan_state(mode: str | None = None) -> dict[str, Any]:
    active_mode = _normalize_mode(mode)
    with _lock:
        if active_mode == "real":
            default_state = {
                "walls": deepcopy(DEFAULT_WALLS),
                "devices": [
                    {
                        "id": dev_id,
                        "x": coords["x"],
                        "y": coords["y"],
                        "room": coords["room"],
                    }
                    for dev_id, coords in DEFAULT_REAL_DEVICE_COORDS.items()
                ],
            }
            REAL_FLOORPLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
            REAL_FLOORPLAN_PATH.write_text(json.dumps(default_state, ensure_ascii=False, indent=2), encoding="utf-8")
            return _get_real_floorplan()
        else:
            from src.simulator_storage import storage
            storage.reset()
            return storage.get_state()
