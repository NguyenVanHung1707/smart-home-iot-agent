"""Focused tests for Gemini configuration and remote report contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval.gemini_config import GeminiConfig, load_gemini_api_key
from eval.gemini_report import RemoteLiveReport


def test_dotenv_does_not_override_exported_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    secret = "exported-secret"
    (tmp_path / ".env").write_text("GEMINI_API_KEY=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", secret)

    # When
    loaded = load_gemini_api_key(tmp_path)

    # Then
    assert loaded.get_secret_value() == secret


def test_config_serialization_never_contains_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    secret = "never-serialize-this"
    monkeypatch.setenv("GEMINI_API_KEY", secret)

    # When
    config = GeminiConfig.from_environment(
        repo_root=tmp_path,
        model="gemini-2.5-flash",
        run_id="run-1",
        timeout_seconds=4.0,
        output=tmp_path / "report.json",
    )

    # Then
    assert secret not in config.model_dump_json()


@pytest.mark.parametrize("forbidden", ["sha256", "fingerprint"])
def test_remote_report_rejects_local_identity_fields(forbidden: str) -> None:
    # Given
    payload = {
        "report_schema_version": "remote-live-report-v1",
        "provider": "google",
        "remote_model": {"requested_model_id": "gemini-2.5-flash", "served_model_id": None},
        "run_id": "run-1",
        "corpus_version": "vietnamese-golden-v1",
        "scoring_version": "scoring-v1",
        "generation": {"temperature": 0.0, "max_tokens": 192, "response_mime_type": "application/json"},
        "complete": False,
        "execution_integrity": "failed",
        "cases": [],
        forbidden: "local-only",
    }

    # When / Then
    with pytest.raises(ValidationError):
        RemoteLiveReport.model_validate(payload)


def test_report_json_has_no_secret_fields() -> None:
    # Given
    schema = RemoteLiveReport.model_json_schema()

    # When
    serialized = json.dumps(schema)

    # Then
    assert "api_key" not in serialized.lower()
