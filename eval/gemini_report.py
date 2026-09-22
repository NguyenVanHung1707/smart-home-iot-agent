"""Strict provider-aware schema for remote live evaluations."""

import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RemoteGeneration(StrictModel):
    temperature: Literal[0.0]
    max_tokens: Literal[192]
    response_mime_type: Literal["application/json"]


class RemoteUsage(StrictModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class RemoteModel(StrictModel):
    requested_model_id: str
    served_model_id: str | None


class RemoteScores(StrictModel):
    intent: float
    safety: float
    entity: float
    response: float
    overall: float


class RemoteCase(StrictModel):
    id: str
    status: Literal["ok", "parse_error", "timeout", "auth_error", "quota_error", "transport_error", "provider_error"]
    raw_output: str | None
    parse_status: Literal["success", "failure", "not_attempted"]
    parse_reason: Literal["empty", "invalid_fence", "invalid_json", "invalid_schema"] | None
    latency_ms: float
    scores: RemoteScores
    usage: RemoteUsage | None = None


class RemoteLiveReport(StrictModel):
    report_schema_version: Literal["remote-live-report-v1"]
    provider: Literal["google"]
    remote_model: RemoteModel
    run_id: str
    corpus_version: str
    scoring_version: Literal["scoring-v1"]
    generation: RemoteGeneration
    complete: bool
    execution_integrity: Literal["passed", "failed"]
    cases: tuple[RemoteCase, ...]


def atomic_write_report(path: Path, report: RemoteLiveReport) -> None:
    """Atomically publish validated report under caller-selected path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(report.model_dump(mode="json"), output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
