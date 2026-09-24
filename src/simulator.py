"""FastAPI-based MQTT Device Simulator Sandbox for Homing Smart Home."""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.simulator_storage import storage, validate_device_id

load_dotenv()

logger = logging.getLogger("simulator")
logging.basicConfig(level=logging.INFO)

PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "homing").strip("/")
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
SIMULATOR_HOST = os.getenv("SIMULATOR_HOST", "0.0.0.0")
SIMULATOR_PORT = int(os.getenv("SIMULATOR_PORT", "8001"))

# Global MQTT Client & Background Loop State
mqtt_client: mqtt.Client | None = None
mqtt_connected = False
_stop_simulation = Event()
_simulation_thread: Thread | None = None


def stamp(event: str, device_id: str, **extra: Any) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "event": event,
            "device_id": device_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "simulator",
            **extra,
        },
        separators=(",", ":"),
    )


def publish_discovery(device: dict[str, Any]) -> None:
    if not mqtt_client:
        return
    payload = json.dumps(
        {
            "device_id": device["id"],
            "name": device["name"],
            "kind": device["kind"],
            "room": device["room"],
            "source": "simulator",
        },
        separators=(",", ":"),
    )
    try:
        mqtt_client.publish(f"{PREFIX}/simulator/discovery", payload, qos=1)
    except Exception:
        logger.debug("Failed to publish discovery for %s", device.get("id"))


def publish_state(device_id: str, command_id: str | None = None) -> None:
    if not mqtt_client:
        return
    dev = storage.get_device(device_id)
    if not dev:
        return
    fault = storage.get_fault(device_id)
    online = fault != "offline"
    payload = stamp(
        "device.state",
        device_id,
        state=dev["state"],
        online=online,
        **({"command_id": command_id} if command_id else {}),
    )
    retain = fault != "offline"
    try:
        mqtt_client.publish(
            f"{PREFIX}/simulator/devices/{device_id}/state",
            payload,
            qos=1,
            retain=retain,
        )
    except Exception:
        logger.debug("Failed to publish state for %s", device_id)


def publish_all_devices() -> None:
    devices = storage.get_devices()
    for dev in devices:
        publish_discovery(dev)
        publish_state(dev["id"])


# Timestamp tracking for physical hardware telemetry
_last_hardware_telemetry: dict[str, float] = {}


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
    global mqtt_connected
    logger.info("Simulator MQTT connected with code %s", reason_code)
    mqtt_connected = True
    client.subscribe(f"{PREFIX}/devices/+/command", qos=1)
    client.subscribe(f"{PREFIX}/simulator/devices/+/command", qos=1)
    client.subscribe(f"{PREFIX}/simulator/+/fault", qos=1)
    client.subscribe(f"{PREFIX}/discovery/scan", qos=1)
    client.subscribe(f"{PREFIX}/simulator/broadcast/scan", qos=1)
    # Bi-directional bridge: Subscribe to real physical device topics
    client.subscribe(f"{PREFIX}/devices/+/state", qos=1)
    client.subscribe(f"{PREFIX}/devices/+/telemetry", qos=1)
    client.subscribe(f"{PREFIX}/security/access_log", qos=1)
    publish_all_devices()


