"""Opt-in evaluator for one already-served local GGUF model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx
import openai
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

from eval.cases.golden import GOLDEN_CASES_V1, GOLDEN_CORPUS_VERSION
from eval.cases.golden_schema import GoldenCase
from eval.live_protocol import LIVE_PROTOCOL_INSTRUCTION, ParseFailure, parse_model_output
from eval.model_discovery import ModelIdentity, RelativeModelPath, discover_models
from eval.scoring import CaseScore, score_golden_case
from src.services.model_adapter import AdapterTimeoutError, ModelAdapter, local_openai_profile

REPORT_SCHEMA_VERSION: Final = "live-report-v1"
SCORING_VERSION: Final = "scoring-v1"
BENCHMARK_MAX_OUTPUT_TOKENS: Final = 192


@dataclass(frozen=True, slots=True)
class EndpointMismatchError(Exception):
    expected: str
    served: tuple[str, ...]

    def __str__(self) -> str:
        return f"expected served model {self.expected!r}, found {self.served!r}"


@dataclass(frozen=True, slots=True)
class IdentityBindingError(Exception):
    expected_sha256: str
    provided_fingerprint: str

    def __str__(self) -> str:
        return (
            "server fingerprint does not bind selected GGUF: "
            f"expected {self.expected_sha256}, provided {self.provided_fingerprint}"
        )


@dataclass(frozen=True, slots=True)
class SelectedModelError(LookupError):
    gguf: RelativeModelPath

    def __str__(self) -> str:
        return f"selected GGUF was not discovered: {self.gguf}"


class TransportError(RuntimeError):
    """Expected per-case endpoint transport failure."""


@dataclass(frozen=True, slots=True)
class LiveConfig:
    models_dir: Path
    base_url: str
    model_name: str
    gguf: RelativeModelPath
    server_fingerprint: str
    run_id: str
    output: Path
    timeout_seconds: float
    max_output_tokens: int


class LiveClient(Protocol):
    def list_model_ids(self) -> tuple[str, ...]: ...

    async def complete(self, prompt: str, temperature: float, max_tokens: int) -> str: ...


class ModelsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    class Item(BaseModel):
        model_config = ConfigDict(extra="ignore", frozen=True)
        id: str

    data: tuple[Item, ...]


class OpenAIClient:
    """Small OpenAI-compatible boundary backed by existing model adapter."""

    def __init__(self, config: LiveConfig) -> None:
        self._config = config
        model = ChatOpenAI(
            base_url=config.base_url,
            api_key="local-eval",
            model=config.model_name,
            temperature=0,
            timeout=config.timeout_seconds,
            max_retries=0,
            max_tokens=config.max_output_tokens,
        )
        self._adapter = ModelAdapter(local_openai_profile(config.model_name), model)

    def list_model_ids(self) -> tuple[str, ...]:
        try:
            response = httpx.get(
                f"{self._config.base_url.rstrip('/')}/models",
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            parsed = ModelsResponse.model_validate(response.json())
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
            raise TransportError("model discovery endpoint failed") from error
        return tuple(item.id for item in parsed.data)

    async def complete(self, prompt: str, temperature: float, max_tokens: int) -> str:
        if temperature != 0.0:
            raise TransportError("live evaluation requires temperature zero")
        try:
            return await self._adapter.chat(prompt)
        except AdapterTimeoutError as error:
            raise TimeoutError from error
        except httpx.TimeoutException as error:
            raise TimeoutError from error
        except httpx.HTTPError as error:
            raise TransportError("completion endpoint failed") from error


def sanitize_base_url(raw: str) -> str:
    """Retain endpoint location while removing credentials and secret-bearing parts."""
    parsed = urlsplit(raw)
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, f"{hostname}{port}", path, "", ""))


def select_model(models: Sequence[ModelIdentity], gguf: RelativeModelPath) -> ModelIdentity:
    """Select one discovered model by safe POSIX-relative path."""
    path = PurePosixPath(gguf)
    if path.is_absolute() or ".." in path.parts:
        raise SelectedModelError(gguf=gguf)
    for model in models:
        if model.relative_path == gguf:
            return model
    raise SelectedModelError(gguf=gguf)


def build_prompt(case: GoldenCase) -> str:
    return f"{LIVE_PROTOCOL_INSTRUCTION}\n\nVietnamese utterance:\n{case.utterance}"


def _case_record(case: GoldenCase, raw: str, status: str, latency_ms: float) -> dict[str, object]:
    parsed = parse_model_output(raw)
    score = score_golden_case(case, parsed)
    parse_reason = parsed.reason if isinstance(parsed, ParseFailure) else None
    return {
        "id": case.id,
        "status": status if status != "ok" else ("parse_error" if parse_reason else "ok"),
        "raw_output": raw,
        "parse_status": "failure" if parse_reason else "success",
        "parse_reason": parse_reason,
        "latency_ms": round(latency_ms, 3),
        "scores": asdict(score),
    }


def _failure_record(case: GoldenCase, status: str, latency_ms: float) -> dict[str, object]:
    zero = CaseScore(intent=0.0, safety=0.0, entity=0.0, response=0.0, overall=0.0)
    return {
        "id": case.id,
        "status": status,
        "raw_output": None,
        "parse_status": "not_attempted",
        "parse_reason": None,
        "latency_ms": round(latency_ms, 3),
        "scores": asdict(zero),
    }


def atomic_write_json(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


async def run_live(
    config: LiveConfig,
    identity: ModelIdentity,
    cases: Sequence[GoldenCase],
    client: LiveClient,
) -> bool:
    served = client.list_model_ids()
    if served != (config.model_name,):
        raise EndpointMismatchError(expected=config.model_name, served=served)
    if config.server_fingerprint != identity.sha256:
        raise IdentityBindingError(
            expected_sha256=str(identity.sha256),
            provided_fingerprint=config.server_fingerprint,
        )

    records: list[dict[str, object]] = []
    for case in cases:
        started = time.perf_counter()
        try:
            raw = await client.complete(build_prompt(case), 0.0, config.max_output_tokens)
            records.append(_case_record(case, raw, "ok", (time.perf_counter() - started) * 1000))
        except (TimeoutError, openai.APITimeoutError, httpx.TimeoutException):
            records.append(_failure_record(case, "timeout", (time.perf_counter() - started) * 1000))
        except (TransportError, openai.APIConnectionError, openai.APIStatusError, httpx.HTTPError):
            records.append(_failure_record(case, "transport_error", (time.perf_counter() - started) * 1000))

    complete = len(records) == len(cases) and all(record["raw_output"] is not None for record in records)
    execution_integrity = "passed" if complete else "failed"
    report: dict[str, object] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "corpus_version": GOLDEN_CORPUS_VERSION,
        "scoring_version": SCORING_VERSION,
        "generation": {"max_tokens": config.max_output_tokens, "temperature": 0.0},
        "complete": complete,
        "execution_integrity": execution_integrity,
        "run_id": config.run_id,
        "endpoint": sanitize_base_url(config.base_url),
        "served_model_id": config.model_name,
        "server_identity": {"fingerprint": config.server_fingerprint},
        "model": {
            "name": identity.relative_path,
            "sha256": identity.sha256,
            "size_bytes": identity.size_bytes,
        },
        "cases": records,
    }
    atomic_write_json(config.output, report)
    return complete


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _parse_args() -> LiveConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--gguf", required=True, type=RelativeModelPath)
    parser.add_argument("--server-fingerprint", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-output-tokens", type=_positive_int, default=BENCHMARK_MAX_OUTPUT_TOKENS)
    args = parser.parse_args()
    return LiveConfig(
        models_dir=args.models_dir,
        base_url=args.base_url,
        model_name=args.model_name,
        gguf=args.gguf,
        server_fingerprint=args.server_fingerprint,
        run_id=args.run_id,
        output=args.output,
        timeout_seconds=args.timeout,
        max_output_tokens=args.max_output_tokens,
    )


async def _main() -> int:
    config = _parse_args()
    discovered = discover_models(config.models_dir)
    identity = select_model(discovered.models, config.gguf)
    complete = await run_live(config, identity, GOLDEN_CASES_V1, OpenAIClient(config))
    return 0 if complete else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_main()))
