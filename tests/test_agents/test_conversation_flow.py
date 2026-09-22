from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.agents.nodes.clarify import (
    ActionFlow,
    BatchOutcome,
    ClarificationReply,
    ClarificationStatus,
)
from src.models.actions import ActionProposal, ActionProposalBatch, ValidatedCommand
from src.models.dialogue import UnresolvedSlot
from src.models.schemas import Device
from src.services.context_store import ContextStore
from src.services.executor import (
    ExecutionResult,
    ExecutionStatus,
    Executor,
    InMemoryExecutionLedger,
)
from src.services.mqtt import CommandVerification, VerificationStatus


@dataclass
class FakeValidator:
    invalid_device: str | None = None

    def validate(self, proposal: ActionProposal) -> ValidatedCommand | str:
        if proposal.device_id == self.invalid_device:
            return "invalid"
        return ValidatedCommand(
            request_id=proposal.request_id,
            correlation_id=proposal.correlation_id,
            device_id=proposal.device_id,
            action=proposal.action,
            value=proposal.value,
        )


class FakeExecutor:
    def __init__(self, critical_device: str | None = None) -> None:
        self.critical_device = critical_device
        self.dispatched: list[str] = []

    def execute(self, command: ValidatedCommand) -> ExecutionResult:
        self.dispatched.append(command.device_id)
        status = ExecutionStatus.FAILED if command.device_id == self.critical_device else ExecutionStatus.SUCCEEDED
        return ExecutionResult(command.request_id, command.device_id, status, "result")


def proposal(device_id: str, *, request_id: UUID | None = None, action: str = "on") -> ActionProposal:
    identity = request_id or uuid4()
    return ActionProposal(
        request_id=identity,
        correlation_id=uuid4(),
        device_id=device_id,
        action=action,
        confidence=1.0,
    )


def batch(*device_ids: str) -> ActionProposalBatch:
    request_id = uuid4()
    return ActionProposalBatch(
        request_id=request_id,
        actions=tuple(proposal(device_id, request_id=request_id) for device_id in device_ids),
    )


def flow(
    tmp_path: Path, now: list[datetime], executor: FakeExecutor, validator: FakeValidator | None = None
) -> ActionFlow:
    store = ContextStore(tmp_path / "context.db", clock=lambda: now[0], ttl_seconds=60)
    return ActionFlow(store=store, validator=validator or FakeValidator(), executor=executor)


def test_ordered_batch_validates_every_action_before_first_dispatch(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor, FakeValidator(invalid_device="bad"))

    # When
    result = service.execute("session", batch("first", "bad", "third"))

    # Then
    assert result.outcome is BatchOutcome.FAILED
    assert executor.dispatched == []


def test_ordered_batch_preserves_order_and_stops_after_critical_failure(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor(critical_device="second")
    service = flow(tmp_path, now, executor)

    # When
    result = service.execute("session", batch("first", "second", "third"))

    # Then
    assert result.outcome is BatchOutcome.PARTIAL_SUCCESS
    assert executor.dispatched == ["first", "second"]
    assert tuple(item.status for item in result.actions) == (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.NOT_DISPATCHED,
    )


def test_exactly_five_actions_are_accepted_and_dispatched_in_order(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor)

    # When
    result = service.execute("session", batch("one", "two", "three", "four", "five"))

    # Then
    assert result.outcome is BatchOutcome.SUCCESS
    assert executor.dispatched == ["one", "two", "three", "four", "five"]


def test_sixth_action_is_rejected_by_typed_batch() -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        batch("one", "two", "three", "four", "five", "six")


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": str(uuid4()), "actions": [{"forged": True}]},
        {"request_id": "malformed", "actions": []},
    ],
)
def test_forged_or_malformed_batch_is_rejected_at_typed_boundary(payload: dict[str, object]) -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        ActionProposalBatch.model_validate(payload)


