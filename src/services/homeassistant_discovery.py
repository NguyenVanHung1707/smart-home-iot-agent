"""Home Assistant MQTT Discovery provider for Homing Hub.

Automatically publishes standard Home Assistant MQTT Discovery configuration
payloads (with retain=True) so that Home Assistant, Apple HomeKit (via HASS
HomeKit Bridge), and Google Home (via HASS Google Assistant) seamlessly discover
and control all Homing smart-home devices.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config import get_settings
from src.models.schemas import Device

logger = logging.getLogger(__name__)


def build_ha_discovery_payload(device: Device) -> list[tuple[str, dict[str, Any]]]:
    """Return a list of (discovery_topic, config_payload) for the given device."""
    settings = get_settings()
    prefix = settings.mqtt_topic_prefix.strip("/")
    device_id = device.id
    name = device.name or device_id
    room = device.room or "Living Room"
    kind = (device.kind or "light").lower()

    base_device_info = {
        "identifiers": [f"homing_{device_id}"],
        "name": f"HomeMind {name}",
        "suggested_area": room,
        "manufacturer": "HomeMind Hub (VinAI P-140)",
        "model": f"ESP32 {kind.title()}",
        "sw_version": "1.0.0",
    }

    results: list[tuple[str, dict[str, Any]]] = []

    if kind == "light":
        topic = f"homeassistant/light/homing_{device_id}/config"
        payload = {
            "name": name,
            "unique_id": f"homing_light_{device_id}",
            "command_topic": f"{prefix}/devices/{device_id}/command",
            "state_topic": f"{prefix}/devices/{device_id}/state",
            "schema": "json",
            "brightness": True,
            "brightness_scale": 100,
            "device": base_device_info,
        }
        results.append((topic, payload))

    elif kind == "aircon":
        topic = f"homeassistant/climate/homing_{device_id}/config"
        payload = {
            "name": name,
            "unique_id": f"homing_climate_{device_id}",
            "mode_command_topic": f"{prefix}/devices/{device_id}/command",
            "mode_state_topic": f"{prefix}/devices/{device_id}/state",
            "mode_state_template": "{{ value_json.mode | default('cool') }}",
            "temperature_command_topic": f"{prefix}/devices/{device_id}/command",
            "temperature_state_topic": f"{prefix}/devices/{device_id}/state",
            "temperature_state_template": "{{ value_json.target_temperature | default(24) }}",
            "modes": ["off", "cool", "heat", "fan_only", "dry"],
            "min_temp": 16,
            "max_temp": 30,
            "temp_step": 1.0,
            "device": base_device_info,
        }
        results.append((topic, payload))

    elif kind == "blind":
        topic = f"homeassistant/cover/homing_{device_id}/config"
        payload = {
            "name": name,
            "unique_id": f"homing_cover_{device_id}",
            "command_topic": f"{prefix}/devices/{device_id}/command",
            "position_topic": f"{prefix}/devices/{device_id}/state",
            "position_template": "{{ value_json.position | default(0) }}",
            "set_position_topic": f"{prefix}/devices/{device_id}/command",
            "position_open": 100,
            "position_closed": 0,
            "device": base_device_info,
        }
        results.append((topic, payload))

    elif kind == "speaker":
        topic = f"homeassistant/media_player/homing_{device_id}/config"
        payload = {
            "name": name,
            "unique_id": f"homing_speaker_{device_id}",
            "command_topic": f"{prefix}/devices/{device_id}/command",
            "state_topic": f"{prefix}/devices/{device_id}/state",
            "device": base_device_info,
        }
        results.append((topic, payload))

    elif kind == "lock":
        topic = f"homeassistant/lock/homing_{device_id}/config"
        payload = {
            "name": name,
            "unique_id": f"homing_lock_{device_id}",
            "command_topic": f"{prefix}/devices/{device_id}/command",
            "state_topic": f"{prefix}/devices/{device_id}/state",
            "state_locked": "LOCKED",
            "state_unlocked": "UNLOCKED",
            "payload_lock": json.dumps({"action": "lock"}),
            "payload_unlock": json.dumps({"action": "unlock"}),
            "device": base_device_info,
        }
        results.append((topic, payload))

    elif kind == "sensor":
        telemetry = device.capabilities.get("telemetry", {}) if isinstance(device.capabilities, dict) else {}
        metrics = list(telemetry.keys()) if telemetry else ["temperature", "humidity", "gas"]
        for metric in metrics:
            topic = f"homeassistant/sensor/homing_{device_id}_{metric}/config"
            unit = (
                "°C" if metric == "temperature" else "%" if metric == "humidity" else "ppm" if metric == "gas" else None
            )
            dev_class = (
                "temperature"
                if metric == "temperature"
                else "humidity"
                if metric == "humidity"
                else "gas"
                if metric == "gas"
                else None
            )
            payload = {
                "name": f"{name} {metric.capitalize()}",
                "unique_id": f"homing_sensor_{device_id}_{metric}",
                "state_topic": f"{prefix}/devices/{device_id}/state",
                "value_template": f"{{{{ value_json.{metric} | default(0) }}}}",
                "device": base_device_info,
            }
            if unit:
                payload["unit_of_measurement"] = unit
            if dev_class:
                payload["device_class"] = dev_class
            results.append((topic, payload))

    return results


def publish_homeassistant_discovery(device: Device, mqtt_client: Any = None) -> int:
    """Publish Home Assistant MQTT Discovery payloads for a device."""
    try:
        from src.services.mqtt import get_mqtt_hub

        hub = mqtt_client or get_mqtt_hub()
        if not getattr(hub, "client", None):
            return 0

        items = build_ha_discovery_payload(device)
        published_count = 0
        for topic, payload in items:
            payload_str = json.dumps(payload, ensure_ascii=False)
            hub.client.publish(topic, payload_str, qos=1, retain=True)
            published_count += 1
            logger.debug("Published Home Assistant Discovery: %s", topic)
        return published_count
    except Exception as e:
        logger.warning("Could not publish Home Assistant discovery for %s: %s", device.id, e)
        return 0


def publish_all_devices_discovery(devices: list[Device], mqtt_client: Any = None) -> int:
    """Publish discovery configs for all registered devices."""
    total = 0
    for dev in devices:
        total += publish_homeassistant_discovery(dev, mqtt_client=mqtt_client)
    logger.info("Published Home Assistant Discovery configs for %d devices (%d entities total)", len(devices), total)
    return total
