"""Validation for the standalone Vietnamese smart-home review corpus."""

import json
from pathlib import Path

from eval.cases.golden import GOLDEN_CASES_V1
from eval.cases.smart_home_review_golden import (
    REVIEW_CASES_V1,
    REVIEW_CORPUS_VERSION,
    ReviewCase,
    ReviewToolCall,
)
from src.agents.tools.runtime import TOOLS

EXPECTED_FIELDS = {
    "id",
    "description",
    "utterance",
    "categories",
    "expected_act",
    "safety_class",
    "expected_tool_calls",
    "required_concepts",
    "forbidden_concepts",
    "notes",
}
EXPECTED_ACTS = {"CONTROL", "CLARIFY", "INFORM", "REFUSE"}
EXPECTED_SAFETY_CLASSES = {"ROUTINE", "READ_ONLY", "AMBIGUOUS", "UNSUPPORTED", "SENSITIVE", "ADVERSARIAL"}
REQUIRED_CATEGORIES = {
    "security",
    "jailbreak",
    "prompt-injection",
    "sensitive-unlock",
    "multi-command",
    "self-correction",
    "ambiguity",
    "negation",
    "quoted",
    "hypothetical",
    "no-accents",
    "asr-typo",
    "regional",
    "unsupported-schedule",
    "unsupported-scope",
    "read-only",
    "status",
    "value-boundary",
    "temperature",
    "brightness",
}
REPO_ROOT = Path(__file__).resolve().parents[1]
DEVICE_REGISTRY_PATH = REPO_ROOT / "runtime" / "devices.json"
CONTROL_TOOL_KINDS = {
    "control_light": "light",
    "control_aircon": "aircon",
    "control_blind": "blind",
    "control_speaker": "speaker",
    "control_display": "display",
    "control_lock": "lock",
    "request_unlock_approval": "lock",
}


def _registry_devices() -> list[dict]:
    return json.loads(DEVICE_REGISTRY_PATH.read_text(encoding="utf-8"))


def test_review_corpus_has_at_least_100_cases_and_unique_ids() -> None:
    case_ids = [case.id for case in REVIEW_CASES_V1]

    assert REVIEW_CORPUS_VERSION == "vietnamese-smart-home-review-v1"
    assert len(REVIEW_CASES_V1) >= 100
    assert len(case_ids) == len(set(case_ids))


def test_review_corpus_shape_and_tool_calls_are_explicit() -> None:
    runtime_tool_names = {tool.name for tool in TOOLS}
    runtime_tools = {tool.name: tool for tool in TOOLS}

    for case in REVIEW_CASES_V1:
        payload = case.model_dump()
        assert isinstance(case, ReviewCase)
        assert set(payload) == EXPECTED_FIELDS
        assert case.expected_act in EXPECTED_ACTS
        assert case.safety_class in EXPECTED_SAFETY_CLASSES
        assert case.categories
        assert case.required_concepts
        assert case.forbidden_concepts
        assert isinstance(case.expected_tool_calls, tuple)
        for call in case.expected_tool_calls:
            assert isinstance(call, ReviewToolCall)
            assert call.name in runtime_tool_names
            runtime_tools[call.name].args_schema.model_validate(call.args)


def test_review_corpus_covers_required_taxonomy() -> None:
    categories = {category for case in REVIEW_CASES_V1 for category in case.categories}
    acts = {case.expected_act for case in REVIEW_CASES_V1}
    safety_classes = {case.safety_class for case in REVIEW_CASES_V1}

    assert REQUIRED_CATEGORIES <= categories
    assert acts == EXPECTED_ACTS
    assert safety_classes == EXPECTED_SAFETY_CLASSES


def test_review_corpus_is_new_and_covers_all_runtime_tools() -> None:
    legacy_ids = {case.id for case in GOLDEN_CASES_V1}
    legacy_utterances = {case.utterance for case in GOLDEN_CASES_V1}
    review_ids = {case.id for case in REVIEW_CASES_V1}
    review_utterances = {case.utterance for case in REVIEW_CASES_V1}
    runtime_tool_names = {tool.name for tool in TOOLS}
    covered_tool_names = {call.name for case in REVIEW_CASES_V1 for call in case.expected_tool_calls}

    assert len(review_utterances) == len(REVIEW_CASES_V1)
    assert legacy_ids.isdisjoint(review_ids)
    assert legacy_utterances.isdisjoint(review_utterances)
    assert runtime_tool_names <= covered_tool_names


def test_review_tool_calls_only_reference_runtime_registry() -> None:
    devices = _registry_devices()
    rooms = {device["room"] for device in devices}
    kinds = {device["kind"] for device in devices}
    device_ids = {device["id"] for device in devices}
    room_kind_pairs = {(device["room"], device["kind"]) for device in devices}

    for case in REVIEW_CASES_V1:
        for call in case.expected_tool_calls:
            name = call.name
            args = call.args
            room = args.get("room")
            kind = args.get("kind")
            device_id = args.get("device_id")

            if room is not None:
                assert room in rooms, case.id
            if kind is not None:
                assert kind in kinds, case.id
            if device_id is not None:
                assert device_id in device_ids, case.id

            if name in CONTROL_TOOL_KINDS and room is not None:
                assert (room, CONTROL_TOOL_KINDS[name]) in room_kind_pairs, case.id

            if name == "set_device_timer" and room is not None and kind is not None:
                assert (room, kind) in room_kind_pairs, case.id


def test_nonexistent_room_cases_never_carry_gold_tool_calls() -> None:
    """Hallucination probes: a case naming a room outside the registry must expect no action.

    This is the complement of ``test_review_tool_calls_only_reference_runtime_registry``.
    That test says "any room in gold must exist"; this one says a case built around a room
    that does *not* exist must not be quietly retargeted to a room that does.
    """
    probes = [case for case in REVIEW_CASES_V1 if "nonexistent-room" in case.categories]

    assert len(probes) >= 5
    for case in probes:
        assert case.expected_tool_calls == (), case.id
        assert case.expected_act in {"INFORM", "CLARIFY", "REFUSE"}, case.id


def test_review_reads_only_target_devices_that_exist() -> None:
    """A gold read must be satisfiable: the room must own a sensor / the requested signal."""
    devices = _registry_devices()
    sensor_signals: dict[str, set[str]] = {}
    for device in devices:
        if device["kind"] == "sensor":
            sensor_signals.setdefault(device["room"], set()).update(device.get("state", {}))

    for case in REVIEW_CASES_V1:
        for call in case.expected_tool_calls:
            if call.name != "get_sensor_data":
                continue
            room = call.args.get("room")
            sensor_type = call.args.get("sensor_type")
            if room is not None:
                assert room in sensor_signals, case.id
            if room is not None and sensor_type is not None:
                assert sensor_type in sensor_signals[room], case.id
