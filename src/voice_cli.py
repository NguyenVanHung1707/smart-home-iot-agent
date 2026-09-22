"""One-shot Raspberry Pi microphone client for the local voice API."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import httpx


def run_voice_command(api_url: str, duration: int) -> int:
    base_url = api_url.rstrip("/")
    with tempfile.TemporaryDirectory(prefix="homing-voice-") as temp_dir:
        capture_path = Path(temp_dir) / "capture.wav"
        reply_path = Path(temp_dir) / "reply.wav"
        print(f"Dang thu am trong toi da {duration} giay...")
        subprocess.run(
            [
                "arecord",
                "-q",
                "-f",
                "S16_LE",
                "-r",
                "16000",
                "-c",
                "1",
                "-d",
                str(duration),
                str(capture_path),
            ],
            check=True,
        )

        with httpx.Client(timeout=60.0) as client:
            with capture_path.open("rb") as audio:
                transcription_response = client.post(
                    f"{base_url}/voice/transcribe",
                    files={"file": ("capture.wav", audio, "audio/wav")},
                )
            transcription_response.raise_for_status()
            transcript = transcription_response.json()["transcript"]
            print(f"Ban: {transcript}")

            process_response = client.post(f"{base_url}/voice/process", json={"transcript": transcript})
            process_response.raise_for_status()
            reply = process_response.json()["response"]
            print(f"HomeMind: {reply}")

            synthesis_response = client.post(f"{base_url}/voice/synthesize", json={"text": reply})
            synthesis_response.raise_for_status()
            reply_path.write_bytes(synthesis_response.content)

        subprocess.run(["aplay", "-q", str(reply_path)], check=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Thu mot lenh giong noi va phat phan hoi tren Raspberry Pi")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--duration", type=int, default=10, choices=range(1, 21), metavar="1-20")
    args = parser.parse_args()
    try:
        return run_voice_command(args.api_url, args.duration)
    except (OSError, subprocess.CalledProcessError, httpx.HTTPError, KeyError) as exc:
        print(f"Voice command failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