def on_disconnect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
    global mqtt_connected
    mqtt_connected = False
    logger.warning("Simulator MQTT disconnected: %s", reason_code)


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    try:
        topic = message.topic
        payload_str = message.payload.decode("utf-8")
        payload = json.loads(payload_str) if payload_str.strip() else {}

        # Scan requests (simulator/broadcast/scan or discovery/scan)
        if topic.endswith("/simulator/broadcast/scan") or topic.endswith("/discovery/scan"):
            logger.info("Simulator received scan request from topic %s", topic)
            publish_all_devices()
            return

        # Fault injection topic: homing/simulator/{id}/fault
        if "/simulator/" in topic and topic.endswith("/fault"):
            parts = topic.split("/")
            device_id = parts[-2]
            try:
                device_id = validate_device_id(device_id)
                mode = payload.get("mode", "none")
                storage.set_fault(device_id, mode)
                publish_state(device_id)
            except ValueError as exc:
                logger.warning("Simulator fault injection error for %s: %s", device_id, exc)
            return

        # Mirror real physical device state: homing/devices/{id}/state (NOT /simulator/)
        if topic.startswith(f"{PREFIX}/devices/") and topic.endswith("/state"):
            parts = topic.split("/")
            raw_id = parts[-2]
            try:
                device_id = validate_device_id(raw_id)
            except ValueError:
                return

            _last_hardware_telemetry[device_id] = datetime.now(UTC).timestamp()

            state_updates: dict[str, Any] = {}
            # Case 1: Gateway packet format {"action": "...", "value": ..., "float_val": ...}
            if "action" in payload or "float_val" in payload:
                act = str(payload.get("action", "")).lower()
                val = payload.get("value", 0)
                fval = float(payload.get("float_val", 0.0))

                if device_id in {"living-light", "bedroom-light", "kitchen-light"}:
                    state_updates["power"] = (act == "on" or val == 1)
                elif device_id in {"living-fan", "bedroom-fan", "kitchen-fan"}:
                    state_updates["power"] = (act == "on" or val > 0)
                    state_updates["speed"] = val if val > 0 else 0
                elif device_id in {"entry-lock"}:
                    state_updates["locked"] = not (act in {"unlocked", "open"} or val == 1)
                elif device_id in {"window-servo", "living-blind"}:
                    target_id = "living-blind"
                    is_open = (act in {"open", "unlocked"} or val == 1)
                    dev = storage.get_device(target_id)
                    if dev:
                        storage.update_device(target_id, {"state": {"position": 100 if is_open else 0, "power": is_open}})
                        publish_state(target_id)
                    return
                elif device_id == "living-temperature":
                    target_id = "living-temperature"
                    dev = storage.get_device(target_id)
                    if dev:
                        curr = deepcopy(dev.get("state", {}))
                        if fval > 0:
                            curr["temperature"] = round(fval, 1)
                        storage.update_device(target_id, {"state": curr})
                        publish_state(target_id)
                    return
                elif device_id == "living-humidity":
                    target_id = "living-temperature"
                    dev = storage.get_device(target_id)
                    if dev:
                        curr = deepcopy(dev.get("state", {}))
                        if fval > 0:
                            curr["humidity"] = round(fval, 0)
                        storage.update_device(target_id, {"state": curr})
                        publish_state(target_id)
                    return
                elif device_id in {"living-ldr", "living-light-sensor"}:
                    target_id = "living-light-sensor"
                    dev = storage.get_device(target_id)
                    if dev:
                        lvl = int(fval if fval > 0 else val)
                        storage.update_device(target_id, {"state": {"light_level": lvl, "is_dark": lvl < 500}})
                        publish_state(target_id)
                    return
                elif device_id == "kitchen-gas":
                    target_id = "kitchen-gas"
                    dev = storage.get_device(target_id)
                    if dev:
                        ppm_val = int(fval if fval > 0 else val)
                        is_leak = (ppm_val > 1000 or act == "gas_leak")
                        storage.update_device(target_id, {"state": {"ppm": ppm_val, "gas_detected": is_leak, "alert": is_leak}})
                        publish_state(target_id)
                    return
                elif device_id == "living-motion":
                    target_id = "living-motion"
                    dev = storage.get_device(target_id)
                    if dev:
                        detected = (act == "detected" or val == 1)
                        storage.update_device(target_id, {"state": {"motion": detected}})
                        publish_state(target_id)
                    return
            else:
                # Case 2: Standard dictionary payload from classic firmware
                state_updates = {
                    k: v
                    for k, v in payload.items()
                    if k not in {"schema_version", "event", "device_id", "timestamp", "source", "online"}
                }

            if state_updates:
                dev = storage.get_device(device_id)
                if dev:
                    curr = deepcopy(dev.get("state", {}))
                    curr.update(state_updates)
                    storage.update_device(device_id, {"state": curr})
                    logger.info("Mirrored physical hardware state into simulator for %s: %s", device_id, state_updates)
                    publish_state(device_id)
            return

        # Command topic: homing/devices/{id}/command or homing/simulator/devices/{id}/command
        if topic.endswith("/command"):
            device_id = payload.get("device_id")
            if not device_id:
                parts = topic.split("/")
                device_id = parts[-2]
            if not device_id:
                return

            try:
                device_id = validate_device_id(device_id)
            except ValueError as exc:
                logger.warning("Invalid device_id in MQTT command: %s", exc)
                return

            dev = storage.get_device(device_id)
            if dev is None:
                return

            fault = storage.get_fault(device_id)
            if fault in {"offline", "timeout"}:
                logger.info("Simulator ignoring command for %s due to fault mode: %s", device_id, fault)
                return

            command_id = payload.get("command_id", "")
            action = payload.get("action", "")
            value = payload.get("value")

            if fault == "error":
                client.publish(
                    f"{PREFIX}/simulator/devices/{device_id}/ack",
                    stamp(
                        "device.ack", device_id, command_id=command_id, status="error", error="simulated_device_error"
                    ),
                    qos=1,
                )
                return

            try:
                updated_dev = storage.apply_action(device_id, action, value)
                client.publish(
                    f"{PREFIX}/simulator/devices/{device_id}/ack",
                    stamp(
                        "device.ack",
                        device_id,
                        command_id=command_id,
                        status="ok",
                        state=deepcopy(updated_dev["state"]),
                    ),
                    qos=1,
                )
                publish_state(device_id, command_id=command_id)
            except ValueError as exc:
                client.publish(
                    f"{PREFIX}/simulator/devices/{device_id}/ack",
                    stamp("device.ack", device_id, command_id=command_id, status="error", error=str(exc)),
                    qos=1,
                )
    except Exception:
        logger.exception("Simulator error processing MQTT message")


