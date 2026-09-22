from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from src.models.actions import ActionProposal, ActionProposalBatch, ValidatedCommand
from src.models.dialogue import DialogueAct, DialogueTurn, UnresolvedSlot
from src.models.results import PolicyDecision, TruthState


def test_dialogue_turn_parses_typed_act_and_unresolved_slots() -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "act": "clarify",
        "utterance": "Bật đèn",
        "confidence": 0.72,
        "unresolved_slots": [{"name": "room", "reason": "ambiguous"}],
    }

    # When
    turn = DialogueTurn.model_validate(payload)

    # Then
    assert turn.act is DialogueAct.CLARIFY
    assert turn.unresolved_slots == (UnresolvedSlot(name="room", reason="ambiguous"),)


def test_confidence_rejects_bool_as_numeric() -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "act": "control",
        "utterance": "Bật đèn phòng khách",
        "confidence": True,
    }

    # When / Then
    with pytest.raises(ValidationError):
        DialogueTurn.model_validate(payload)


def test_action_proposal_accepts_at_most_five_non_authoritative_actions() -> None:
    # Given
    request_id = uuid4()
    proposals = tuple(
        ActionProposal(
            request_id=request_id,
            correlation_id=uuid4(),
            device_id=f"light-{index}",
            action="on",
            confidence=0.9,
        )
        for index in range(5)
    )

    # When
    batch = ActionProposalBatch(request_id=request_id, actions=proposals)

    # Then
    assert len(batch.actions) == 5


def test_action_batch_rejects_more_than_five_actions() -> None:
    # Given
    request_id = uuid4()
    proposals = tuple(
        ActionProposal(
            request_id=request_id,
            correlation_id=uuid4(),
            device_id=f"light-{index}",
            action="on",
            confidence=0.9,
        )
        for index in range(6)
    )

    # When / Then
    with pytest.raises(ValidationError):
        ActionProposalBatch(request_id=request_id, actions=proposals)


@pytest.mark.parametrize("forged_field", ["authorized", "approved", "completed", "truth_state"])
def test_action_proposal_rejects_forged_authority_and_completion(forged_field: str) -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "device_id": "front-door",
        "action": "lock",
        "confidence": 1.0,
        forged_field: True,
    }

    # When / Then
    with pytest.raises(ValidationError):
        ActionProposal.model_validate(payload)


def test_validated_command_requires_request_and_correlation_ids() -> None:
    # Given
    payload = {"device_id": "living-light", "action": "on"}

    # When / Then
    with pytest.raises(ValidationError):
        ValidatedCommand.model_validate(payload)


def test_validated_command_rejects_unlock_authorization() -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "device_id": "front-door",
        "action": "unlock",
    }

    # When / Then
    with pytest.raises(ValidationError):
        ValidatedCommand.model_validate(payload)


def test_models_forbid_extra_fields() -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "decision": "allow",
        "reason": "device policy permits command",
        "unexpected": "mass-assignment",
    }

    # When / Then
    with pytest.raises(ValidationError):
        PolicyDecision.model_validate(payload)


def test_truth_state_cannot_claim_completion() -> None:
    # Given
    adapter = TypeAdapter(TruthState)

    # When / Then
    with pytest.raises(ValidationError):
        adapter.validate_python("completed")


def test_policy_decision_rejects_client_forged_completion() -> None:
    # Given
    payload = {
        "request_id": str(uuid4()),
        "decision": "allow",
        "reason": "device policy permits command",
        "completed": True,
    }

    # When / Then
    with pytest.raises(ValidationError):
        PolicyDecision.model_validate(payload)
