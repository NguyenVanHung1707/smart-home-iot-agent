"""Focused tests for opt-in single-model live GGUF evaluation."""

import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import openai
import pytest

from eval.cases.golden import GOLDEN_CASES_V1
from eval.live_runner import (
    BENCHMARK_MAX_OUTPUT_TOKENS,
    EndpointMismatchError,
    IdentityBindingError,
    LiveConfig,
    OpenAIClient,
    TransportError,
    _parse_args,
    build_prompt,
    run_live,
    sanitize_base_url,
    select_model,
)
from eval.model_discovery import ModelIdentity, ModelSha256, RelativeModelPath


@dataclass
class FakeClient:
    served_ids: tuple[str, ...]
    replies: list[str | Exception]
    calls: list[tuple[str, float, int]]

    def list_model_ids(self) -> tuple[str, ...]:
        return self.served_ids

    async def complete(self, prompt: str, temperature: float, max_tokens: int) -> str:
        self.calls.append((prompt, temperature, max_tokens))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def identity(path: str = "models/selected.gguf") -> ModelIdentity:
    return ModelIdentity(
        relative_path=RelativeModelPath(path),
        sha256=ModelSha256("a" * 64),
        size_bytes=123,
    )


def valid_output() -> str:
    return json.dumps(
        {
            "act": "CONTROL",
            "safety": "ROUTINE",
            "entities": {"device": "living-room-light", "action": "on", "value": None},
            "response": "Có thể bật đèn.",
        },
        ensure_ascii=False,
    )


def config(tmp_path: Path) -> LiveConfig:
    return LiveConfig(
        models_dir=tmp_path / "models",
        base_url="http://user:secret@localhost:8080/v1?token=hidden",
        model_name="served-model",
        gguf=RelativeModelPath("models/selected.gguf"),
        server_fingerprint="a" * 64,
        run_id="run-1",
        output=tmp_path / "report.json",
        timeout_seconds=10.0,
        max_output_tokens=BENCHMARK_MAX_OUTPUT_TOKENS,
    )


def test_parse_args_defaults_to_benchmark_token_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_runner",
            "--models-dir",
            "models",
            "--base-url",
            "http://localhost:8080/v1",
            "--model-name",
            "served-model",
            "--gguf",
            "selected.gguf",
            "--server-fingerprint",
            "a" * 64,
            "--run-id",
            "run-1",
            "--output",
            "report.json",
        ],
    )

    # When
    parsed = _parse_args()

    # Then
    assert parsed.max_output_tokens == BENCHMARK_MAX_OUTPUT_TOKENS


def test_parse_args_accepts_explicit_positive_token_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_runner",
            "--models-dir",
            "models",
            "--base-url",
            "http://localhost:8080/v1",
            "--model-name",
            "served-model",
            "--gguf",
            "selected.gguf",
            "--server-fingerprint",
            "a" * 64,
            "--run-id",
            "run-1",
            "--output",
            "report.json",
            "--max-output-tokens",
            "2048",
        ],
    )

    # When
    parsed = _parse_args()

    # Then
    assert parsed.max_output_tokens == 2048


@pytest.mark.parametrize("value", ["0", "-1"])
def test_parse_args_rejects_non_positive_token_cap(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    # Given
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_runner",
            "--models-dir",
            "models",
            "--base-url",
            "http://localhost:8080/v1",
            "--model-name",
            "served-model",
            "--gguf",
            "selected.gguf",
            "--server-fingerprint",
            "a" * 64,
            "--run-id",
            "run-1",
            "--output",
            "report.json",
            "--max-output-tokens",
            value,
        ],
    )

    # When / Then
    with pytest.raises(SystemExit):
        _parse_args()


def test_openai_client_complete_accepts_benchmark_token_cap() -> None:
    # Given
    signature = inspect.signature(OpenAIClient.complete)

    # When
    parameters = tuple(signature.parameters)

    # Then
    assert parameters == ("self", "prompt", "temperature", "max_tokens")


def test_select_model_requires_discovered_relative_gguf() -> None:
    # Given
    models = (identity(),)

    # When / Then
    assert select_model(models, RelativeModelPath("models/selected.gguf")) == models[0]
    with pytest.raises(LookupError):
        select_model(models, RelativeModelPath("/absolute.gguf"))


def test_endpoint_metadata_removes_credentials_query_and_fragment() -> None:
    # Given / When
    sanitized = sanitize_base_url("https://user:pass@example.test:8443/v1/?api_key=x#secret")

    # Then
    assert sanitized == "https://example.test:8443/v1"


def test_prompt_contains_protocol_and_utterance_without_execution_hooks() -> None:
    # Given / When
    prompt = build_prompt(GOLDEN_CASES_V1[0])

    # Then
    assert GOLDEN_CASES_V1[0].utterance in prompt
    assert '"act"' in prompt