def _auto_simulate_loop() -> None:
    logger.info("Simulator auto-simulate background loop started")
    iteration = 0
    while not _stop_simulation.is_set():
        try:
            iteration += 1
            devices = storage.get_devices()

            # Heartbeat keepalive: publish state for all non-offline/non-timeout devices every ~15s (5 iterations * 3s)
            if iteration % 5 == 0:
                for dev in devices:
                    if storage.get_fault(dev["id"]) not in {"offline", "timeout"}:
                        publish_state(dev["id"])

            for dev in devices:
                if storage.get_fault(dev["id"]) in {"offline", "timeout"}:
                    continue
                if not dev.get("auto_simulate", False):
                    continue
                dev_id = dev["id"]
                # Skip auto-simulation if real physical hardware telemetry was recently received
                if datetime.now(UTC).timestamp() - _last_hardware_telemetry.get(dev_id, 0) < 60:
                    continue
                state = deepcopy(dev.get("state", {}))
                changed = False

                if "temperature" in state:
                    delta = random.choice([-0.2, -0.1, 0.0, 0.1, 0.2])
                    state["temperature"] = round(max(16.0, min(38.0, state["temperature"] + delta)), 1)
                    changed = True

                if "humidity" in state:
                    delta_h = random.choice([-1, 0, 1])
                    state["humidity"] = round(max(30.0, min(95.0, state["humidity"] + delta_h)), 1)
                    changed = True

                if "ppm" in state:
                    delta_p = random.choice([-5, -2, 0, 2, 5])
                    state["ppm"] = max(30, min(600, state["ppm"] + delta_p))
                    state["gas_detected"] = state["ppm"] > 350
                    changed = True

                if "motion" in state:
                    # Random 10% chance to toggle motion detection
                    if random.random() < 0.10:
                        state["motion"] = not state["motion"]
                        changed = True

                if "battery" in state and random.random() < 0.02:
                    state["battery"] = max(10, state["battery"] - 1)
                    changed = True

                if changed:
                    storage.update_device(dev_id, {"state": state})
                    publish_state(dev_id)
        except Exception:
            logger.debug("Auto-simulate iteration error", exc_info=True)

        _stop_simulation.wait(3.0)


def is_test_mode() -> bool:
    return os.getenv("APP_ENV") == "test" or "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def start_mqtt_client() -> None:
    global mqtt_client
    if mqtt_client is not None or is_test_mode():
        return
    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"homing-device-simulator-{uuid4().hex[:6]}",
        )
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.reconnect_delay_set(min_delay=1, max_delay=15)
        client.connect_async(BROKER, PORT, keepalive=60)
        client.loop_start()
        mqtt_client = client
    except Exception:
        logger.warning("Could not initiate MQTT client connection to %s:%s (will retry in background)", BROKER, PORT)


def stop_mqtt_client() -> None:
    global mqtt_client
    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        except Exception:
            pass
        mqtt_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulation_thread
    if not is_test_mode():
        start_mqtt_client()
        _stop_simulation.clear()
        _simulation_thread = Thread(target=_auto_simulate_loop, daemon=True)
        _simulation_thread.start()
    try:
        yield
    finally:
        if not is_test_mode():
            _stop_simulation.set()
            stop_mqtt_client()


app = FastAPI(
    title="Homing Device Simulator Sandbox",
    description="Interactive 2D/3D Smart Home Device Simulator and MQTT Sandbox",
    lifespan=None if is_test_mode() else lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mqtt_connected": mqtt_connected,
        "broker": f"{BROKER}:{PORT}",
        "topic_prefix": PREFIX,
    }


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    return storage.get_state()


