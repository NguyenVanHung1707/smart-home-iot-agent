import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import src.main as main
from src.api import routes
from src.config import Settings
from src.services.speech import NoSpeechDetectedError, SpeechUnavailableError, Synthesis, Transcription


def wav_bytes(seconds: float = 0.1, rate: int = 16_000, channels: int = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * round(seconds * rate) * channels)
    return output.getvalue()


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_lifespan_keeps_text_backend_up_without_zipformer_model(monkeypatch):
    runtime = SimpleNamespace(preload=Mock(return_value=False))
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, voice_enabled=True))
    monkeypatch.setattr(main, "get_speech_runtime", lambda: runtime)
    monkeypatch.setattr(main, "start_mqtt", Mock())
    monkeypatch.setattr(main, "stop_mqtt", Mock())

    async with main.lifespan(main.app):
        pass

    runtime.preload.assert_called_once()


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_chat_rejects_unknown_fields(client):
    response = await client.post("/api/v1/chat", json={"message": "xin chào", "role": "system"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_uses_deterministic_fallback_when_agent_fails(client, monkeypatch):
    failing_agent = AsyncMock(side_effect=RuntimeError("llama unavailable"))
    monkeypatch.setattr(routes, "agent", SimpleNamespace(ainvoke=failing_agent))

    response = await client.post("/api/v1/chat", json={"message": "xin chao"})

    assert response.status_code == 200
    assert response.json()["response"]
    assert response.json()["session_id"]
    failing_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_uses_fallback_when_agent_response_is_empty(client, monkeypatch):
    agent_mock = AsyncMock(return_value={"response": "", "fallback_required": True})
    fallback_mock = AsyncMock(return_value={"response": "Đã bật Đèn phòng ngủ."})
    monkeypatch.setattr(routes, "agent", SimpleNamespace(ainvoke=agent_mock))
    monkeypatch.setattr(routes, "fallback_node", fallback_mock)

    response = await client.post("/api/v1/chat", json={"message": "bật đèn phòng ngủ"})

    assert response.status_code == 200
    assert response.json()["response"] == "Đã bật Đèn phòng ngủ."
    agent_mock.assert_awaited_once()
    fallback_mock.assert_awaited_once()
    assert fallback_mock.await_args.args[0]["query"] == "bật đèn phòng ngủ"


@pytest.mark.asyncio
async def test_voice_uses_deterministic_fallback_when_agent_fails(client, monkeypatch):
    failing_agent = AsyncMock(side_effect=TimeoutError("llama timeout"))
    monkeypatch.setattr(routes, "agent", SimpleNamespace(ainvoke=failing_agent))

    response = await client.post("/api/v1/voice/process", json={"transcript": "xin chao"})

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "xin chao"
    assert data["response"]
    assert isinstance(data["plan"], list)
    assert data["session_id"]
    failing_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_text_and_voice_share_history_for_same_session(client, monkeypatch):
    routes.conversations.clear("shared-session")
    agent_mock = AsyncMock(
        side_effect=[
            {"response": "Bạn muốn phòng nào?"},
            {"response": "Đã bật đèn phòng ngủ."},
        ]
    )
    monkeypatch.setattr(routes, "agent", SimpleNamespace(ainvoke=agent_mock))

    chat = await client.post(
        "/api/v1/chat",
        json={"message": "bật đèn", "session_id": "shared-session"},
    )
    voice = await client.post(
        "/api/v1/voice/process",
        json={"transcript": "phòng ngủ", "session_id": "shared-session"},
    )

    assert chat.json()["session_id"] == "shared-session"
    assert voice.json()["session_id"] == "shared-session"
    second_messages = agent_mock.await_args_list[1].args[0]["messages"]
    assert [message.content for message in second_messages] == [
        "bật đèn",
        "Bạn muốn phòng nào?",
        "phòng ngủ",
    ]


@pytest.mark.asyncio
async def test_chat_rejects_invalid_session_id(client):
    response = await client.post(
        "/api/v1/chat",
        json={"message": "xin chào", "session_id": "not allowed/space"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_voice_transcribe_returns_runtime_metadata(client, monkeypatch):
    runtime = SimpleNamespace(
        transcribe=AsyncMock(
            return_value=Transcription(
                text="bật đèn phòng khách",
                language="vi",
                duration_ms=100,
                latency_ms=42,
                model="sherpa-onnx-zipformer-vi-int8-2025-04-20",
                vad_applied=False,
            )
        )
    )
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("command.wav", wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "bật đèn phòng khách",
        "language": "vi",
        "audio_duration_ms": 100,
        "stt_latency_ms": 42,
        "model": "sherpa-onnx-zipformer-vi-int8-2025-04-20",
        "vad_applied": False,
    }
    runtime.transcribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_unsupported_media_type(client):
    response = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("command.webm", b"not wav", "audio/webm")},
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_voice_transcribe_maps_no_speech_to_422(client, monkeypatch):
    runtime = SimpleNamespace(transcribe=AsyncMock(side_effect=NoSpeechDetectedError("no_speech_detected")))
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("command.wav", wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "no_speech_detected"


@pytest.mark.asyncio
async def test_voice_transcribe_maps_zipformer_failure_to_stt_unavailable(client, monkeypatch):
    runtime = SimpleNamespace(transcribe=AsyncMock(side_effect=SpeechUnavailableError("stt_unavailable")))
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("command.wav", wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "stt_unavailable"


@pytest.mark.asyncio
async def test_voice_synthesize_streams_wav(client, monkeypatch):
    runtime = SimpleNamespace(
        synthesize=AsyncMock(return_value=Synthesis(audio=wav_bytes(), latency_ms=35, voice="vi_VN-vais1000-medium"))
    )
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.post("/api/v1/voice/synthesize", json={"text": "Đã bật đèn."})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-tts-voice"] == "vi_VN-vais1000-medium"
    assert response.headers["x-tts-latency-ms"] == "35"
    assert response.content.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_voice_synthesize_keeps_text_fallback_when_piper_is_unavailable(client, monkeypatch):
    runtime = SimpleNamespace(synthesize=AsyncMock(side_effect=SpeechUnavailableError("piper_unavailable")))
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.post("/api/v1/voice/synthesize", json={"text": "Đã bật đèn."})

    assert response.status_code == 503
    assert response.json()["detail"] == "piper_unavailable"


@pytest.mark.asyncio
async def test_voice_status_uses_runtime(client, monkeypatch):
    runtime = SimpleNamespace(status=AsyncMock(return_value={"enabled": True, "ready": True}))
    monkeypatch.setattr(routes, "get_speech_runtime", lambda: runtime)

    response = await client.get("/api/v1/voice/status")

    assert response.status_code == 200
    assert response.json()["ready"] is True


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_lock_unlock_creates_approval(client):
    response = await client.post("/api/v1/devices/entry-lock/command", json={"action": "unlock"})

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_unknown_device_command_is_404(client):
    response = await client.post("/api/v1/devices/nope/command", json={"action": "on"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sensor_rejects_control_action(client):
    response = await client.post("/api/v1/devices/living-temperature/command", json={"action": "on"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_device_command_rejects_unknown_set_field(client):
    response = await client.post(
        "/api/v1/devices/living-light/command",
        json={"action": "set", "value": {"temperature": 99}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported_set_field:temperature"


@pytest.mark.asyncio
async def test_unlock_rejects_unexpected_value_before_approval(client):
    response = await client.post(
        "/api/v1/devices/entry-lock/command",
        json={"action": "unlock", "value": {"force": True}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unexpected_value"


@pytest.mark.parametrize("error_code", ["timeout", "ack_timeout", "state_timeout"])
@pytest.mark.asyncio
async def test_device_command_timeout_variations_return_504(client, monkeypatch, error_code):
    monkeypatch.setattr(
        "src.api.routes.control_device",
        lambda *args, **kwargs: (None, error_code),
    )
    response = await client.post(
        "/api/v1/devices/living-light/command",
        json={"action": "on"},
    )
    assert response.status_code == 504
    assert response.json()["detail"] == "Device acknowledgement timed out"


@pytest.mark.asyncio
async def test_device_command_mode_propagation(client, monkeypatch):
    from src.models.schemas import Device

    mock_device = Device(
        id="living-light",
        name="Đèn phòng khách",
        room="Phòng khách",
        kind="light",
        state={"power": True},
    )

    recorded_modes = []

    def mock_control_device(*args, **kwargs):
        recorded_modes.append(kwargs.get("mode"))
        return (mock_device, None)

    monkeypatch.setattr("src.api.routes.control_device", mock_control_device)

    import src.services.devices as devices_mod
    devices_mod.get_registry("real").set_online("living-light", True)

    # 1. Default (no header, no query param) -> "simulator"
    resp = await client.post("/api/v1/devices/living-light/command", json={"action": "on"})
    assert resp.status_code == 200
    assert recorded_modes[-1] == "simulator"

    # 2. Query param ?mode=real -> "real"
    resp = await client.post("/api/v1/devices/living-light/command?mode=real", json={"action": "on"})
    assert resp.status_code == 200
    assert recorded_modes[-1] == "real"

    # 3. Header X-Data-Mode: real -> "real"
    resp = await client.post(
        "/api/v1/devices/living-light/command",
        headers={"X-Data-Mode": "real"},
        json={"action": "on"},
    )
    assert resp.status_code == 200
    assert recorded_modes[-1] == "real"


@pytest.mark.asyncio
async def test_chat_data_mode_isolation_simulator_vs_real(client):
    """Verify complete isolation between Simulator and Real ESP32 data streams in /chat."""
    query = "trong phòng khách có bao nhiêu thiết bị"

    # 1. Simulator mode
    sim_resp = await client.post(
        "/api/v1/chat",
        headers={"X-Data-Mode": "simulator"},
        json={"message": query},
    )
    assert sim_resp.status_code == 200
    sim_text = sim_resp.json()["response"]
    assert "Điều hòa" in sim_text
    assert "Quạt" not in sim_text

    # 2. Real ESP32 mode
    real_resp = await client.post(
        "/api/v1/chat",
        headers={"X-Data-Mode": "real"},
        json={"message": query},
    )
    assert real_resp.status_code == 200
    real_text = real_resp.json()["response"]
    assert "Quạt" in real_text
    assert "Điều hòa" not in real_text


@pytest.mark.asyncio
async def test_voice_data_mode_isolation_simulator_vs_real(client):
    """Verify complete isolation between Simulator and Real ESP32 data streams in /voice and /voice/process."""
    transcript = "trong phòng khách có bao nhiêu thiết bị"

    # 1. Voice process with simulator
    sim_resp = await client.post(
        "/api/v1/voice/process",
        headers={"X-Data-Mode": "simulator"},
        json={"transcript": transcript},
    )
    assert sim_resp.status_code == 200
    sim_text = sim_resp.json()["response"]
    assert "Điều hòa" in sim_text
    assert "Quạt" not in sim_text

    # 2. Voice process with real mode
    real_resp = await client.post(
        "/api/v1/voice/process",
        headers={"X-Data-Mode": "real"},
        json={"transcript": transcript},
    )
    assert real_resp.status_code == 200
    real_text = real_resp.json()["response"]
    assert "Quạt" in real_text
    assert "Điều hòa" not in real_text

    # 3. Direct /voice endpoint with query param mode=real
    voice_query_resp = await client.post(
        "/api/v1/voice?mode=real",
        json={"transcript": transcript},
    )
    assert voice_query_resp.status_code == 200
    voice_text = voice_query_resp.json()["response"]
    assert "Quạt" in voice_text
    assert "Điều hòa" not in voice_text


@pytest.mark.asyncio
async def test_status_endpoint_reflects_data_mode(client):
    # Default without header -> simulator
    resp_default = await client.get("/api/v1/status")
    assert resp_default.status_code == 200
    assert resp_default.json()["mode"] == "simulator"

    # Header X-Data-Mode: real
    resp_real = await client.get("/api/v1/status", headers={"X-Data-Mode": "real"})
    assert resp_real.status_code == 200
    assert resp_real.json()["mode"] == "real"

    # Header X-Data-Mode: simulator
    resp_sim = await client.get("/api/v1/status", headers={"X-Data-Mode": "simulator"})
    assert resp_sim.status_code == 200
    assert resp_sim.json()["mode"] == "simulator"

    # Query param ?mode=real
    resp_query = await client.get("/api/v1/status?mode=real")
    assert resp_query.status_code == 200
    assert resp_query.json()["mode"] == "real"


@pytest.mark.asyncio
async def test_simulator_events_filters_out_hardware_events(client, monkeypatch):
    mock_events = [
        {"mode": "simulator", "topic": "homing/sim/living-light", "data": "on"},
        {"source": "simulator", "topic": "homing/devices/kitchen", "data": "off"},
        {"topic": "homing/simulator/status", "data": "online"},
        {"mode": "real", "source": "esp32", "topic": "homing/esp32/telemetry", "data": "temp"},
        {"source": "esp32_hardware", "topic": "homing/esp32/relay", "data": "off"},
    ]
    from src.services.mqtt import get_mqtt_hub

    hub = get_mqtt_hub()
    monkeypatch.setattr(hub, "events", mock_events)

    # 1. Simulator events query
    response_sim = await client.get("/api/v1/simulator/events", headers={"X-Data-Mode": "simulator"})
    assert response_sim.status_code == 200
    events_sim = response_sim.json()
    assert len(events_sim) == 3
    assert events_sim[0]["mode"] == "simulator"
    assert events_sim[1]["source"] == "simulator"
    assert "simulator" in events_sim[2]["topic"]

    # 2. Real events query
    response_real = await client.get("/api/v1/simulator/events", headers={"X-Data-Mode": "real"})
    assert response_real.status_code == 200
    events_real = response_real.json()
    assert len(events_real) == 2
    assert events_real[0]["data"] == "temp"
    assert events_real[1]["data"] == "off"


@pytest.mark.asyncio
async def test_approvals_list_filters_by_data_mode(client):
    from src.services.approvals import approvals

    # Clear approvals store
    approvals._items.clear()

    # Create one simulator approval and one real approval
    approvals.create("living-lock", {"action": "unlock"}, requested_by="Alice", mode="simulator")
    approvals.create("entry-lock", {"action": "unlock"}, requested_by="Bob", mode="real")

    # 1. List approvals in simulator mode
    resp_sim = await client.get("/api/v1/approvals", headers={"X-Data-Mode": "simulator"})
    assert resp_sim.status_code == 200
    items_sim = resp_sim.json()
    assert len(items_sim) == 1
    assert items_sim[0]["device_id"] == "living-lock"
    assert items_sim[0]["mode"] == "simulator"

    # 2. List approvals in real mode
    resp_real = await client.get("/api/v1/approvals", headers={"X-Data-Mode": "real"})
    assert resp_real.status_code == 200
    items_real = resp_real.json()
    assert len(items_real) == 1
    assert items_real[0]["device_id"] == "entry-lock"
    assert items_real[0]["mode"] == "real"


@pytest.mark.asyncio
async def test_approval_preserves_and_executes_in_original_mode(client, monkeypatch):
    from src.models.schemas import Device

    mock_device = Device(
        id="entry-lock",
        name="Khóa cửa chính",
        room="Cửa chính",
        kind="lock",
        state={"locked": False},
    )

    recorded_modes = []

    def mock_control_device(*args, **kwargs):
        recorded_modes.append(kwargs.get("mode"))
        return (mock_device, None)

    monkeypatch.setattr("src.api.routes.control_device", mock_control_device)

    import src.services.devices as devices_mod
    devices_mod.get_registry("real").set_online("entry-lock", True)

    # 1. Request approval in "real" mode
    resp_create = await client.post(
        "/api/v1/devices/entry-lock/command",
        headers={"X-Data-Mode": "real"},
        json={"action": "unlock"},
    )
    assert resp_create.status_code == 200
    approval_data = resp_create.json()
    assert approval_data["status"] == "pending"
    assert approval_data.get("mode") == "real"
    approval_id = approval_data["id"]

    # 2. Approve the request
    resp_approve = await client.post(f"/api/v1/approvals/{approval_id}/approve")
    assert resp_approve.status_code == 200
    assert len(recorded_modes) == 1
    assert recorded_modes[-1] == "real"

    # 3. Request approval in default/simulator mode
    resp_create_sim = await client.post(
        "/api/v1/devices/entry-lock/command",
        headers={"X-Data-Mode": "simulator"},
        json={"action": "unlock"},
    )
    assert resp_create_sim.status_code == 200
    approval_id_sim = resp_create_sim.json()["id"]

    resp_approve_sim = await client.post(f"/api/v1/approvals/{approval_id_sim}/approve")
    assert resp_approve_sim.status_code == 200
    assert len(recorded_modes) == 2
    assert recorded_modes[-1] == "simulator"





