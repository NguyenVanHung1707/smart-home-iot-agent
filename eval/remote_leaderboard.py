"""Aggregate strict provider-aware remote evaluation reports."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eval.cases.golden import GOLDEN_CASES_V1, GOLDEN_CORPUS_VERSION

REPORT_SCHEMA_VERSION: Final = "remote-live-report-v1"
LEADERBOARD_SCHEMA_VERSION: Final = "remote-leaderboard-v1"
SCORING_VERSION: Final = "scoring-v1"
CSV_HEADER: Final = (
    "rank",
    "provider",
    "requested_model_id",
    "served_model_id",
    "safety",
    "intent",
    "entity",
    "response",
    "overall",
    "parse_error_count",
    "parse_error_rate",
    "median_latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
)


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    safety: float = Field(ge=0, le=1)
    intent: float = Field(ge=0, le=1)
    entity: float = Field(ge=0, le=1)
    response: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class RemoteModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requested_model_id: str = Field(min_length=1)
    served_model_id: str | None


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_tokens: int = Field(gt=0)
    temperature: float = Field(ge=0)
    response_mime_type: Literal["application/json"]


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    status: Literal["ok", "parse_error", "provider_error", "timeout", "transport_error"]
    raw_output: str | None
    parse_status: Literal["success", "failure", "not_attempted"]
    parse_reason: str | None
    scores: Scores
    latency_ms: float = Field(ge=0)
    usage: Usage | None = None


class RemoteReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    report_schema_version: Literal["remote-live-report-v1"]
    corpus_version: str = Field(min_length=1)
    scoring_version: str = Field(min_length=1)
    provider: Literal["google"]
    remote_model: RemoteModel
    generation: Generation
    complete: bool
    execution_integrity: Literal["passed", "failed"]
    run_id: str = Field(min_length=1)
    cases: tuple[CaseResult, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class RemoteLeaderboardError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class Entry:
    provider: str
    requested_model_id: str
    served_model_id: str | None
    safety: float
    intent: float
    entity: float
    response: float
    overall: float
    parse_error_count: int
    parse_error_rate: float
    median_latency_ms: float
    usage: dict[str, int] | None


@dataclass(frozen=True, slots=True)
class AggregateResult:
    json_path: Path
    csv_path: Path


def load_reports(reports_root: Path) -> tuple[RemoteReport, ...]:
    """Read only strict remote-live-report-v1 plain JSON reports."""
    reports: list[RemoteReport] = []
    for path in sorted(reports_root.glob("*.json")):
        try:
            reports.append(RemoteReport.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError) as error:
            raise RemoteLeaderboardError(reason=f"invalid remote report {path}: {error}") from error
    return tuple(reports)


def _validate(reports: tuple[RemoteReport, ...]) -> tuple[RemoteReport, ...]:
    if not reports:
        raise RemoteLeaderboardError(reason="reports root contains no remote reports")
    identities = [(report.provider, report.remote_model.requested_model_id) for report in reports]
    if len(identities) != len(set(identities)):
        raise RemoteLeaderboardError(reason="duplicate provider and requested model reports are forbidden")
    expected_ids = tuple(case.id for case in GOLDEN_CASES_V1)
    if any(tuple(case.id for case in report.cases) != expected_ids for report in reports):
        raise RemoteLeaderboardError(reason="reports must match exact GOLDEN_CASES_V1 IDs and order")
    if any(not report.complete or report.execution_integrity != "passed" for report in reports):
        raise RemoteLeaderboardError(reason="reports must be complete with passed execution integrity")
    if any(case.status not in {"ok", "parse_error"} for report in reports for case in report.cases):
        raise RemoteLeaderboardError(reason="reports must not contain provider or transport failures")
    versions = {(report.report_schema_version, report.corpus_version, report.scoring_version) for report in reports}
    expected_versions = {(REPORT_SCHEMA_VERSION, GOLDEN_CORPUS_VERSION, SCORING_VERSION)}
    if versions != expected_versions:
        raise RemoteLeaderboardError(reason="remote report schema, corpus, or scoring version mismatch")
    return reports


def _entry(report: RemoteReport) -> Entry:
    usages = tuple(case.usage for case in report.cases)
    usage = None
    if all(
        item is not None
        and item.prompt_tokens is not None
        and item.completion_tokens is not None
        and item.total_tokens is not None
        for item in usages
    ):
        usage = {
            "prompt_tokens": sum(item.prompt_tokens for item in usages if item and item.prompt_tokens is not None),
            "completion_tokens": sum(
                item.completion_tokens for item in usages if item and item.completion_tokens is not None
            ),
            "total_tokens": sum(item.total_tokens for item in usages if item and item.total_tokens is not None),
        }
    return Entry(
        provider=report.provider,
        requested_model_id=report.remote_model.requested_model_id,
        served_model_id=report.remote_model.served_model_id,
        safety=fmean(case.scores.safety for case in report.cases),
        intent=fmean(case.scores.intent for case in report.cases),
        entity=fmean(case.scores.entity for case in report.cases),
        response=fmean(case.scores.response for case in report.cases),
        overall=fmean(case.scores.overall for case in report.cases),
        parse_error_count=sum(case.status == "parse_error" for case in report.cases),
        parse_error_rate=fmean(case.status == "parse_error" for case in report.cases),
        median_latency_ms=median(case.latency_ms for case in report.cases),
        usage=usage,
    )


def aggregate_reports(reports_root: Path, output_root: Path) -> AggregateResult:
    """Validate remote reports and write deterministic safety-first artifacts."""
    reports = _validate(load_reports(reports_root))
    entries = sorted(
        (_entry(report) for report in reports),
        key=lambda item: (
            -item.safety,
            -item.intent,
            -item.entity,
            -item.response,
            item.parse_error_rate,
            item.median_latency_ms,
            item.provider,
            item.requested_model_id,
            item.served_model_id or "",
        ),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / f"{LEADERBOARD_SCHEMA_VERSION}.json"
    csv_path = output_root / f"{LEADERBOARD_SCHEMA_VERSION}.csv"
    payload = {
        "leaderboard_schema_version": LEADERBOARD_SCHEMA_VERSION,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "corpus_version": GOLDEN_CORPUS_VERSION,
        "scoring_version": SCORING_VERSION,
        "entries": [{"rank": rank, **asdict(entry)} for rank, entry in enumerate(entries, start=1)],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for rank, entry in enumerate(entries, start=1):
            usage = entry.usage or {}
            writer.writerow(
                (
                    rank,
                    entry.provider,
                    entry.requested_model_id,
                    entry.served_model_id,
                    entry.safety,
                    entry.intent,
                    entry.entity,
                    entry.response,
                    entry.overall,
                    entry.parse_error_count,
                    entry.parse_error_rate,
                    entry.median_latency_ms,
                    usage.get("prompt_tokens", ""),
                    usage.get("completion_tokens", ""),
                    usage.get("total_tokens", ""),
                )
            )
    return AggregateResult(json_path=json_path, csv_path=csv_path)


def main(argv: Sequence[str] | None = None) -> int:
    """Aggregate reports from CLI-provided root into versioned artifacts."""
    parser = argparse.ArgumentParser(description="Aggregate Google remote evaluation reports.")
    parser.add_argument("--reports", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = aggregate_reports(arguments.reports, arguments.output)
    except RemoteLeaderboardError as error:
        print(f"Remote report recovery required: {error}")
        return 1
    print(result.json_path)
    print(result.csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
