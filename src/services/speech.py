"""Adapters for local Zipformer STT and Piper TTS runtimes."""

from __future__ import annotations

import asyncio
import io
import sys
import threading
import time
import wave
from array import array
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from src.config import Settings, get_settings

ZIPFORMER_MODEL = "sherpa-onnx-zipformer-vi-int8-2025-04-20"


class SpeechError(RuntimeError):
    """Base error for speech runtime failures."""


class SpeechUnavailableError(SpeechError):
    """Raised when voice support or a speech runtime is unavailable."""


class SpeechTimeoutError(SpeechError):
    """Raised when a speech runtime exceeds its configured timeout."""


class InvalidAudioError(SpeechError):
    """Raised when uploaded audio does not match the supported WAV contract."""


class NoSpeechDetectedError(SpeechError):
    """Raised when VAD/STT returns no usable transcript."""


@dataclass(frozen=True)
class AudioInfo:
    duration_ms: int


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str
    duration_ms: int
    latency_ms: int
    model: str
    vad_applied: bool = False


@dataclass(frozen=True)
class Synthesis:
    audio: bytes
    latency_ms: int
    voice: str


def _validate_wav_handle(wav: wave.Wave_read, audio_size: int, settings: Settings) -> AudioInfo:
    if not audio_size:
        raise InvalidAudioError("empty_audio")
    if audio_size > settings.voice_max_audio_bytes:
        raise InvalidAudioError("audio_too_large")

    channels = wav.getnchannels()
    sample_width = wav.getsampwidth()
    sample_rate = wav.getframerate()
    frame_count = wav.getnframes()
    compression = wav.getcomptype()

    if channels != 1:
        raise InvalidAudioError("wav_must_be_mono")
    if sample_width != 2:
        raise InvalidAudioError("wav_must_be_pcm_16_bit")
    if sample_rate != 16_000:
        raise InvalidAudioError("wav_sample_rate_must_be_16000")
    if compression != "NONE":
        raise InvalidAudioError("wav_must_be_uncompressed_pcm")

    duration_ms = round(frame_count / sample_rate * 1000)
    if duration_ms <= 0:
        raise InvalidAudioError("empty_audio")
    if duration_ms > settings.voice_max_audio_seconds * 1000:
        raise InvalidAudioError("audio_too_long")
    return AudioInfo(duration_ms=duration_ms)


def validate_wav(audio: bytes, settings: Settings) -> AudioInfo:
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            return _validate_wav_handle(wav, len(audio), settings)
    except (EOFError, wave.Error) as exc:
        raise InvalidAudioError("invalid_wav") from exc


