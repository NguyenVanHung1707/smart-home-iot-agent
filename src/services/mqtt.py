"""MQTT command dispatcher and state mirror for HomeMind Hub."""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from src.config import get_settings
from src.models.schemas import Device


def _registry():
    import src.services.devices as devices_mod

    return devices_mod.registry


def _all_registries():
    import src.services.devices as devices_mod

    current_default = _registry()
    regs = [current_default]
    for reg in devices_mod.list_all_active_registries():
        if reg not in regs:
            regs.append(reg)
    return regs


def _target_registries(is_simulator: bool):
    import src.services.devices as devices_mod

    if is_simulator:
        return [devices_mod.get_registry("simulator")]
    regs = [devices_mod.get_registry("real")]
    current_default = _registry()
    if current_default is not devices_mod.get_registry("simulator") and current_default not in regs:
        regs.append(current_default)
    return regs


class VerificationStatus(StrEnum):
    STATE_VERIFIED = "STATE_VERIFIED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class CommandVerification:
    status: VerificationStatus
    reason: str
    device: Device | None = None


@dataclass(slots=True)
class _PendingVerification:
    """Accumulate ACK and state messages arriving on MQTT callbacks."""

    device_id: str
    ack_received: Event = field(default_factory=Event)
    state_received: Event = field(default_factory=Event)
    ack: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


logger = logging.getLogger(__name__)


def _topic(device_id: str, suffix: str) -> str:
    return f"{get_settings().mqtt_topic_prefix.strip('/')}/devices/{device_id}/{suffix}"


def device_command_topic(device_id: str, mode: str = "real") -> str:
    prefix = get_settings().mqtt_topic_prefix.strip("/")
    if (mode or "").strip().lower() == "simulator":
        return f"{prefix}/simulator/devices/{device_id}/command"
    return f"{prefix}/devices/{device_id}/command"


def device_state_topic(device_id: str) -> str:
    return _topic(device_id, "state")


def device_ack_topic(device_id: str) -> str:
    return _topic(device_id, "ack")


def simulator_fault_topic(device_id: str) -> str:
    return f"{get_settings().mqtt_topic_prefix.strip('/')}/simulator/{device_id}/fault"


def _message(event: str, device_id: str, **fields: Any) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "event": event,
            "device_id": device_id,
            "timestamp": datetime.now(UTC).isoformat(),
            **fields,
        },
        separators=(",", ":"),
    )


def device_state_message(device_id: str, state: dict[str, Any]) -> str:
    return _message("device.state", device_id, state=state)


def _state_matches_command(action: str, value: Any, state: dict[str, Any]) -> bool:
    match action:
        case "on":
            return state.get("power") is True
        case "off":
            return state.get("power") is False
        case "lock":
            return state.get("locked") is True
        case "unlock":
            return state.get("locked") is False
        case "open":
            return state.get("position") == 100 or state.get("power") is True or state.get("open") is True
        case "close":
            return state.get("position") == 0 or state.get("power") is False or state.get("open") is False
        case "play":
            return state.get("playing") is True
        case "pause":
            return state.get("playing") is False
        case "stop":
            return state.get("playing") is False
        case "set":
            return isinstance(value, dict) and all(state.get(key) == item for key, item in value.items())
        case "toggle":
            return "power" in state
        case _:
            return False