def test_ambiguous_request_asks_once_and_answer_resumes(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor)
    pending = batch("living-fan")

    # When
    question = service.clarify(
        "session",
        pending,
        "Phòng nào?",
        (UnresolvedSlot(name="device", reason="ambiguous"),),
    )
    result = service.resume("session", ClarificationReply(answer="phòng khách", batch=pending))

    # Then
    assert question.status is ClarificationStatus.REQUIRED
    assert result.outcome is BatchOutcome.SUCCESS
    assert executor.dispatched == ["living-fan"]


def test_stale_or_mismatched_persisted_batch_never_dispatches(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor)
    pending = batch("living-fan")
    service.clarify("session", pending, "Phòng nào?", ())

    # When
    mismatched = service.resume("session", ClarificationReply(answer="phòng khách", batch=batch("living-light")))
    stale = service.resume("missing", ClarificationReply(answer="phòng khách", batch=pending))

    # Then
    assert mismatched.status is ClarificationStatus.REJECTED
    assert stale.status is ClarificationStatus.EXPIRED
    assert executor.dispatched == []


def test_orchestration_uses_existing_executor_ledger_and_verification_boundary(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]

    @dataclass
    class Registry:
        device: Device = field(
            default_factory=lambda: Device(
                id="living-fan",
                name="Fan",
                room="Living room",
                kind="fan",
                state={"power": False},
            )
        )
        validation_calls: int = 0

        def get(self, device_id: str) -> Device | None:
            return self.device if device_id == self.device.id else None

        def validate_command(
            self,
            device_id: str,
            action: str,
            value: str | int | float | bool | None = None,
            *,
            approved_sensitive: bool = False,
        ) -> tuple[Device | None, str | None]:
            del approved_sensitive
            self.validation_calls += 1
            return (self.get(device_id), None) if action == "on" and value is None else (None, "invalid")

        def capabilities(self, device: Device) -> dict[str, list[str]]:
            del device
            return {"actions": ["on"]}

    class VerificationSpy:
        def __init__(self) -> None:
            self.calls = 0

        def command(
            self,
            device_id: str,
            action: str,
            value: str | int | float | bool | None = None,
        ) -> CommandVerification:
            del action, value
            self.calls += 1
            return CommandVerification(VerificationStatus.STATE_VERIFIED, "state_verified", registry.get(device_id))

    registry = Registry()
    verification = VerificationSpy()
    ledger = InMemoryExecutionLedger()
    executor = Executor(registry=registry, transport=verification, ledger=ledger)
    service = ActionFlow(ContextStore(tmp_path / "context.db", clock=lambda: now[0]), FakeValidator(), executor)
    requested = batch("living-fan")

    # When
    first = service.execute("session", requested)
    replay = service.execute("session", requested)

    # Then
    assert first.outcome is BatchOutcome.SUCCESS
    assert replay.actions == first.actions
    assert registry.validation_calls == 1
    assert verification.calls == 1


def test_cancel_and_expired_reply_never_dispatch(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor)
    pending = batch("living-fan")
    service.clarify("session", pending, "Phòng nào?", ())

    # When
    cancelled = service.resume("session", ClarificationReply(answer="hủy", batch=pending))
    service.clarify("expired", pending, "Phòng nào?", ())
    now[0] += timedelta(seconds=61)
    expired = service.resume("expired", ClarificationReply(answer="phòng khách", batch=pending))

    # Then
    assert cancelled.status is ClarificationStatus.CANCELLED
    assert expired.status is ClarificationStatus.EXPIRED
    assert executor.dispatched == []


def test_chat_consent_cannot_confirm_sensitive_action(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    executor = FakeExecutor()
    service = flow(tmp_path, now, executor)
    sensitive = batch("entry-lock")
    service.clarify("session", sensitive, "Xác nhận?", ())

    # When
    result = service.resume("session", ClarificationReply(answer="đồng ý", batch=sensitive, sensitive=True))

    # Then
    assert result.status is ClarificationStatus.REJECTED
    assert executor.dispatched == []