def decode_wav(audio: bytes, settings: Settings) -> tuple[AudioInfo, array]:
    """Validate and convert one accepted WAV payload into normalized float32 samples."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            info = _validate_wav_handle(wav, len(audio), settings)
            expected_bytes = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            pcm = wav.readframes(wav.getnframes())
    except (EOFError, wave.Error) as exc:
        raise InvalidAudioError("invalid_wav") from exc

    if len(pcm) != expected_bytes:
        raise InvalidAudioError("invalid_wav")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return info, array("f", (sample / 32768.0 for sample in samples))


def apply_vad(samples: array) -> array:
    """Trim quiet edges and reject silence before sending samples to Zipformer."""
    frame_size = 320  # 20 ms at 16 kHz
    threshold = 0.018
    speech_frames = [
        index
        for index in range(0, len(samples), frame_size)
        if max((abs(value) for value in samples[index : index + frame_size]), default=0.0) >= threshold
    ]
    if not speech_frames:
        raise NoSpeechDetectedError("no_speech_detected")
    first = max(0, speech_frames[0] - 1600)
    last = min(len(samples), speech_frames[-1] + frame_size + 1600)
    return array("f", samples[first:last])


class SpeechRuntime:
    """Serialize heavy speech work so STT and TTS do not peak together."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._inference_lock = asyncio.Lock()
        self._recognizer_lock = threading.Lock()
        self._recognizer: Any | None = None

    def _require_enabled(self) -> None:
        if not self.settings.voice_enabled:
            raise SpeechUnavailableError("voice_disabled")

    def _load_recognizer(self) -> Any:
        model_dir = Path(self.settings.zipformer_model_dir)
        files = {
            "encoder": model_dir / "encoder-epoch-12-avg-8.int8.onnx",
            "decoder": model_dir / "decoder-epoch-12-avg-8.onnx",
            "joiner": model_dir / "joiner-epoch-12-avg-8.int8.onnx",
            "tokens": model_dir / "tokens.txt",
        }
        if not all(path.is_file() for path in files.values()):
            raise SpeechUnavailableError("stt_unavailable")
        try:
            import sherpa_onnx

            return sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(files["encoder"]),
                decoder=str(files["decoder"]),
                joiner=str(files["joiner"]),
                tokens=str(files["tokens"]),
                num_threads=self.settings.zipformer_num_threads,
                provider="cpu",
                decoding_method="greedy_search",
            )
        except Exception as exc:
            raise SpeechUnavailableError("stt_unavailable") from exc

    def _get_recognizer(self) -> Any:
        with self._recognizer_lock:
            if self._recognizer is None:
                self._recognizer = self._load_recognizer()
            return self._recognizer

    def preload(self) -> bool:
        if self.settings.zipformer_endpoint:
            return True
        try:
            self._get_recognizer()
        except SpeechUnavailableError:
            return False
        return True

    def _transcribe_sync(self, samples: array) -> str:
        recognizer = self._get_recognizer()
        stream = recognizer.create_stream()
        stream.accept_waveform(16_000, samples)
        recognizer.decode_stream(stream)
        return str(stream.result.text).strip()

    async def transcribe(self, audio: bytes) -> Transcription:
        self._require_enabled()
        started = time.perf_counter()
        info = validate_wav(audio, self.settings)

        if self.settings.zipformer_endpoint:
            try:
                async with self._inference_lock:
                    async with httpx.AsyncClient(timeout=self.settings.tts_timeout_seconds) as client:
                        files = {"file": ("command.wav", audio, "audio/wav")}
                        response = await client.post(self.settings.zipformer_endpoint, files=files)
                        if getattr(response, "status_code", None) == 422:
                            err_data = response.json() if getattr(response, "content", None) else {}
                            err_msg = str(err_data.get("error", ""))
                            if "no speech detected" in err_msg.lower():
                                raise NoSpeechDetectedError("no_speech_detected")
                            raise InvalidAudioError(err_msg or "invalid_wav")
                        response.raise_for_status()
                        data = response.json()
            except (NoSpeechDetectedError, InvalidAudioError):
                raise
            except httpx.TimeoutException as exc:
                raise SpeechTimeoutError("stt_timeout") from exc
            except httpx.HTTPError as exc:
                raise SpeechUnavailableError("stt_unavailable") from exc

            text = str(data.get("text", "")).strip()
            if not text:
                raise NoSpeechDetectedError("no_speech_detected")
            return Transcription(
                text=text,
                language=str(data.get("language", "vi")),
                duration_ms=int(data.get("duration_ms", info.duration_ms)),
                latency_ms=int(data.get("latency_ms", round((time.perf_counter() - started) * 1000))),
                model=str(data.get("model", ZIPFORMER_MODEL)),
                vad_applied=bool(data.get("vad_applied", True)),
            )

        info, samples = decode_wav(audio, self.settings)
        voiced_samples = apply_vad(samples)
        try:
            async with self._inference_lock:
                text = await asyncio.to_thread(self._transcribe_sync, voiced_samples)
        except SpeechUnavailableError:
            raise
        except Exception as exc:
            raise SpeechUnavailableError("stt_unavailable") from exc
        if not text:
            raise NoSpeechDetectedError("no_speech_detected")
        return Transcription(
            text=text,
            language="vi",
            duration_ms=info.duration_ms,
            latency_ms=round((time.perf_counter() - started) * 1000),
            model=ZIPFORMER_MODEL,
            vad_applied=True,
        )

    async def synthesize(self, text: str) -> Synthesis:
        self._require_enabled()
        normalized = text.strip()
        if not normalized:
            raise SpeechError("empty_tts_text")
        if len(normalized) > self.settings.voice_max_tts_chars:
            raise SpeechError("tts_text_too_long")

        started = time.perf_counter()
        try:
            async with self._inference_lock:
                async with httpx.AsyncClient(timeout=self.settings.tts_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.settings.piper_endpoint.rstrip('/')}/synthesize",
                        json={"text": normalized, "voice": self.settings.piper_voice},
                    )
                    response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SpeechTimeoutError("piper_timeout") from exc
        except httpx.HTTPError as exc:
            raise SpeechUnavailableError("piper_unavailable") from exc
        if not response.content:
            raise SpeechUnavailableError("empty_piper_response")
        return Synthesis(
            audio=response.content,
            latency_ms=round((time.perf_counter() - started) * 1000),
            voice=self.settings.piper_voice,
        )

    async def status(self) -> dict[str, object]:
        if not self.settings.voice_enabled:
            return {
                "enabled": False,
                "ready": False,
                "stt": {"ready": False, "model": ZIPFORMER_MODEL, "vad": False},
                "tts": {"ready": False, "voice": self.settings.piper_voice},
                "limits": {"max_audio_seconds": self.settings.voice_max_audio_seconds},
            }

        async def reachable(url: str) -> bool:
            try:
                async with httpx.AsyncClient(timeout=min(self.settings.tts_timeout_seconds, 3.0)) as client:
                    response = await client.get(url)
                    return response.is_success
            except httpx.HTTPError:
                return False

        async def check_stt() -> bool:
            if self.settings.zipformer_endpoint:
                health_url = self.settings.zipformer_health_endpoint or (
                    self.settings.zipformer_endpoint.rsplit("/v1", 1)[0] + "/health"
                )
                return await reachable(health_url)
            return await asyncio.to_thread(self.preload)

        stt_ready, piper_ready = await asyncio.gather(
            check_stt(),
            reachable(f"{self.settings.piper_endpoint.rstrip('/')}/info"),
        )
        return {
            "enabled": True,
            "ready": stt_ready and piper_ready,
            "stt": {"ready": stt_ready, "model": ZIPFORMER_MODEL, "vad": stt_ready},
            "tts": {"ready": piper_ready, "voice": self.settings.piper_voice},
            "limits": {"max_audio_seconds": self.settings.voice_max_audio_seconds},
        }


@lru_cache
def get_speech_runtime() -> SpeechRuntime:
    return SpeechRuntime()
