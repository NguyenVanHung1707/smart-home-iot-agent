"""Generate deterministic local-protocol SFT examples from review control cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.cases.smart_home_review_golden import REVIEW_CASES_V1
from src.agents.local_tool_protocol import parse_local_tool_calls


def _protocol_for_case(case):
    if not case.expected_tool_calls or case.safety_class in {"SENSITIVE", "ADVERSARIAL"}:
        return None
    payload = {"calls": [{"name": call.name, "args": call.args} for call in case.expected_tool_calls]}
    content = "```tool_calls\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n```"
    try:
        parse_local_tool_calls(content)
    except Exception:
        return None
    return content


def _is_holdout(case) -> bool:
    """Match the benchmark's stable stratified holdout selection.

    Keeping this local avoids importing the benchmark runner (and its optional
    CUDA dependencies) when preparing a Kaggle upload.
    """
    grouped = [
        candidate
        for candidate in REVIEW_CASES_V1
        if (candidate.expected_act, candidate.safety_class) == (case.expected_act, case.safety_class)
    ]
    ranked = sorted(grouped, key=lambda candidate: hashlib.sha256(candidate.id.encode()).digest())
    return case.id in {candidate.id for candidate in ranked[:max(1, round(len(ranked) * 0.2))]}


def build_examples(*, split: str = "development") -> list[dict[str, object]]:
    if split not in {"development", "all"}:
        raise ValueError("split must be development or all")
    examples = []
    for case in REVIEW_CASES_V1:
        if split == "development" and _is_holdout(case):
            continue
        protocol = _protocol_for_case(case)
        if protocol:
            examples.append({"case_id": case.id, "messages": [{"role": "user", "content": case.utterance}, {"role": "assistant", "content": protocol}]})
    return examples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=("development", "all"),
        default="development",
        help="Development excludes benchmark holdout (default); all is only for non-comparative experiments.",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    examples = build_examples(split=args.split)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in examples), encoding="utf-8")
    print(f"Wrote {len(examples)} {args.split} examples to {args.output}")


if __name__ == "__main__":
    main()
