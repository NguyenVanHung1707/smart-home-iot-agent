"""Focused tests for six-model leaderboard and operator workflow."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from eval.batch_runner import main
from eval.cases.golden import GOLDEN_CASES_V1
from eval.leaderboard import LeaderboardError, aggregate_reports
from eval.live_runner import LiveConfig, run_live
from eval.model_discovery import ModelIdentity, RelativeModelPath, discover_models

CASE_IDS = tuple(case.id for case in GOLDEN_CASES_V1)


@dataclass
class SuccessfulClient:
    model_name: str

    def list_model_ids(self) -> tuple[str, ...]:
        return (self.model_name,)

    async def complete(self, prompt: str, temperature: float, max_tokens: int) -> str:
        return json.dumps(
            {
                "act": "CONTROL",
                "safety": "ROUTINE",
                "entities": {"device": "living-room-light", "action": "on", "value": None},
                "response": "Có thể bật đèn.",
            },
            ensure_ascii=False,
        )


def _models(root: Path) -> None:
    root.mkdir()
    for index in range(6):
        (root / f"mô hình-{index}.gguf").write_bytes(f"model-{index}".encode())


def _report(
    path: Path,
    *,
    sha256: str,
    name: str,
    safety: float = 1.0,
    corpus: str = "corpus-v1",
    status: str = "ok",
    max_tokens: int = 192,
    temperature: float = 0.0,
) -> None:
    payload = {
        "report_schema_version": "live-report-v1",
        "corpus_version": corpus,
        "scoring_version": "scoring-v1",
        "generation": {"max_tokens": max_tokens, "temperature": temperature},
        "complete": status in {"ok", "parse_error"},
        "execution_integrity": "passed" if status in {"ok", "parse_error"} else "failed",
        "run_id": path.stem,
        "endpoint": "http://localhost:8080/v1",
        "served_model_id": name,
        "server_identity": {"fingerprint": sha256},
        "model": {"name": name, "sha256": sha256, "size_bytes": 7},
        "cases": [
            {
                "id": case_id,
                "status": status,
                "raw_output": None
                if status in {"timeout", "transport_error"}
                else "invalid"
                if status == "parse_error"
                else "{}",
                "parse_status": "not_attempted"
                if status in {"timeout", "transport_error"}
                else "failure"
                if status == "parse_error"
                else "success",
                "parse_reason": "invalid_json" if status == "parse_error" else None,
                "scores": {"safety": safety, "intent": 0.9, "entity": 0.8, "response": 0.7, "overall": 0.85},
                "latency_ms": 20 + index,
            }
            for index, case_id in enumerate(CASE_IDS)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _complete_reports(tmp_path: Path) -> tuple[Path, Path]:
    models_root = tmp_path / "models"
    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    _models(models_root)
    discovered = discover_models(models_root)
    for index, model in enumerate(discovered.models):
        _report(reports_root / f"report-{index}.json", sha256=model.sha256, name=Path(model.relative_path).stem)
    return models_root, reports_root


@pytest.mark.asyncio
async def test_live_output_aggregates_end_to_end(tmp_path: Path) -> None:
    # Given
    models_root = tmp_path / "models"
    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    _models(models_root)
    discovered = discover_models(models_root)
    for index, model in enumerate(discovered.models):
        config = LiveConfig(
            models_dir=models_root,
            base_url="http://localhost:8080/v1",
            model_name=f"served-{index}",
            gguf=RelativeModelPath(model.relative_path),
            server_fingerprint=str(model.sha256),
            run_id=f"run-{index}",
            output=reports_root / f"run-{index}.json",
            timeout_seconds=10.0,
            max_output_tokens=192,
        )
        await run_live(
            config,
            ModelIdentity(model.relative_path, model.sha256, model.size_bytes),
            GOLDEN_CASES_V1,
            SuccessfulClient(config.model_name),
        )

    # When
    result = aggregate_reports(discovered, reports_root, tmp_path / "output")

    # Then
    assert result.json_path.is_file()


def test_aggregate_writes_versioned_ranked_utf8_json_and_stable_csv(tmp_path: Path) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    discovered = discover_models(models_root)
    first_hash = discovered.models[0].sha256
    first_report = reports_root / "report-0.json"
    _report(first_report, sha256=first_hash, name="Zeta", safety=0.5)

    # When
    result = aggregate_reports(discovered, reports_root, tmp_path / "output")

    # Then
    data = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert data["leaderboard_schema_version"] == "leaderboard-v2"
    assert [entry["rank"] for entry in data["entries"]] == list(range(1, 7))
    assert data["entries"][-1]["model_name"] == "Zeta"
    assert "mô hình" in result.csv_path.read_text(encoding="utf-8")
    with result.csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == [
        "rank",
        "model_name",
        "model_sha256",
        "safety",
        "intent",
        "entity",
        "response",
        "parse_error_count",
        "parse_error_rate",
        "median_latency_ms",
    ]
    assert len(rows) == 7


@pytest.mark.parametrize("mutation", ["mismatch", "missing", "duplicate", "incomplete", "case-gap"])
def test_aggregate_rejects_incompatible_or_incomplete_report_sets(tmp_path: Path, mutation: str) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    discovered = discover_models(models_root)
    target = reports_root / "report-0.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    if mutation == "mismatch":
        payload["corpus_version"] = "corpus-v2"
    elif mutation == "missing":
        target.unlink()
    elif mutation == "duplicate":
        (reports_root / "duplicate.json").write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "incomplete":
        payload["complete"] = False
    else:
        payload["cases"].pop()
    if mutation not in {"missing", "duplicate"}:
        target.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(LeaderboardError):
        aggregate_reports(discovered, reports_root, tmp_path / "output")


@pytest.mark.parametrize(
    ("generation_field", "value"),
    [("max_tokens", 2048), ("temperature", 0.5)],
)
def test_aggregate_rejects_mixed_generation_profiles(
    tmp_path: Path,
    generation_field: str,
    value: int | float,
) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    target = reports_root / "report-0.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["generation"][generation_field] = value
    target.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(LeaderboardError, match="generation profile"):
        aggregate_reports(discover_models(models_root), reports_root, tmp_path / "output")


def test_homogeneous_2048_reports_write_deterministic_v2_generation_metadata(tmp_path: Path) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    discovered = discover_models(models_root)
    for index, model in enumerate(discovered.models):
        _report(
            reports_root / f"report-{index}.json",
            sha256=model.sha256,
            name=Path(model.relative_path).stem,
            max_tokens=2048,
        )
    output_root = tmp_path / "output"

    # When
    first = aggregate_reports(discovered, reports_root, output_root)
    first_bytes = first.json_path.read_bytes()
    second = aggregate_reports(discovered, reports_root, output_root)

    # Then
    payload = json.loads(first_bytes)
    assert first.json_path.name == "leaderboard-v2.json"
    assert first.csv_path.name == "leaderboard-v2.csv"
    assert payload["leaderboard_schema_version"] == "leaderboard-v2"
    assert payload["generation"] == {"max_tokens": 2048, "temperature": 0.0}
    assert second.json_path.read_bytes() == first_bytes
    assert not (output_root / "leaderboard-v1.json").exists()
    assert len(payload["entries"]) == 6


def test_six_parse_error_reports_aggregate_with_penalty_metrics(tmp_path: Path) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    discovered = discover_models(models_root)
    for index, model in enumerate(discovered.models):
        _report(
            reports_root / f"report-{index}.json",
            sha256=model.sha256,
            name=Path(model.relative_path).stem,
            safety=0.0,
            status="parse_error",
        )

    # When
    result = aggregate_reports(discovered, reports_root, tmp_path / "output")

    # Then
    data = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 6
    assert all(entry["parse_error_count"] == len(CASE_IDS) for entry in data["entries"])
    assert all(entry["parse_error_rate"] == 1.0 for entry in data["entries"])
    assert all(entry["safety"] == 0.0 for entry in data["entries"])


@pytest.mark.parametrize("status", ["timeout", "transport_error"])
def test_aggregate_rejects_execution_integrity_failure(tmp_path: Path, status: str) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    discovered = discover_models(models_root)
    model = discovered.models[0]
    _report(
        reports_root / "report-0.json",
        sha256=model.sha256,
        name=Path(model.relative_path).stem,
        status=status,
    )

    # When / Then
    with pytest.raises(LeaderboardError):
        aggregate_reports(discovered, reports_root, tmp_path / "output")


def test_batch_next_reports_actionable_recovery_for_malformed_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    models_root = tmp_path / "models"
    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    _models(models_root)
    (reports_root / "unrelated.json").write_text("not-json", encoding="utf-8")

    # When
    status = main(["next", "--models", str(models_root), "--reports", str(reports_root)])

    # Then
    output = capsys.readouterr().out
    assert status == 1
    assert "unrelated.json" in output
    assert "remove or repair" in output


def test_aggregate_rejects_missing_identity_binding(tmp_path: Path) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    target = reports_root / "report-0.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    del payload["server_identity"]
    target.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(LeaderboardError):
        aggregate_reports(discover_models(models_root), reports_root, tmp_path / "output")


def test_batch_cli_discovers_selects_next_and_aggregates_without_process_calls(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    models_root, reports_root = _complete_reports(tmp_path)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("process call forbidden"))
    (reports_root / "report-5.json").unlink()

    # When
    discover_status = main(["discover", "--models", str(models_root)])
    next_status = main(["next", "--models", str(models_root), "--reports", str(reports_root)])
    _report(reports_root / "report-5.json", sha256=discover_models(models_root).models[5].sha256, name="last")
    aggregate_status = main(
        ["aggregate", "--models", str(models_root), "--reports", str(reports_root), "--output", str(tmp_path / "board")]
    )

    # Then
    output = capsys.readouterr().out
    assert (discover_status, next_status, aggregate_status) == (0, 0, 0)
    assert "docker" in output
    assert "llama" in output
    assert (tmp_path / "board" / "leaderboard-v2.json").is_file()
