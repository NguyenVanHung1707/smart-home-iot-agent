import pytest
from unittest.mock import AsyncMock, Mock

import src.services.devices as devices_mod
from src.api import routes
from src.services.device_control import control_device
from src.services.xiaozhi import xiaozhi_service


@pytest.mark.asyncio
async def test_xiaozhi_service_processes_real_device_command(monkeypatch):
    """Xiaozhi AI controls physical real devices and isolates from simulator."""
    real_reg = devices_mod.get_registry("real")
    real_reg.set_online("living-light", True)

    published_speaker = []

    class MockHub:
        client = Mock()

        def command(self, dev_id, action, value=None, mode=None):
            return {
                "id": dev_id,
                "name": "Đèn phòng khách",
                "room": "Phòng khách",
                "kind": "light",
                "state": {"power": action == "on"},
            }, None

    mock_hub = MockHub()
    mock_hub.client.publish = lambda topic, payload, qos=0: published_speaker.append((topic, payload))
    monkeypatch.setattr("src.services.xiaozhi.get_mqtt_hub", lambda: mock_hub)
    monkeypatch.setattr("src.services.device_control.get_mqtt_hub", lambda: mock_hub)

    result = await xiaozhi_service.process("bật đèn phòng khách", session_id="test-session-real")

    assert result["metadata"]["ai_engine"] == "xiaozhi_ai"
    assert result["metadata"]["mode"] == "real"
    assert "Xiaozhi đã bật" in result["response"]
    assert any("homing/speaker/say" in topic for topic, _ in published_speaker)


@pytest.mark.asyncio
async def test_xiaozhi_service_handles_sensor_inquiries(monkeypatch):
    """Xiaozhi AI answers sensor inquiries based on real hardware data."""
    real_reg = devices_mod.get_registry("real")
    real_reg.update_state("living-temperature", {"temperature": 27.5, "humidity": 65}, online=True)
    real_reg.update_state("kitchen-gas", {"gas": 120}, online=True)

    result_temp = await xiaozhi_service.process("nhiệt độ trong nhà bao nhiêu độ")
    assert "27.5°C" in result_temp["response"]
    assert "65%" in result_temp["response"]

    result_gas = await xiaozhi_service.process("kiểm tra rò rỉ khí gas")
    assert "120 ppm" in result_gas["response"]
    assert "an toàn" in result_gas["response"]


def test_strict_mode_isolation_prevents_cross_registry_leakage():
    """Real mode must reject simulator-only devices; simulator mode must reject real-only devices."""
    # living-aircon is ONLY in simulator, NOT in real
    dev_real, err_real = control_device("living-aircon", "on", mode="real")
    assert dev_real is None
    assert err_real == "device_not_found_in_real"

    # living-fan is ONLY in real, NOT in simulator
    dev_sim, err_sim = control_device("living-fan", "on", mode="simulator")
    assert dev_sim is None
    assert err_sim == "device_not_found_in_simulator"


@pytest.mark.asyncio
async def test_api_status_reports_correct_engine_per_mode(client):
    """Status endpoint must report Xiaozhi AI for real and Local Model for simulator."""
    res_real = await client.get("/api/v1/status", headers={"X-Data-Mode": "real"})
    assert res_real.status_code == 200
    assert res_real.json()["ai_engine"] == "xiaozhi_ai"
    assert "Xiaozhi" in res_real.json()["agent"]

    res_sim = await client.get("/api/v1/status", headers={"X-Data-Mode": "simulator"})
    assert res_sim.status_code == 200
    assert res_sim.json()["ai_engine"] == "local_model"
    assert "Local Model" in res_sim.json()["agent"]


@pytest.mark.asyncio
async def test_api_voice_process_routes_to_xiaozhi_in_real_mode(client, monkeypatch):
    """POST /voice/process routes to Xiaozhi AI when X-Data-Mode is real."""
    mock_process = AsyncMock(
        return_value={
            "transcript": "bật đèn phòng khách",
            "response": "Xiaozhi đã bật Đèn phòng khách.",
            "analysis": "xiaozhi_device_control",
            "metadata": {"commands": [{"device_id": "living-light", "action": "on"}], "ai_engine": "xiaozhi_ai"},
            "session_id": "session-real-123",
        }
    )
    monkeypatch.setattr(routes.xiaozhi_service, "process", mock_process)

    response = await client.post(
        "/api/v1/voice/process",
        json={"transcript": "bật đèn phòng khách", "session_id": "session-real-123"},
        headers={"X-Data-Mode": "real"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ai_engine"] == "xiaozhi_ai"
    assert data["mode"] == "real"
    assert data["response"] == "Xiaozhi đã bật Đèn phòng khách."
    mock_process.assert_awaited_once_with("bật đèn phòng khách", session_id="session-real-123")
