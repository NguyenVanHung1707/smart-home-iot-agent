"""Native async Gemini evaluator and remote report CLI."""

import argparse
import time
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Final, Protocol

import anyio
from google import genai
from google.genai import errors, types

from eval.cases.golden import GOLDEN_CASES_V1, GOLDEN_CORPUS_VERSION
from eval.cases.golden_schema import GoldenCase
from eval.gemini_config import GeminiConfig, load_gemini_api_key
from eval.gemini_report import (
    RemoteCase,
    RemoteGeneration,
    RemoteLiveReport,
    RemoteModel,
    RemoteScores,
    RemoteUsage,
    atomic_write_report,
)
from eval.live_protocol import ParseFailure, parse_model_output
from eval.live_runner import build_prompt
from eval.scoring import CaseScore, score_golden_case

MAX_OUTPUT_TOKENS: Final = 192
SCORING_VERSION: Final = "scoring-v1"
_ZERO_SCORE: Final = CaseScore(intent=0, safety=0, entity=0, response=0, overall=0)


class AsyncModels(Protocol):
    async def generate_content(
        self, *, model: str, contents: str, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse: ...


class AsyncClient(Protocol):
    models: AsyncModels


class NativeClient(Protocol):
    aio: AsyncClient


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    usage: RemoteUsage | None


class GeminiClient:
    """Narrow native google-genai async adapter."""

    def __init__(self, client: NativeClient) -> None:
        self._client = client

    async def complete(self, model: str, prompt: str) -> Completion:
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                response_mime_type="application/json",
            ),
        )
        usage = response.usage_metadata
        return Completion(
            text=response.text or "",
            usage=None
            if usage is None
            else RemoteUsage(
                prompt_tokens=usage.prompt_token_count,
                completion_tokens=usage.candidates_token_count,
                total_tokens=usage.total_token_count,
            ),
        )


def _model_case(case: GoldenCase, completion: Completion, latency_ms: float) -> RemoteCase:
    parsed = parse_model_output(completion.text)
    score = score_golden_case(case, parsed)
    reason = parsed.reason if isinstance(parsed, ParseFailure) else None
    return RemoteCase(
        id=case.id,
        status="parse_error" if reason else "ok",
        raw_output=completion.text,
        parse_status="failure" if reason else "success",
        parse_reason=reason,
        latency_ms=round(latency_ms, 3),
        scores=RemoteScores(**asdict(score)),
        usage=completion.usage,
    )


def _provider_failure(case: GoldenCase, status: str, latency_ms: float) -> RemoteCase:
    return RemoteCase(
        id=case.id,
        status=status,
        raw_output=None,
        parse_status="not_attempted",
        parse_reason=None,
        latency_ms=round(latency_ms, 3),
        scores=RemoteScores(**asdict(_ZERO_SCORE)),
    )


def _api_failure_status(error: errors.APIError) -> str:
    match error.code:
        case 401 | 403:
            return "auth_error"
        case 429:
            return "quota_error"
        case _:
            return "provider_error"


async def run_gemini(config: GeminiConfig, cases: tuple[GoldenCase, ...], client: GeminiClient) -> RemoteLiveReport:
    """Evaluate cases sequentially; model parse failures remain valid scored outcomes."""
    records: list[RemoteCase] = []
    for case in cases:
        started = time.perf_counter()
        try:
            with anyio.fail_after(config.timeout_seconds):
                completion = await client.complete(config.model, build_prompt(case))
            record = _model_case(case, completion, (time.perf_counter() - started) * 1000)
        except TimeoutError:
            record = _provider_failure(case, "timeout", (time.perf_counter() - started) * 1000)
        except errors.APIError as error:
            record = _provider_failure(case, _api_failure_status(error), (time.perf_counter() - started) * 1000)
        except (ConnectionError, OSError):
            record = _provider_failure(case, "transport_error", (time.perf_counter() - started) * 1000)
        records.append(record)
    complete = all(record.raw_output is not None for record in records) and len(records) == len(cases)
    return RemoteLiveReport(
        report_schema_version="remote-live-report-v1",
        provider="google",
        remote_model=RemoteModel(requested_model_id=config.model, served_model_id=None),
        run_id=config.run_id,
        corpus_version=GOLDEN_CORPUS_VERSION,
        scoring_version=SCORING_VERSION,
        generation=RemoteGeneration(
            temperature=0.0, max_tokens=MAX_OUTPUT_TOKENS, response_mime_type="application/json"
        ),
        complete=complete,
        execution_integrity="passed" if complete else "failed",
        cases=tuple(records),
    )


def _arguments() -> GeminiConfig:
    parser = argparse.ArgumentParser(description="Run native Gemini remote evaluation.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    values = vars(parser.parse_args())
    return GeminiConfig.model_validate(values)


async def _main_async(config: GeminiConfig) -> int:
    api_key = load_gemini_api_key(Path(__file__).resolve().parents[1])
    client = GeminiClient(genai.Client(api_key=api_key.get_secret_value()))
    report = await run_gemini(config, GOLDEN_CASES_V1, client)
    atomic_write_report(config.output, report)
    return int(report.execution_integrity == "failed")


def main() -> int:
    return anyio.run(partial(_main_async, _arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
