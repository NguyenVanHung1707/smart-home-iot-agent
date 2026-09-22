"""Kiểm tra hợp đồng và tính toàn vẹn của bộ ca vàng tiếng Việt."""

import pytest
from pydantic import ValidationError

from eval.cases.golden import GOLDEN_CASES_V1, GOLDEN_CORPUS_VERSION
from eval.cases.golden_schema import GoldenCase

REQUIRED_ACTS = {"CONTROL", "CLARIFY", "INFORM", "REFUSE"}
REQUIRED_CATEGORIES = {
    "direct-control",
    "status-info",
    "clarification",
    "refusal",
    "accents",
    "no-accents",
    "asr-typo",
    "regional",
    "quotation",
    "question",
    "negation",
    "hypothetical",
    "future-scheduling",
    "sensitive-unlock",
    "prompt-injection",
    "ambiguity",
}


def test_golden_schema_forbids_unknown_fields() -> None:
    # Given
    payload = {
        "id": "strict-case",
        "description": "Ca kiểm tra schema nghiêm ngặt.",
        "utterance": "Bật đèn phòng khách.",
        "categories": {"direct-control"},
        "expected_act": "CONTROL",
        "safety_class": "ROUTINE",
        "entities": {"device": "living-room-light", "action": "on"},
        "required_concepts": ("proposal_only",),
        "forbidden_concepts": ("execution_claim",),
        "unexpected": True,
    }

    # When / Then
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(payload)


def test_golden_schema_is_frozen() -> None:
    # Given
    case = GOLDEN_CASES_V1[0]

    # When / Then
    with pytest.raises(ValidationError):
        case.id = "changed"


def test_golden_corpus_has_unique_ids_and_minimum_size() -> None:
    # Given / When
    case_ids = [case.id for case in GOLDEN_CASES_V1]

    # Then
    assert GOLDEN_CORPUS_VERSION == "vietnamese-golden-v1"
    assert len(case_ids) >= 48
    assert len(case_ids) == len(set(case_ids))


def test_golden_corpus_covers_required_taxonomy() -> None:
    # Given / When
    categories = {category for case in GOLDEN_CASES_V1 for category in case.categories}
    acts = {case.expected_act for case in GOLDEN_CASES_V1}

    # Then
    assert REQUIRED_CATEGORIES <= categories
    assert acts == REQUIRED_ACTS


def test_golden_corpus_round_trips_through_strict_schema() -> None:
    # Given / When
    reparsed = tuple(GoldenCase.model_validate(case.model_dump()) for case in GOLDEN_CASES_V1)

    # Then
    assert reparsed == GOLDEN_CASES_V1
    assert all(case.required_concepts for case in reparsed)
    assert all(case.forbidden_concepts for case in reparsed)
