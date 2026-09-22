"""Focused fake-client tests for native Gemini evaluation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest
from google.genai import errors, types

from eval.cases.golden import GOLDEN_CASES_V1
from eval.gemini_config import GeminiConfig
from eval.gemini_report import atomic_write_report
from eval.gemini_runner import GeminiClient, run_gemini
from eval.remote_leaderboard import aggregate_reports

VALID_OUTPUT: Final = '{"act":"CONTROL","safety":"ROUTINE","entities":{"device":"living-room-light","action":"on","value":null},"response":"Tôi đề xuất bật đèn; chưa thực thi."}'


@dataclass(slots=True)
class FakeModels:
    response: types.GenerateContentResponse | None = None
    failure: BaseException | None = None
    call: tuple[str, str, types.GenerateContentConfig] | None = None

    async def generate_content(
        self, *, model: str, contents: str, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        self.call = (model, contents, config)
        if self.failure is not None:
            raise self.failure
        assert self.response is not None
        return self.response


@dataclass(frozen=True, slots=True)
class FakeAio:
    models: FakeModels


@dataclass(frozen=True, slots=True)
class FakeNativeClient:
    aio: FakeAio


def _config(tmp_path: Path) -> GeminiConfig:
    return GeminiConfig(
        model="gemini-2.5-flash",
        run_id="run-1",
        timeout_seconds=1.0,
        output=tmp_path / "remote.json",
    )


@pytest.mark.asyncio
async def test_native_client_uses_required_generation_config(tmp_path: Path) -> None:
    # Given
    models = FakeModels(
        response=types.GenerateContentResponse(candidates=[{"content": {"parts": [{"text": VALID_OUTPUT}]}}])
    )
    client = GeminiClient(FakeNativeClient(aio=FakeAio(models=models)))

    # When
    report = await run_gemini(_config(tmp_path), GOLDEN_CASES_V1[:1], client)

    # Then
    assert report.execution_integrity == "passed"
    assert models.call is not None
    model, _, generation = models.call
    assert model == "gemini-2.5-flash"
    assert generation.temperature == 0
    assert generation.max_output_tokens == 192
    assert generation.response_mime_type == "application/json"


@pytest.mark.asyncio
async def test_run_report_is_accepted_by_remote_leaderboard(tmp_path: Path) -> None:
    # Given
    models = FakeModels(
        response=types.GenerateContentResponse(
            candidates=[{"content": {"parts": [{"text": VALID_OUTPUT}]}}],
            usage_metadata={
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        )
    )
    reports = tmp_path / "reports"
    config = _config(reports)

    # When
    report = await run_gemini(
        config,
        GOLDEN_CASES_V1,
        GeminiClient(FakeNativeClient(aio=FakeAio(models=models))),
    )
    atomic_write_report(config.output, report)
    result = aggregate_reports(reports, tmp_path / "leaderboard")

    # Then
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    entry = payload["entries"][0]
    assert entry["provider"] == "google"
    assert entry["requested_model_id"] == "gemini-2.5-flash"
    assert entry["served_model_id"] is None
    assert entry["usage"] == {
        "prompt_tokens": 10 * len(GOLDEN_CASES_V1),
        "completion_tokens": 5 * len(GOLDEN_CASES_V1),
        "total_tokens": 15 * len(GOLDEN_CASES_V1),
    }


@pytest.mark.asyncio
async def test_parse_error_is_complete_scored_model_outcome(tmp_path: Path) -> None:
    # Given
    models = FakeModels(
        response=types.GenerateContentResponse(candidates=[{"content": {"parts": [{"text": "not-json"}]}}])
    )

    # When
    report = await run_gemini(
        _config(tmp_path), GOLDEN_CASES_V1[:1], GeminiClient(FakeNativeClient(aio=FakeAio(models=models)))
    )

    # Then
    assert report.complete is True
    assert report.execution_integrity == "passed"
    assert report.cases[0].status == "parse_error"
    assert report.cases[0].scores.overall == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (TimeoutError(), "timeout"),
        (errors.ClientError(401, {"error": {"message": "hidden-key"}}), "auth_error"),
        (errors.ClientError(429, {"error": {"message": "quota"}}), "quota_error"),
        (errors.ServerError(503, {"error": {"message": "provider"}}), "provider_error"),
        (ConnectionError(), "transport_error"),
    ],
)
async def test_provider_failures_are_explicit_and_fail_integrity(
    tmp_path: Path, failure: BaseException, status: str
) -> None:
    # Given
    models = FakeModels(failure=failure)

    # When
    report = await run_gemini(
        _config(tmp_path), GOLDEN_CASES_V1[:1], GeminiClient(FakeNativeClient(aio=FakeAio(models=models)))
    )

    # Then
    assert report.complete is False
    assert report.execution_integrity == "failed"
    assert report.cases[0].status == status
    assert "hidden-key" not in report.model_dump_json()