@pytest.mark.asyncio
async def test_endpoint_mismatch_fails_before_artifact(tmp_path: Path) -> None:
    # Given
    client = FakeClient(served_ids=("other",), replies=[], calls=[])
    live_config = config(tmp_path)

    # When / Then
    with pytest.raises(EndpointMismatchError):
        await run_live(live_config, identity(), GOLDEN_CASES_V1[:1], client)
    assert not live_config.output.exists()
    assert client.calls == []


@pytest.mark.asyncio
async def test_wrong_server_fingerprint_rejects_unverified_gguf(tmp_path: Path) -> None:
    # Given
    live_config = config(tmp_path)
    live_config = LiveConfig(
        models_dir=live_config.models_dir,
        base_url=live_config.base_url,
        model_name=live_config.model_name,
        gguf=live_config.gguf,
        server_fingerprint="b" * 64,
        run_id=live_config.run_id,
        output=live_config.output,
        timeout_seconds=live_config.timeout_seconds,
        max_output_tokens=live_config.max_output_tokens,
    )
    client = FakeClient(served_ids=("served-model",), replies=[], calls=[])

    # When / Then
    with pytest.raises(IdentityBindingError):
        await run_live(live_config, identity(), GOLDEN_CASES_V1[:1], client)
    assert not live_config.output.exists()


@pytest.mark.asyncio
async def test_openai_timeout_is_recorded_as_incomplete_transport_failure(tmp_path: Path) -> None:
    # Given
    request = httpx.Request("POST", "http://localhost:8080/v1/chat/completions")
    timeout = openai.APITimeoutError(request=request)
    client = FakeClient(served_ids=("served-model",), replies=[timeout], calls=[])
    live_config = config(tmp_path)

    # When
    complete = await run_live(live_config, identity(), GOLDEN_CASES_V1[:1], client)

    # Then
    report = json.loads(live_config.output.read_text(encoding="utf-8"))
    assert complete is False
    assert report["complete"] is False
    assert report["cases"][0]["status"] == "timeout"
    assert report["cases"][0]["scores"]["overall"] == 0.0


@pytest.mark.asyncio
async def test_run_continues_case_failures_and_writes_atomic_report(tmp_path: Path) -> None:
    # Given
    replies: list[str | Exception] = [
        valid_output(),
        "not-json",
        TimeoutError(),
        TransportError("connection lost"),
    ]
    client = FakeClient(served_ids=("served-model",), replies=replies, calls=[])
    live_config = config(tmp_path)

    # When
    await run_live(live_config, identity(), GOLDEN_CASES_V1[:4], client)

    # Then
    report = json.loads(live_config.output.read_text(encoding="utf-8"))
    assert len(client.calls) == 4
    assert all(temperature == 0.0 for _, temperature, _ in client.calls)
    assert all(max_tokens == BENCHMARK_MAX_OUTPUT_TOKENS for _, _, max_tokens in client.calls)
    assert [case["status"] for case in report["cases"]] == [
        "ok",
        "parse_error",
        "timeout",
        "transport_error",
    ]
    assert report["cases"][0]["raw_output"] == valid_output()
    assert report["cases"][0]["scores"]["overall"] >= 0
    assert report["model"]["name"] == "models/selected.gguf"
    assert report["model"]["sha256"] == "a" * 64
    assert report["server_identity"]["fingerprint"] == "a" * 64
    assert report["endpoint"] == "http://localhost:8080/v1"
    assert report["report_schema_version"] == "live-report-v1"
    assert report["scoring_version"] == "scoring-v1"
    assert report["generation"] == {"max_tokens": BENCHMARK_MAX_OUTPUT_TOKENS, "temperature": 0.0}
    assert report["complete"] is False
    assert report["execution_integrity"] == "failed"
    assert not list(tmp_path.glob(".report.json.*.tmp"))


@pytest.mark.asyncio
async def test_parse_error_is_complete_scored_model_response(tmp_path: Path) -> None:
    # Given
    client = FakeClient(served_ids=("served-model",), replies=["invalid model output"], calls=[])
    live_config = config(tmp_path)

    # When
    complete = await run_live(live_config, identity(), GOLDEN_CASES_V1[:1], client)

    # Then
    report = json.loads(live_config.output.read_text(encoding="utf-8"))
    assert complete is True
    assert report["complete"] is True
    assert report["execution_integrity"] == "passed"
    assert report["cases"][0]["status"] == "parse_error"
    assert report["cases"][0]["raw_output"] == "invalid model output"
    assert report["cases"][0]["scores"]["overall"] == 0.0