@app.post("/api/walls")
async def save_walls(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, float]]:
    walls = payload.get("walls", []) if isinstance(payload, dict) else payload
    try:
        saved = storage.save_walls(walls)
        return saved
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/devices")
async def add_device(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        dev = storage.add_device(payload)
        publish_discovery(dev)
        publish_state(dev["id"])
        return dev
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/api/devices/{device_id}")
async def update_device(device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        updated = storage.update_device(device_id, payload)
        if updated is None:
            raise HTTPException(status_code=404, detail="device_not_found")
        publish_discovery(updated)
        publish_state(device_id)
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str) -> dict[str, bool]:
    try:
        deleted = storage.delete_device(device_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="device_not_found")
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/devices/{device_id}/action")
async def perform_action(device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    value = payload.get("value")
    if not action:
        raise HTTPException(status_code=400, detail="action_required")
    fault = storage.get_fault(device_id)
    if fault in {"offline", "timeout"}:
        raise HTTPException(status_code=400, detail=f"device_{fault}")
    try:
        updated = storage.apply_action(device_id, action, value)
        publish_state(device_id)

        # Forward command to physical ESP32 hardware via MQTT
        if mqtt_client:
            cmd_id = str(uuid4())
            hw_action = action
            hw_value = value
            is_on = bool(updated.get("state", {}).get("power", False))

            if action == "toggle":
                if device_id == "entry-lock":
                    is_locked = bool(updated.get("state", {}).get("locked", True))
                    hw_action = "lock" if is_locked else "unlock"
                    hw_value = 0 if is_locked else 1
                elif device_id in {"living-blind", "window-servo"}:
                    hw_action = "open" if is_on else "close"
                    hw_value = 1 if is_on else 0
                else:
                    hw_action = "turn_on" if is_on else "turn_off"
                    hw_value = 1 if is_on else 0
            elif action in {"on", "turn_on"}:
                hw_action = "turn_on"
                hw_value = 1
            elif action in {"off", "turn_off"}:
                hw_action = "turn_off"
                hw_value = 0
            elif action in {"unlock", "open"} and device_id == "entry-lock":
                hw_action = "unlock"
                hw_value = 1
            elif action in {"lock", "close"} and device_id == "entry-lock":
                hw_action = "lock"
                hw_value = 0

            hw_payload = json.dumps(
                {
                    "device_id": device_id,
                    "command_id": cmd_id,
                    "action": hw_action,
                    "value": hw_value if hw_value is not None else 1,
                },
                separators=(",", ":"),
            )
            try:
                mqtt_client.publish(f"{PREFIX}/devices/{device_id}/command", hw_payload, qos=1)
                logger.info("Forwarded command to real hardware %s: %s", f"{PREFIX}/devices/{device_id}/command", hw_payload)
                if device_id == "living-blind":
                    mqtt_client.publish(f"{PREFIX}/devices/window-servo/command", hw_payload, qos=1)
            except Exception:
                logger.warning("Failed to publish command to real hardware topic for %s", device_id)

        return updated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/devices/{device_id}/fault")
async def set_device_fault(device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode", "none"))
    try:
        applied_mode = storage.set_fault(device_id, mode)
        publish_state(device_id)
        return {"device_id": device_id, "fault": applied_mode}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/discovery/scan")
async def trigger_scan() -> dict[str, Any]:
    publish_all_devices()
    return {"status": "scan_broadcasted", "device_count": len(storage.get_devices())}


@app.post("/api/state/reset")
async def reset_simulator_state() -> dict[str, Any]:
    state = storage.reset()
    publish_all_devices()
    return state


# Mount frontend dist assets if present
frontend_dist = Path(__file__).parent.parent / "frontend-simulator" / "dist"
assets_dir = frontend_dist / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
app.mount("/simulator/assets", StaticFiles(directory=str(assets_dir)), name="simulator-assets")


@app.get("/", response_class=HTMLResponse)
@app.get("/simulator", response_class=HTMLResponse)
@app.get("/simulator/", response_class=HTMLResponse)
async def get_simulator_ui() -> HTMLResponse:
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<html><body><h1>Terra Simulator Sandbox</h1><p>Frontend not built. Please run 'npm run build' in frontend-simulator/.</p></body></html>",
        status_code=200,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SIMULATOR_HOST, port=SIMULATOR_PORT)
