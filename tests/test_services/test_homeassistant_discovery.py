"""Tests for Home Assistant MQTT Discovery integration."""

from unittest.mock import MagicMock

import pytest

from fastapi.testclient import TestClient

from src.main import app
from src.models.schemas import Device
from src.services.homeassistant_discovery import (
    build_ha_discovery_payload,
    publish_all_devices_discovery,
    publish_homeassistant_discovery,
)


def test_build_ha_discovery_payload_light():
    dev = Device(
        id="light_living",
        name="Đèn trần",
        room="Phòng khách",
        kind="light",
        online=True,
        state={"power": True, "brightness": 80},
        capabilities={"brightness": True},
    )
    payloads = build_ha_discovery_payload(dev)
    assert len(payloads) == 1
    topic, config = payloads[0]
    assert topic == "homeassistant/light/homing_light_living/config"
    assert config["name"] == "Đèn trần"
    assert config["schema"] == "json"
    assert config["brightness"] is True
    assert config["device"]["suggested_area"] == "Phòng khách"


def test_build_ha_discovery_payload_aircon():
    dev = Device(
        id="ac_bedroom",
        name="Điều hòa",
        room="Phòng ngủ",
        kind="aircon",
        online=True,
        state={"power": True, "target_temperature": 25, "mode": "cool"},
        capabilities={"target_temperature": {"min": 16, "max": 30}},
    )
    payloads = build_ha_discovery_payload(dev)
    assert len(payloads) == 1
    topic, config = payloads[0]
    assert topic == "homeassistant/climate/homing_ac_bedroom/config"
    assert config["min_temp"] == 16
    assert config["max_temp"] == 30
    assert "cool" in config["modes"]


def test_build_ha_discovery_payload_sensor():
    dev = Device(
        id="sensor_env",
        name="Cảm biến môi trường",
        room="Phòng khách",
        kind="sensor",
        online=True,
        state={"temperature": 27.5, "humidity": 65},
        capabilities={"telemetry": {"temperature": {}, "humidity": {}}},
    )
    payloads = build_ha_discovery_payload(dev)
    assert len(payloads) == 2
    topics = [p[0] for p in payloads]
    assert "homeassistant/sensor/homing_sensor_env_temperature/config" in topics
    assert "homeassistant/sensor/homing_sensor_env_humidity/config" in topics


def test_publish_homeassistant_discovery():
    mock_hub = MagicMock()
    mock_hub.client = MagicMock()

    dev = Device(
        id="blind_balcony",
        name="Rèm ban công",
        room="Ban công",
        kind="blind",
        online=True,
        state={"position": 100},
        capabilities={},
    )
    published = publish_homeassistant_discovery(dev, mqtt_client=mock_hub)
    assert published == 1
    mock_hub.client.publish.assert_called_once()
    args, kwargs = mock_hub.client.publish.call_args
    assert args[0] == "homeassistant/cover/homing_blind_balcony/config"
    assert kwargs.get("retain") is True


def test_publish_all_devices_discovery():
    mock_hub = MagicMock()
    mock_hub.client = MagicMock()

    devices = [
        Device(id="d1", name="Light 1", room="R1", kind="light", online=True, state={}, capabilities={}),
        Device(id="d2", name="Door Lock", room="R1", kind="lock", online=True, state={}, capabilities={}),
    ]
    total = publish_all_devices_discovery(devices, mqtt_client=mock_hub)
    assert total == 2
    assert mock_hub.client.publish.call_count == 2


@pytest.mark.asyncio
async def test_sync_homeassistant_route(client):
    response = await client.post("/api/v1/integrations/homeassistant/sync")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "device_count" in data
    assert "entities_published" in data

