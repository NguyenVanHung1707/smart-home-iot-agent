from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.models.actions import ActionProposal, ValidatedCommand
from src.services.executor import (
    ExecutionStatus,
    Executor,
    InMemoryExecutionLedger,
    InvalidExecutionInputError,
)
from src.services.policy import PolicyDecision, PolicyDecisionKind


@dataclass
class FakeDevice:
    id: str = "living-fan"
    kind: str = "fan"
    online: bool = True


class FakeRegistry:
    def __init__(self) -> None:
        self.device = FakeDevice()
        self.validation_calls = 0

    def get(self, device_id: str) -> FakeDevice | None:
        return self.device if device_id == self.device.id else None

    def validate_command(
        self,
        device_id: str,
        action: str,
        value: str | int | float | bool | None = None,
        *,
        approved_sensitive: bool = False,
    ):
        self.validation_calls += 1
        if self.get(device_id) is None:
            return None, "not_found"
        if action not in {"on", "off", "toggle"}:
            return None, "unsupported_action"
        if value is not None:
            return None, "unexpected_value"
        return self.device, None

    def capabilities(self, device: FakeDevice):
        return {"actions": ["off", "on", "toggle"]}


class FakeHub:
    def __init__(self) -> None:
        self.publish_count = 0
        self.mutation_count = 0
        self.error: str | None = None

    def command(self, device_id: str, action: str, value=None):
        self.publish_count += 1
        if self.error is not None:
            return None, self.error
        self.mutation_count += 1
        return {
            "id": device_id,
            "name": "Fan",
            "room": "Living room",
            "kind": "fan",
            "state": {"power": action == "on"},
        }, None


def command(*, request_id: UUID | None = None, action: str = "on") -> ValidatedCommand:
    return ValidatedCommand(
        request_id=request_id or uuid4(),
        correlation_id=uuid4(),
        device_id="living-fan",
        action=action,
    )


def executor() -> tuple[Executor, FakeRegistry, FakeHub]:
    registry = FakeRegistry()
    hub = FakeHub()
    return Executor(registry=registry, transport=hub, ledger=InMemoryExecutionLedger()), registry, hub


def test_executor_rejects_non_validated_inputs_without_side_effects() -> None:
    # Given
    service, registry, hub = executor()
    proposal = ActionProposal(
        request_id=uuid4(),
        correlation_id=uuid4(),
        device_id="living-fan",
        action="on",
        confidence=1.0,
    )

    # When / Then
    for invalid in (proposal, {"device_id": "living-fan", "action": "on"}):
        with pytest.raises(InvalidExecutionInputError):
            service.execute(invalid)
    assert registry.validation_calls == 0
    assert hub.publish_count == 0
    assert hub.mutation_count == 0


def test_executor_rejects_forged_policy_decision_and_direct_dispatch() -> None:
    # Given
    service, registry, hub = executor()
    forged = PolicyDecision(PolicyDecisionKind.ALLOW, "forged")

    # When / Then
    with pytest.raises(InvalidExecutionInputError):
        service.execute(command(), forged)
    assert registry.validation_calls == 0
    assert hub.publish_count == 0
    assert hub.mutation_count == 0


def test_executor_dispatches_low_risk_fan_once_and_replays_result() -> None:
    # Given
    service, registry, hub = executor()
    requested = command()

    # When
    first = service.execute(requested)
    replay = service.execute(requested)

    # Then
    assert first.status is ExecutionStatus.SUCCEEDED
    assert replay == first
    assert registry.validation_calls == 1
    assert hub.publish_count == 1
    assert hub.mutation_count == 1


def test_executor_rejects_same_command_id_with_changed_hash() -> None:
    # Given
    service, registry, hub = executor()
    request_id = uuid4()
    first = command(request_id=request_id, action="on")
    changed = command(request_id=request_id, action="off")
    service.execute(first)

    # When
    result = service.execute(changed)

    # Then
    assert result.status is ExecutionStatus.NOT_DISPATCHED
    assert result.reason == "command_hash_mismatch"
    assert registry.validation_calls == 1
    assert hub.publish_count == 1
    assert hub.mutation_count == 1


def test_executor_returns_truthful_transport_failure_states() -> None:
    # Given
    service, _, hub = executor()
    hub.error = "timeout"

    # When
    timeout = service.execute(command())
    hub.error = "unavailable"
    unavailable = service.execute(command())

    # Then
    assert timeout.status is ExecutionStatus.INDETERMINATE
    assert unavailable.status is ExecutionStatus.FAILED
    assert hub.publish_count == 2
    assert hub.mutation_count == 0