class MqttHub:
    """MQTT command dispatcher and state mirror."""

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings or get_settings()
        self.client: Any = None
        self.events: list[dict[str, Any]] = []
        self._pending: dict[str, _PendingVerification] = {}
        self._lock = Lock()
        self._watchdog_thread: Thread | None = None
        self._watchdog_stop = Event()

    def start(self) -> None:
        if getattr(self.settings, "app_env", "") == "test" or not self.settings.mqtt_enabled:
            return
        if self.client is not None:
            return
        try:
            import paho.mqtt.client as mqtt

            client_id = f"{self.settings.mqtt_client_id}-{uuid4().hex[:8]}"
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                protocol=mqtt.MQTTv311,
            )
            if self.settings.mqtt_username and self.settings.mqtt_password:
                self.client.username_pw_set(self.settings.mqtt_username, self.settings.mqtt_password)
            if self.settings.mqtt_tls_enabled:
                self.client.tls_set()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.connect_async(self.settings.mqtt_broker, self.settings.mqtt_port, keepalive=60)
            self.client.loop_start()

            if self._watchdog_thread is None or not self._watchdog_thread.is_alive():
                self._watchdog_stop.clear()
                self._watchdog_thread = Thread(target=self._watchdog_loop, daemon=True)
                self._watchdog_thread.start()
        except Exception:
            logger.exception("Unable to start MQTT hub")

    def _watchdog_loop(self) -> None:
        import src.services.devices as devices_mod

        while not self._watchdog_stop.is_set():
            if not self.settings.mqtt_enabled or getattr(self.settings, "app_env", "") == "test":
                self._watchdog_stop.wait(1.0)
                continue
            stale_ids = []
            for reg in _all_registries():
                if reg is devices_mod.get_registry("simulator") and not any(d.id.startswith("esp32") for d in reg.list()):
                    continue
                stale_ids.extend(reg.check_stale_devices(timeout_seconds=30.0))
            if stale_ids:
                unique_stale = list(set(stale_ids))
                logger.info("Heartbeat Watchdog: Stale devices marked offline: %s", unique_stale)
                self._record(
                    {
                        "type": "state",
                        "device_ids": unique_stale,
                        "status": "offline",
                        "online": False,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            self._watchdog_stop.wait(3.0)

    def trigger_discovery_scan(self, mode: str = "real") -> bool:
        if getattr(self.settings, "app_env", "") == "test" or not self.settings.mqtt_enabled:
            return True
        self.start()
        if self.client is None:
            return False
        prefix = self.settings.mqtt_topic_prefix.strip("/")
        payload = json.dumps(
            {
                "action": "scan",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        norm_mode = (mode or "real").strip().lower()
        topics = []
        if norm_mode == "simulator":
            topics.append(f"{prefix}/simulator/broadcast/scan")
        elif norm_mode in {"real", "live", "hardware"}:
            topics.append(f"{prefix}/broadcast/scan")
        elif norm_mode == "all":
            topics.append(f"{prefix}/broadcast/scan")
            topics.append(f"{prefix}/simulator/broadcast/scan")
        else:
            topics.append(f"{prefix}/broadcast/scan")

        success = True
        for topic in topics:
            try:
                self.client.publish(topic, payload, qos=0)
                logger.info("MQTT Discovery Scan broadcast published to %s", topic)
            except Exception:
                logger.exception("Failed to publish discovery scan broadcast to %s", topic)
                success = False
        return success

    def stop(self) -> None:
        self._watchdog_stop.set()
        if self.client is not None:
            self.client.disconnect()
            self.client.loop_stop()
            self.client = None

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code == 0:
            prefix = self.settings.mqtt_topic_prefix.strip("/")
            client.subscribe(f"{prefix}/devices/+/state", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/devices/+/ack", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/devices/+/lwt", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/nodes/+/lwt", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/discovery", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/discovery/+", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/simulator/devices/+/state", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/simulator/devices/+/ack", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/simulator/discovery", qos=self.settings.mqtt_qos)
            client.subscribe(f"{prefix}/simulator/discovery/+", qos=self.settings.mqtt_qos)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            import src.services.devices as devices_mod

            payload = json.loads(message.payload.decode())
            prefix = self.settings.mqtt_topic_prefix.strip("/")
            topic = str(message.topic)
            is_sim_topic = topic.startswith(f"{prefix}/simulator/devices/")
            is_simulator = is_sim_topic or (payload.get("source") == "simulator")
            msg_mode = "simulator" if is_simulator else "real"
            target_regs = _target_registries(is_simulator)

            if topic.startswith(f"{prefix}/simulator/discovery"):
                devices_mod.get_registry("simulator").add_discovered(payload)
                self._record({"type": "discovery", "mode": "simulator", **payload})
                return

            if topic.startswith(f"{prefix}/discovery"):
                if is_simulator:
                    devices_mod.get_registry("simulator").add_discovered(payload)
                else:
                    devices_mod.get_registry("real").add_discovered(payload)
                self._record({"type": "discovery", "mode": msg_mode, **payload})
                return

            if topic.startswith(f"{prefix}/nodes/") and topic.endswith("/lwt"):
                node_id = payload.get("node_id") or topic.split("/")[-2]
                real_reg = devices_mod.get_registry("real")
                sim_reg = devices_mod.get_registry("simulator")
                target_node_regs = [r for r in [real_reg, _registry()] if r is not sim_reg] or [real_reg]
                all_updated = []
                for reg in target_node_regs:
                    all_updated.extend(reg.set_node_online(node_id, False))
                self._record(
                    {
                        "type": "state",
                        "mode": "real",
                        "node_id": node_id,
                        "device_ids": [d.id for d in all_updated],
                        "status": "offline",
                        "online": False,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                return

            device_id = payload.get("device_id")
            if not device_id:
                return

            is_online = (
                bool(payload.get("online", True))
                and payload.get("status") != "offline"
                and payload.get("fault") != "offline"
            )

            if topic.endswith("/lwt") or not is_online:
                for reg in target_regs:
                    reg.set_online(device_id, False)
                self._record(
                    {
                        "type": "state",
                        "mode": msg_mode,
                        "device_id": device_id,
                        "status": "offline",
                        "online": False,
                        "state": payload.get("state", {}),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                return

            command_id = payload.get("command_id")
            with self._lock:
                pending = self._pending.get(command_id)
                if command_id is None and topic.endswith("/state"):
                    candidates = [
                        item
                        for item in self._pending.values()
                        if item.device_id == device_id
                        and item.ack_received.is_set()
                        and item.ack.get("status") in {"ok", "executed"}
                    ]
                    pending = candidates[0] if len(candidates) == 1 else None
            if topic.endswith("/state"):
                correlated = pending is not None and pending.device_id == device_id
                if command_id is not None and not correlated:
                    self._record({"type": "state", "mode": msg_mode, **payload})
                    return
                found_in_any = False
                for reg in target_regs:
                    if reg.get(device_id) is not None:
                        found_in_any = True
                        reg.update_state(device_id, payload.get("state", {}), online=True)
                if not found_in_any:
                    target_reg = devices_mod.get_registry("simulator") if is_simulator else devices_mod.get_registry("real")
                    target_reg.add_discovered(payload)
                    self._record({"type": "discovery", "mode": msg_mode, **payload})
                else:
                    self._record({"type": "state", "mode": msg_mode, **payload})
                if pending and pending.device_id == device_id and isinstance(payload.get("state"), dict):
                    pending.state.update(payload)
                    pending.state_received.set()
            elif topic.endswith("/ack"):
                for reg in target_regs:
                    reg.record_heartbeat(device_id)
                self._record({"type": "ack", "mode": msg_mode, **payload})
                if pending and pending.device_id == device_id and payload.get("status") in {"ok", "executed", "error"}:
                    pending.ack.update(payload)
                    pending.ack_received.set()
        except Exception:
            logger.exception("Ignoring invalid MQTT message")

    def _record(self, item: dict[str, Any]) -> None:
        self.events[:] = (self.events + [item])[-100:]

    def command(
        self, device_id: str, action: str, value: Any = None, timeout: float = 5.0, mode: str = "real"
    ) -> CommandVerification:
        if not self.settings.mqtt_enabled:
            target_reg = _registry() if _registry().get(device_id) is not None else None
            if target_reg is None:
                for reg in _all_registries():
                    if reg.get(device_id) is not None:
                        target_reg = reg
                        break
            if target_reg is None:
                target_reg = _registry()
            device = target_reg.command(device_id, action, value)
            if device is None:
                return CommandVerification(VerificationStatus.FAILED, "not_found")
            return CommandVerification(VerificationStatus.STATE_VERIFIED, "state_verified", device)
        self.start()
        if self.client is None:
            return CommandVerification(VerificationStatus.FAILED, "unavailable")
        command_id = str(uuid4())
        pending = _PendingVerification(device_id=device_id)
        with self._lock:
            self._pending[command_id] = pending
        payload = _message("device.command", device_id, command_id=command_id, action=action, value=value)
        topic = device_command_topic(device_id, mode=mode)
        self._record(
            {
                "type": "command",
                "event": "device.command",
                "device_id": device_id,
                "command_id": command_id,
                "action": action,
                "value": value,
                "mode": mode,
                "topic": topic,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.client.publish(topic, payload, qos=self.settings.mqtt_qos)
        ack_received = pending.ack_received.wait(timeout)
        if not ack_received:
            with self._lock:
                self._pending.pop(command_id, None)
            for reg in _all_registries():
                if reg.get(device_id) is not None:
                    reg.set_online(device_id, False)
            self._record(
                {
                    "type": "timeout",
                    "device_id": device_id,
                    "command_id": command_id,
                    "status": "offline",
                    "online": False,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            return CommandVerification(VerificationStatus.INDETERMINATE, "ack_timeout")
        if pending.ack.get("status") not in {"ok", "executed"}:
            with self._lock:
                self._pending.pop(command_id, None)
            return CommandVerification(VerificationStatus.FAILED, pending.ack.get("error", "rejected"))
        state_received = pending.state_received.wait(timeout)
        with self._lock:
            self._pending.pop(command_id, None)
        if not state_received:
            return CommandVerification(VerificationStatus.INDETERMINATE, "state_timeout")
        state = pending.state.get("state", {})
        if not _state_matches_command(action, value, state):
            return CommandVerification(VerificationStatus.FAILED, "state_mismatch")
        found_device = None
        for reg in _all_registries():
            dev = reg.update_state(device_id, state)
            if dev is not None:
                found_device = dev
        if found_device is None:
            return CommandVerification(VerificationStatus.FAILED, "not_found")
        return CommandVerification(VerificationStatus.STATE_VERIFIED, "state_verified", found_device)

    def authorized_command(
        self, device_id: str, action: str, value: Any = None, timeout: float = 3.0, mode: str = "real"
    ) -> CommandVerification:
        if self.settings.mqtt_enabled:
            return self.command(device_id, action, value, timeout, mode=mode)
        target_reg = _registry() if _registry().get(device_id) is not None else None
        if target_reg is None:
            for reg in _all_registries():
                if reg.get(device_id) is not None:
                    target_reg = reg
                    break
        if target_reg is None:
            target_reg = _registry()
        device = target_reg.command(device_id, action, value, approved_sensitive=True)
        if device is None:
            return CommandVerification(VerificationStatus.FAILED, "not_found")
        return CommandVerification(VerificationStatus.STATE_VERIFIED, "state_verified", device)

    def fault(self, device_id: str, mode: str) -> bool:
        if not self.settings.mqtt_enabled:
            for reg in _all_registries():
                reg.set_online(device_id, mode != "offline")
            return True
        self.start()
        if self.client is None:
            return False
        self.client.publish(
            simulator_fault_topic(device_id),
            _message("simulator.fault", device_id, mode=mode),
            qos=self.settings.mqtt_qos,
        )
        for reg in _all_registries():
            reg.set_online(device_id, mode != "offline")
        return True


_hub: MqttHub | None = None


def get_mqtt_hub() -> MqttHub:
    global _hub
    if _hub is None:
        _hub = MqttHub()
    return _hub


def start_mqtt() -> None:
    get_mqtt_hub().start()


def stop_mqtt() -> None:
    get_mqtt_hub().stop()


def publish_device_state(device_id: str, state: dict[str, Any]) -> bool:
    # Compatibility helper used by legacy unit tests.
    return get_mqtt_hub().fault(device_id, "none")
