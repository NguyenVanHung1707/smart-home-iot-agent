"""Focused tests for provider-aware remote leaderboard artifacts."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from eval.cases.golden import GOLDEN_CASES_V1
from eval.remote_leaderboard import RemoteLeaderboardError, aggregate_reports, main

CASE_IDS = tuple(case.id for case in GOLDEN_CASES_V1)


def _report(*, requested: str = "gemini-2.5-flash", served: str = "gemini-2.5-flash-001", safety: float = 1.0) -> dict:
    return {
        "report_schema_version": "remote-live-report-v1",
        "corpus_version": "vietnamese-golden-v1",
        "scoring_version": "scoring-v1",
        "provider": "google",
        "remote_model": {"requested_model_id": requested, "served_model_id": served},
        "generation": {"max_tokens": 192, "temperature": 0.0, "response_mime_type": "application/json"},
        "complete": True,
        "execution_integrity": "passed",
        "run_id": requested,
        "cases": [
            {
                "id": case_id,
                "status": "ok",
                "raw_output": "{}",
                "parse_status": "success",
                "parse_reason": None,
                "scores": {"safety": safety, "intent": 0.9, "entity": 0.8, "response": 0.7, "overall": 0.85},
                "latency_ms": 20 + index,
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            for index, case_id in enumerate(CASE_IDS)
        ],
    }


def _write(root: Path, name: str, payload: dict) -> None:
    root.mkdir(exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_aggregate_scores_parse_errors_and_writes_remote_artifacts(tmp_path: Path) -> None:
    # Given
    reports = tmp_path / "reports"
    fast = _report(requested="gemini-fast", served="gemini-fast-001")
    fast["cases"][0].update(
        status="parse_error",
        raw_output="invalid",
        parse_status="failure",
        parse_reason="invalid_json",
        scores={"safety": 0.0, "intent": 0.0, "entity": 0.0, "response": 0.0, "overall": 0.0},
    )
    _write(reports, "fast.json", fast)
    _write(reports, "safe.json", _report(requested="gemini-safe", served="gemini-safe-001"))

    # When
    result = aggregate_reports(reports, tmp_path / "output")

    # Then
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["leaderboard_schema_version"] == "remote-leaderboard-v1"
    assert [entry["requested_model_id"] for entry in payload["entries"]] == ["gemini-safe", "gemini-fast"]
    assert payload["entries"][1]["parse_error_count"] == 1
    assert payload["entries"][1]["parse_error_rate"] == pytest.approx(1 / len(CASE_IDS))
    assert payload["entries"][0]["usage"] == {
        "completion_tokens": 5 * len(CASE_IDS),
        "prompt_tokens": 10 * len(CASE_IDS),
        "total_tokens": 15 * len(CASE_IDS),
    }
    with result.csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0][:4] == ["rank", "provider", "requested_model_id", "served_model_id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "provider",
        "missing",
        "reordered",
        "incomplete",
        "integrity",
        "provider-failure",
        "fingerprint",
        "duplicate",
    ],
)
def test_aggregate_rejects_incompatible_remote_reports(tmp_path: Path, mutation: str) -> None:
    # Given
    reports = tmp_path / "reports"
    payload = _report()
    match mutation:
        case "schema":
            payload["report_schema_version"] = "live-report-v1"
        case "provider":
            payload["provider"] = "other"
        case "missing":
            payload["cases"].pop()
        case "reordered":
            payload["cases"][0], payload["cases"][1] = payload["cases"][1], payload["cases"][0]
        case "incomplete":
            payload["complete"] = False
        case "integrity":
            payload["execution_integrity"] = "failed"
        case "provider-failure":
            payload["cases"][0]["status"] = "provider_error"
        case "fingerprint":
            payload["server_identity"] = {"fingerprint": "a" * 64}
        case "duplicate":
            _write(reports, "duplicate.json", deepcopy(payload))
        case unreachable:
            raise AssertionError(unreachable)
    _write(reports, "report.json", payload)

    # When / Then
    with pytest.raises(RemoteLeaderboardError):
        aggregate_reports(reports, tmp_path / "output")


def test_cli_aggregates_reports_root(tmp_path: Path) -> None:
    # Given
    reports = tmp_path / "reports"
    output = tmp_path / "board"
    _write(reports, "report.json", _report())

    # When
    status = main(["--reports", str(reports), "--output", str(output)])

    # Then
    assert status == 0
    assert (output / "remote-leaderboard-v1.json").is_file()
    assert (output / "remote-leaderboard-v1.csv").is_file()
