#!/usr/bin/env python3
"""Benchmark a configured local STT runtime without storing transcripts."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import httpx


def edit_distance(expected: list[str], actual: list[str]) -> int:
    previous = list(range(len(actual) + 1))
    for expected_item in expected:
        current = [previous[0] + 1]
        for index, actual_item in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1] + (expected_item != actual_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str, *, words: bool) -> float:
    expected = reference.lower().split() if words else list(reference.lower().replace(" ", ""))
    actual = hypothesis.lower().split() if words else list(hypothesis.lower().replace(" ", ""))
    return edit_distance(expected, actual) / max(1, len(expected))


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def run_benchmark(api_url: str, manifest: Path, model_label: str) -> dict[str, object]:
    samples = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    cer_values: list[float] = []
    wer_values: list[float] = []
    latency_values: list[float] = []
    rtf_values: list[float] = []
    failures = 0

    with httpx.Client(timeout=120.0) as client:
        for sample in samples:
            audio_path = (manifest.parent / sample["audio"]).resolve()
            try:
                with audio_path.open("rb") as audio:
                    response = client.post(
                        f"{api_url.rstrip('/')}/voice/transcribe",
                        files={"file": (audio_path.name, audio, "audio/wav")},
                    )
                response.raise_for_status()
                result = response.json()
            except (OSError, httpx.HTTPError, KeyError, ValueError):
                failures += 1
                continue

            reference = str(sample["reference"])
            hypothesis = str(result["transcript"])
            latency_ms = float(result["stt_latency_ms"])
            duration_ms = max(1.0, float(result["audio_duration_ms"]))
            cer_values.append(error_rate(reference, hypothesis, words=False))
            wer_values.append(error_rate(reference, hypothesis, words=True))
            latency_values.append(latency_ms)
            rtf_values.append(latency_ms / duration_ms)

    return {
        "model": model_label,
        "samples": len(samples),
        "successful": len(cer_values),
        "failures": failures,
        "cer": statistics.fmean(cer_values) if cer_values else None,
        "wer": statistics.fmean(wer_values) if wer_values else None,
        "stt_latency_ms_median": statistics.median(latency_values) if latency_values else None,
        "stt_latency_ms_p95": percentile(latency_values, 0.95) if latency_values else None,
        "rtf_median": statistics.median(rtf_values) if rtf_values else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="JSONL with relative audio paths and reference text")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.api_url, args.manifest, args.model_label)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
