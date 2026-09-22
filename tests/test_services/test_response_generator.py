from dataclasses import FrozenInstanceError

import pytest

from src.services.response_generator import (
    ActionFact,
    ResponseCandidate,
    ResponseFacts,
    ResponseKind,
    ResponseValidator,
    generate_response,
)


def action(
    device: str,
    status: ResponseKind,
    *,
    name: str = "đèn phòng khách",
    verb: str = "bật",
    value: str | None = None,
    evidence: str | None = None,
) -> ActionFact:
    return ActionFact(device_id=device, device_name=name, action=verb, value=value, status=status, evidence=evidence)


def test_success_requires_verified_completion() -> None:
    # Given
    facts = ResponseFacts(
        ResponseKind.SUCCESS, (action("living-light", ResponseKind.SUCCESS, evidence="STATE_VERIFIED"),)
    )

    # When
    response = generate_response(facts)

    # Then
    assert response.kind is ResponseKind.SUCCESS
    assert response.used_candidate is False
    assert "đã" in response.text.casefold()


@pytest.mark.parametrize("evidence", [None, "ACK", "FAILED"])
def test_ack_only_or_failed_evidence_never_claims_success(evidence: str | None) -> None:
    # Given
    facts = ResponseFacts(ResponseKind.SUCCESS, (action("living-light", ResponseKind.SUCCESS, evidence=evidence),))

    # When
    response = generate_response(facts)

    # Then
    assert response.kind is ResponseKind.INDETERMINATE
    assert "đã bật" not in response.text.casefold()


@pytest.mark.parametrize(
    ("kind", "expected_fragment"),
    [
        (ResponseKind.DENIED, "không thể"),
        (ResponseKind.TIMEOUT, "chưa nhận"),
        (ResponseKind.INDETERMINATE, "chưa thể xác nhận"),
        (ResponseKind.CLARIFICATION, "cho mình biết"),
    ],
)
def test_deterministic_non_success_templates(kind: ResponseKind, expected_fragment: str) -> None:
    # Given
    facts = ResponseFacts(kind, (action("living-light", kind),))

    # When
    response = generate_response(facts)

    # Then
    assert expected_fragment in response.text.casefold()


def test_partial_response_preserves_per_action_truth() -> None:
    # Given
    facts = ResponseFacts(
        ResponseKind.PARTIAL,
        (
            action("living-light", ResponseKind.SUCCESS, evidence="COMPLETED"),
            action("bedroom-fan", ResponseKind.FAILED, name="quạt phòng ngủ", verb="tắt"),
        ),
    )

    # When
    response = generate_response(facts)

    # Then
    assert "đèn phòng khách" in response.text
    assert "quạt phòng ngủ" in response.text
    assert response.kind is ResponseKind.PARTIAL


def test_candidate_with_extra_device_falls_back_to_safe_template() -> None:
    # Given
    facts = ResponseFacts(
        ResponseKind.SUCCESS, (action("living-light", ResponseKind.SUCCESS, evidence="STATE_VERIFIED"),)
    )
    candidate = ResponseCandidate(
        "Mình đã bật đèn phòng khách và quạt phòng ngủ.",
        ResponseKind.SUCCESS,
        facts.actions + (action("bedroom-fan", ResponseKind.SUCCESS, name="quạt phòng ngủ", evidence="COMPLETED"),),
    )

    # When
    response = generate_response(facts, candidate)

    # Then
    assert response.used_candidate is False
    assert "quạt phòng ngủ" not in response.text


def test_candidate_with_flipped_status_falls_back_to_safe_template() -> None:
    # Given
    facts = ResponseFacts(ResponseKind.FAILED, (action("living-light", ResponseKind.FAILED),))
    candidate = ResponseCandidate(
        "Mình đã bật đèn phòng khách.",
        ResponseKind.SUCCESS,
        (action("living-light", ResponseKind.SUCCESS, evidence="COMPLETED"),),
    )

    # When
    response = generate_response(facts, candidate)

    # Then
    assert response.used_candidate is False
    assert response.kind is ResponseKind.FAILED
    assert "đã bật" not in response.text.casefold()


def test_exact_fact_candidate_is_accepted_without_repeating_raw_request() -> None:
    # Given
    facts = ResponseFacts(
        ResponseKind.SUCCESS, (action("living-light", ResponseKind.SUCCESS, evidence="STATE_VERIFIED"),)
    )
    candidate = ResponseCandidate("Xong rồi nhé, đèn phòng khách đang bật.", facts.kind, facts.actions)

    # When
    response = generate_response(facts, candidate)

    # Then
    assert response.used_candidate is True
    assert response.text == candidate.text


def test_response_facts_are_frozen_and_validator_reports_mutation() -> None:
    # Given
    facts = ResponseFacts(ResponseKind.FAILED, (action("living-light", ResponseKind.FAILED),))
    candidate = ResponseCandidate("Đã bật.", ResponseKind.SUCCESS, facts.actions)

    # When
    validation = ResponseValidator.validate(facts, candidate)

    # Then
    assert validation.accepted is False
    assert validation.reason == "factual_mutation"
    with pytest.raises(FrozenInstanceError):
        facts.kind = ResponseKind.SUCCESS
