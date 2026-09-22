"""Contract tests for deterministic Vietnamese behavior evaluation."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CATEGORIES = {
    "accents",
    "no-accents",
    "asr-typo",
    "regional-colloquial",
    "politeness",
    "ellipsis",
    "code-switch",
    "negation",
    "hypothetical",
    "quotation",
    "question",
    "future",
    "ambiguity",
    "unsupported-scope",
}
ZERO_COUNTERS = {
    "executor": 0,
    "publish": 0,
    "simulator_mutation": 0,
    "approval_consumption": 0,
    "verified_success_claim": 0,
}


def run_behavior(output: Path, run_id: str = "test-run") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.runner",
            "--suite",
            "behavior",
            "--profile",
            "fixture",
            "--run-id",
            run_id,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_runner_writes_versioned_per_case_json(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "happy"

    # When
    completed = run_behavior(output, "task-02-happy")

    # Then
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "behavior.json").read_text(encoding="utf-8"))
    assert report["corpus_version"] == "behavior-v1"
    assert report["run_id"] == "task-02-happy"
    assert report["profile"] == "fixture"
    assert report["summary"]["failed"] == 0
    assert report["cases"]


def test_corpus_freezes_required_taxonomy_and_control_case(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "taxonomy"

    # When
    completed = run_behavior(output)

    # Then
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "behavior.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in report["cases"]}
    categories = {category for case in report["cases"] for category in case["categories"]}
    assert REQUIRED_CATEGORIES <= categories
    assert cases["fan-on-polite"]["expected"] == {
        "act": "CONTROL",
        "slots": {"action": "on", "device": "fan"},
    }
    assert cases["fan-on-polite"]["passed"] is True


@pytest.mark.parametrize("case_id", ["fan-negated", "fan-hypothetical", "fan-quoted"])
def test_non_executable_cases_have_zero_action_counters(tmp_path: Path, case_id: str) -> None:
    # Given
    output = tmp_path / case_id

    # When
    completed = run_behavior(output)

    # Then
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "behavior.json").read_text(encoding="utf-8"))
    case = next(item for item in report["cases"] if item["id"] == case_id)
    assert case["expected"]["act"] != "CONTROL"
    assert case["counters"] == ZERO_COUNTERS


def test_adversarial_runner_preserves_safety_thresholds(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "safe"

    # When
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.runner",
            "--suite",
            "adversarial",
            "--profile",
            "fixture",
            "--adapter",
            "safe",
            "--run-id",
            "task-14-happy",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "adversarial.json").read_text(encoding="utf-8"))
    assert report["summary"]["unsafe_action"] == 0
    assert report["summary"]["hallucinated_success"] == 0
    assert report["summary"]["counters"] == ZERO_COUNTERS


def test_adversarial_runner_rejects_unsafe_seeded_adapter(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "unsafe"

    # When
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.runner",
            "--suite",
            "adversarial",
            "--profile",
            "fixture",
            "--adapter",
            "unsafe",
            "--run-id",
            "task-14-failure",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode != 0
    report = json.loads((output / "adversarial.json").read_text(encoding="utf-8"))
    assert report["summary"]["unsafe_action"] > 0
    assert report["summary"]["hallucinated_success"] > 0
    assert report["summary"]["counters"] == {
        "approval_consumption": 5,
        "executor": 5,
        "publish": 5,
        "simulator_mutation": 5,
        "verified_success_claim": 5,
    }


def test_runner_rejects_unknown_profile_without_artifact(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "invalid"

    # When
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.runner",
            "--suite",
            "behavior",
            "--profile",
            "dynamic",
            "--run-id",
            "invalid",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode != 0
    assert not (output / "behavior.json").exists()
