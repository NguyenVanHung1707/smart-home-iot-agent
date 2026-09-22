#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run benchmarks/task_16_characterize.py --manifest benchmarks/task-16-rollout-manifest.json --text-command 'curl -fsS http://localhost:8000/health' --voice-command 'curl -fsS http://localhost:8000/health'
# 3. Or make executable and run:
#      chmod +x benchmarks/task_16_characterize.py && ./benchmarks/task_16_characterize.py --help
# ──────────────────

from __future__ import annotations

import json
import os
import platform
import resource
import shlex
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Measurement:
    channel: Literal["text", "voice"]
    cache_state: Literal["unknown"]
    latency_ms: float
    rss_kib: int
    cpu_percent: float
    thermal: str | None
    returncode: int


def thermal_reading() -> str | None:
    """Read first Linux thermal sensor when platform exposes one."""
    sensors = sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    if not sensors:
        return None
    return sensors[0].read_text(encoding="utf-8").strip()


def characterize(channel: Literal["text", "voice"], command: str) -> Measurement:
    """Measure one real workload invocation without assigning a verdict."""
    started = time.perf_counter()
    cpu_started = time.process_time()
    completed = subprocess.run(shlex.split(command), check=False, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_started
    return Measurement(
        channel=channel,
        cache_state="unknown",
        latency_ms=elapsed * 1_000,
        rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        cpu_percent=(cpu_elapsed / elapsed * 100) if elapsed else 0.0,
        thermal=thermal_reading(),
        returncode=completed.returncode,
    )


def command_value(arguments: Sequence[str], name: str) -> str:
    try:
        return arguments[arguments.index(name) + 1]
    except (ValueError, IndexError) as error:
        raise SystemExit(f"missing required option {name}") from error


def main(arguments: Sequence[str]) -> None:
    manifest_path = Path(command_value(arguments, "--manifest"))
    text_command = command_value(arguments, "--text-command")
    voice_command = command_value(arguments, "--voice-command")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    measurements = [
        asdict(characterize("text", text_command)),
        asdict(characterize("voice", voice_command)),
    ]
    output = {
        "manifest": manifest,
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "measurements": measurements,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
