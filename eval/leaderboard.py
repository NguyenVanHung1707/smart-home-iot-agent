"""Aggregate one compatible live report for each discovered GGUF model."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eval.cases.golden import GOLDEN_CASES_V1
from eval.model_discovery import DiscoveredModels

LEADERBOARD_SCHEMA_VERSION: Final = "leaderboard-v2"
CSV_HEADER: Final = (
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
)


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    safety: float = Field(ge=0, le=1)
    intent: float = Field(ge=0, le=1)
    entity: float = Field(ge=0, le=1)
    response: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1)


class ModelReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)


class ServerIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    status: Literal["ok", "parse_error", "timeout", "transport_error"]
    raw_output: str | None
    parse_status: Literal["success", "failure", "not_attempted"]
    parse_reason: str | None
    scores: Scores
    latency_ms: float = Field(ge=0)


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_tokens: int = Field(gt=0)
    temperature: float = Field(ge=0)


class LiveReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    report_schema_version: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    scoring_version: str = Field(min_length=1)
    generation: Generation
    complete: bool
    execution_integrity: Literal["passed", "failed"]
    run_id: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    served_model_id: str = Field(min_length=1)
    server_identity: ServerIdentity
    model: ModelReference
    cases: tuple[CaseResult, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class LeaderboardError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class Entry:
    model_name: str
    model_sha256: str
    safety: float
    intent: float
    entity: float
    response: float
    parse_error_count: int
    parse_error_rate: float
    median_latency_ms: float


@dataclass(frozen=True, slots=True)
class AggregateResult:
    json_path: Path
    csv_path: Path


def load_reports(reports_root: Path) -> tuple[LiveReport, ...]:
    """Parse all JSON reports from a directory through strict versioned schema."""
    reports: list[LiveReport] = []
    for path in sorted(reports_root.glob("*.json")):
        try:
            reports.append(LiveReport.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError) as error:
            raise LeaderboardError(
                reason=f"invalid live report {path}: remove or repair this file, then retry: {error}"
            ) from error
    return tuple(reports)


def _validated_reports(discovered: DiscoveredModels, reports: tuple[LiveReport, ...]) -> tuple[LiveReport, ...]:
    expected_hashes = {str(model.sha256) for model in discovered.models}
    report_hashes = [report.model.sha256 for report in reports]
    if len(report_hashes) != len(expected_hashes) or set(report_hashes) != expected_hashes:
        raise LeaderboardError(reason="reports must contain exactly one report per discovered model hash")
    if not all(report.complete and report.execution_integrity == "passed" for report in reports):
        raise LeaderboardError(reason="all reports must have complete model responses and passed execution integrity")
    versions = {(report.report_schema_version, report.corpus_version, report.scoring_version) for report in reports}
    if len(versions) != 1:
        raise LeaderboardError(reason="reports use incompatible schema, corpus, or scoring versions")
    generation_profiles = {(report.generation.max_tokens, report.generation.temperature) for report in reports}
    if len(generation_profiles) != 1:
        raise LeaderboardError(reason="reports use incompatible generation profile")
    canonical_ids = tuple(case.id for case in GOLDEN_CASES_V1)
    case_sets = [tuple(item.id for item in report.cases) for report in reports]
    if any(ids != canonical_ids for ids in case_sets):
        raise LeaderboardError(reason="reports must match canonical GOLDEN_CASES_V1 case coverage and order")
    if any(case.status in {"timeout", "transport_error"} for report in reports for case in report.cases):
        raise LeaderboardError(reason="reports must not contain timeout or transport failures")
    if any(report.server_identity.fingerprint != report.model.sha256 for report in reports):
        raise LeaderboardError(reason="server identity fingerprint must bind the reported model hash")
    return reports


def _entry(report: LiveReport) -> Entry:
    return Entry(
        model_name=report.model.name,
        model_sha256=report.model.sha256,
        safety=fmean(case.scores.safety for case in report.cases),
        intent=fmean(case.scores.intent for case in report.cases),
        entity=fmean(case.scores.entity for case in report.cases),
        response=fmean(case.scores.response for case in report.cases),
        parse_error_count=sum(case.status == "parse_error" for case in report.cases),
        parse_error_rate=fmean(case.status == "parse_error" for case in report.cases),
        median_latency_ms=median(case.latency_ms for case in report.cases),
    )


def aggregate_reports(discovered: DiscoveredModels, reports_root: Path, output_root: Path) -> AggregateResult:
    """Validate, rank, and write deterministic versioned JSON and CSV artifacts."""
    reports = _validated_reports(discovered, load_reports(reports_root))
    entries = sorted(
        (_entry(report) for report in reports),
        key=lambda item: (
            -item.safety,
            -item.intent,
            -item.entity,
            -item.response,
            item.median_latency_ms,
            item.model_name,
        ),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / f"{LEADERBOARD_SCHEMA_VERSION}.json"
    csv_path = output_root / f"{LEADERBOARD_SCHEMA_VERSION}.csv"
    version = reports[0]
    payload = {
        "leaderboard_schema_version": LEADERBOARD_SCHEMA_VERSION,
        "report_schema_version": version.report_schema_version,
        "corpus_version": version.corpus_version,
        "scoring_version": version.scoring_version,
        "generation": version.generation.model_dump(mode="json"),
        "model_set_sha256": discovered.identity_sha256,
        "entries": [{"rank": rank, **asdict(entry)} for rank, entry in enumerate(entries, start=1)],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for rank, entry in enumerate(entries, start=1):
            writer.writerow(
                (
                    rank,
                    entry.model_name,
                    entry.model_sha256,
                    entry.safety,
                    entry.intent,
                    entry.entity,
                    entry.response,
                    entry.parse_error_count,
                    entry.parse_error_rate,
                    entry.median_latency_ms,
                )
            )
    return AggregateResult(json_path=json_path, csv_path=csv_path)
