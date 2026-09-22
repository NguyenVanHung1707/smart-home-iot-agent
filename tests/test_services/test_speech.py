import asyncio
import io
import time
import wave
from array import array
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import src.services.speech as speech
from src.config import Settings
from src.services.speech import (
    InvalidAudioError,
    NoSpeechDetectedError,
    SpeechRuntime,
    SpeechUnavailableError,
    apply_vad,
    decode_wav,
    validate_wav,
)


def make_wav(
    *,
    seconds: float = 0.25,
    rate: int = 16_000,
    channels: int = 1,
    width: int = 2,
    amplitude: int = 1_000,
) -> bytes:
    output = io.BytesIO()
    max_amplitude = (1 << (width * 8 - 1)) - 1
    sample = min(amplitude, max_amplitude).to_bytes(width, byteorder="little", signed=True)
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(sample * round(seconds * rate) * channels)
    return output.getvalue()


def settings(**overrides) -> Settings:
    defaults = {"zipformer_endpoint": ""}
    return Settings(_env_file=None, **(defaults | overrides))


def test_validate_wav_accepts_required_contract():
    info = validate_wav(make_wav(), settings())

    assert info.duration_ms == 250


@pytest.mark.parametrize(
    ("audio", "message"),
    [
        (b"not-wave", "invalid_wav"),
        (make_wav(rate=8000), "wav_sample_rate_must_be_16000"),
        (make_wav(channels=2), "wav_must_be_mono"),
        (make_wav(width=1), "wav_must_be_pcm_16_bit"),
    ],
    ids=["not_wave", "sample_rate_8000", "stereo", "width_1"],
)
def test_validate_wav_rejects_unsupported_audio(audio, message):
    with pytest.raises(InvalidAudioError, match=message):
        validate_wav(audio, settings())


def test_validate_wav_enforces_duration_and_size():
    with pytest.raises(InvalidAudioError, match="audio_too_long"):
        validate_wav(make_wav(seconds=1.1), settings(voice_max_audio_seconds=1))
    with pytest.raises(InvalidAudioError, match="audio_too_large"):
        validate_wav(make_wav(), settings(voice_max_audio_bytes=100))


def test_decode_wav_normalizes_pcm_once_to_float32():
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\x00\x80\x00\x00\xff\x7f" + b"\x00\x00" * 1597)

    info, samples = decode_wav(audio.getvalue(), settings())

    assert info.duration_ms == 100
    assert samples.typecode == "f"
    assert list(samples[:3]) == pytest.approx([-1.0, 0.0, 32767 / 32768])


def test_zipformer_loads_once_and_returns_transcript():
    stream = Mock(result=SimpleNamespace(text=" bật đèn phòng khách "))
    recognizer = Mock()
    recognizer.create_stream.return_value = stream
    runtime = SpeechRuntime(settings(voice_enabled=True))
    runtime._load_recognizer = Mock(return_value=recognizer)

    first = asyncio.run(runtime.transcribe(make_wav()))
    second = asyncio.run(runtime.transcribe(make_wav()))

    assert first.text == "bật đèn phòng khách"
    assert second.model == "sherpa-onnx-zipformer-vi-int8-2025-04-20"
    assert first.vad_applied is True
    runtime._load_recognizer.assert_called_once()
    assert recognizer.decode_stream.call_count == 2


def test_zipformer_empty_result_is_no_speech():
    recognizer = Mock()
    recognizer.create_stream.return_value = Mock(result=SimpleNamespace(text=" "))
    runtime = SpeechRuntime(settings(voice_enabled=True))
    runtime._load_recognizer = Mock(return_value=recognizer)

    with pytest.raises(NoSpeechDetectedError, match="no_speech_detected"):
        asyncio.run(runtime.transcribe(make_wav()))


def test_vad_rejects_silence_before_zipformer_inference():
    runtime = SpeechRuntime(settings(voice_enabled=True))
    runtime._transcribe_sync = Mock(return_value="không được gọi")

    with pytest.raises(NoSpeechDetectedError, match="no_speech_detected"):
        asyncio.run(runtime.transcribe(make_wav(amplitude=0)))

    runtime._transcribe_sync.assert_not_called()


def test_vad_trims_silence_while_preserving_context():
    silence = array("f", [0.0] * 4_000)
    speech_samples = array("f", [0.1] * 1_600)

    voiced = apply_vad(silence + speech_samples + silence)

    assert 4_800 <= len(voiced) < len(silence + speech_samples + silence)
    assert max(voiced) == pytest.approx(0.1)
    assert voiced[0] == pytest.approx(0.0)
    assert voiced[-1] == pytest.approx(0.0)


def test_missing_zipformer_model_keeps_runtime_unready():
    runtime = SpeechRuntime(settings(voice_enabled=True))
    runtime._load_recognizer = Mock(side_effect=SpeechUnavailableError("stt_unavailable"))

    status = asyncio.run(runtime.status())

    assert status["stt"] == {
        "ready": False,
        "model": "sherpa-onnx-zipformer-vi-int8-2025-04-20",
        "vad": False,
    }


def test_shared_lock_serializes_zipformer_inference():
    active = 0
    peak = 0

    class Recognizer:
        def create_stream(self):
            return Mock(result=SimpleNamespace(text="bật đèn"))

        def decode_stream(self, _stream):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            time.sleep(0.01)
            active -= 1

    runtime = SpeechRuntime(settings(voice_enabled=True))
    runtime._load_recognizer = Mock(return_value=Recognizer())

    async def transcribe_twice():
        return await asyncio.gather(runtime.transcribe(make_wav()), runtime.transcribe(make_wav()))

    assert len(asyncio.run(transcribe_twice())) == 2
    assert peak == 1


def test_shared_lock_serializes_zipformer_and_piper(monkeypatch):
    events: list[str] = []
    runtime = SpeechRuntime(settings(voice_enabled=True))

    async def delayed_transcription(*_args):
        events.append("stt-start")
        await asyncio.sleep(0.01)
        events.append("stt-end")
        return "bật đèn"

    class PiperClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            events.append("tts")
            return SimpleNamespace(content=b"wav", raise_for_status=lambda: None)

    monkeypatch.setattr(speech.asyncio, "to_thread", delayed_transcription)
    monkeypatch.setattr(speech.httpx, "AsyncClient", PiperClient)

    async def run_both():
        return await asyncio.gather(runtime.transcribe(make_wav()), runtime.synthesize("Đã bật đèn."))

    assert len(asyncio.run(run_both())) == 2
    assert events == ["stt-start", "stt-end", "tts"]


def test_disabled_runtime_fails_without_network():
    runtime = SpeechRuntime(settings(voice_enabled=False))

    with pytest.raises(SpeechUnavailableError, match="voice_disabled"):
        asyncio.run(runtime.transcribe(make_wav()))
    with pytest.raises(SpeechUnavailableError, match="voice_disabled"):
        asyncio.run(runtime.synthesize("xin chào"))


def test_disabled_status_keeps_text_fallback_available():
    status = asyncio.run(SpeechRuntime(settings(voice_enabled=False, voice_max_audio_seconds=17)).status())

    assert status["enabled"] is False
    assert status["ready"] is False
    assert status["stt"] == {
        "ready": False,
        "model": "sherpa-onnx-zipformer-vi-int8-2025-04-20",
        "vad": False,
    }
    assert status["limits"]["max_audio_seconds"] == 17
