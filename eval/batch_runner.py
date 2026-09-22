"""Operator-only workflow for sequential one-model-at-a-time evaluation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from eval.leaderboard import LeaderboardError, aggregate_reports, load_reports
from eval.model_discovery import DiscoveredModels, ModelIdentity, discover_models

DEFAULT_REPORTS: Final = Path("eval/results/live")
DEFAULT_OUTPUT: Final = Path("eval/results/leaderboard")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guide operator through six sequential live model evaluations.")
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover")
    discover.add_argument("--models", required=True, type=Path)
    next_model = commands.add_parser("next")
    next_model.add_argument("--models", required=True, type=Path)
    next_model.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--models", required=True, type=Path)
    aggregate.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    aggregate.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _template(model: ModelIdentity) -> str:
    return (
        f"model={model.relative_path} sha256={model.sha256}\n"
        f"Operator: configure llama model path for {model.relative_path}\n"
        "Operator: docker compose up llama, then run live evaluator with matching model sha256\n"
        "This tool never starts or restarts Docker or llama."
    )


def _discover(discovered: DiscoveredModels) -> None:
    for model in discovered.models:
        print(_template(model))


def _next(discovered: DiscoveredModels, reports_root: Path) -> None:
    completed = {report.model.sha256 for report in load_reports(reports_root) if report.complete}
    pending = next((model for model in discovered.models if model.sha256 not in completed), None)
    if pending is None:
        print("All discovered models have complete reports; run aggregate.")
        return
    print(_template(pending))


def main(argv: Sequence[str] | None = None) -> int:
    """Execute read/write-only workflow; never invoke external processes."""
    arguments = _parser().parse_args(argv)
    discovered = discover_models(arguments.models)
    try:
        match arguments.command:
            case "discover":
                _discover(discovered)
            case "next":
                _next(discovered, arguments.reports)
            case "aggregate":
                result = aggregate_reports(discovered, arguments.reports, arguments.output)
                print(result.json_path)
                print(result.csv_path)
            case unreachable:
                raise AssertionError(unreachable)
    except LeaderboardError as error:
        print(f"Report recovery required: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
