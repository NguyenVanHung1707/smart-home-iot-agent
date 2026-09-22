from dataclasses import dataclass
from uuid import uuid4

import pytest

from src.services.agent_trace import (
    AgentTrace,
    DispatchOutcome,
    InMemoryTraceSink,
    LifecycleEvent,
    PersistenceError,
    TraceInput,
    TracePhase,
)


@dataclass(frozen=True, slots=True)
class _FailingSink:
    failure: PersistenceError

    def persist(self, event: LifecycleEvent) -> None:
        raise self.failure


def _input() -> TraceInput:
    return TraceInput(
        conversation_id="household-42",
        request_id=uuid4(),
        command_id=uuid4(),
        correlation_id=uuid4(),
        prompt_version="prompt-2026-08-21",
        model_version="gpt-5.6-luna-medium",
        profile_version="control-v3",
    )


def test_lifecycle_records_correlated_redacted_events() -> None:
    # Given
    sink = InMemoryTraceSink()
    trace = AgentTrace(sink=sink, input=_input(), redact_free_text=True)

    # When
    trace.record(
        TracePhase.INTERPRETATION,
        details={"free_text": "bật đèn", "pin": "1234", "raw_audio": "bytes"},
        elapsed_ms=4,
    )

    # Then
    event = sink.events[0]
    assert event.conversation_id != "household-42"
    assert event.request_id == trace.input.request_id
    assert event.command_id == trace.input.command_id
    assert event.correlation_id == trace.input.correlation_id
    assert event.prompt_version == "prompt-2026-08-21"
    assert event.model_version == "gpt-5.6-luna-medium"
    assert event.profile_version == "control-v3"
    assert event.details == {"free_text": "[REDACTED]", "pin": "[REDACTED]", "raw_audio": "[REDACTED]"}
    assert event.elapsed_ms == 4


def test_unknown_detail_field_fails_closed_before_persistence() -> None:
    # Given
    sink = InMemoryTraceSink()
    trace = AgentTrace(sink=sink, input=_input())

    # When / Then
    with pytest.raises(ValueError):
        trace.record(TracePhase.POLICY, details={"unexpected": "field"}, elapsed_ms=0)
    assert sink.events == []


def test_negative_timing_fails_closed_before_persistence() -> None:
    # Given
    sink = InMemoryTraceSink()
    trace = AgentTrace(sink=sink, input=_input())

    # When / Then
    with pytest.raises(ValueError):
        trace.record(TracePhase.POLICY, details={"policy": "allowed"}, elapsed_ms=-1)
    assert sink.events == []


def test_persistence_failure_before_dispatch_prevents_dispatch() -> None:
    # Given
    trace = AgentTrace(sink=_FailingSink(PersistenceError("store unavailable")), input=_input())
    called = False

    def dispatch() -> DispatchOutcome:
        nonlocal called
        called = True
        return DispatchOutcome.ACKNOWLEDGED

    # When / Then
    with pytest.raises(PersistenceError):
        trace.dispatch(dispatch)
    assert called is False


def test_persistence_failure_after_dispatch_returns_indeterminate_alarm() -> None:
    # Given
    class FailAfterFirstPersist:
        def __init__(self) -> None:
            self.calls = 0

        def persist(self, event: LifecycleEvent) -> None:
            self.calls += 1
            if self.calls == 2:
                raise PersistenceError("store unavailable")

    alarms: list[TraceInput] = []

    def alarm(trace_input: TraceInput) -> None:
        alarms.append(trace_input)

    trace = AgentTrace(sink=FailAfterFirstPersist(), input=_input(), alarm=alarm)

    # When
    result = trace.dispatch(lambda: DispatchOutcome.ACKNOWLEDGED)

    # Then
    assert result == DispatchOutcome.INDETERMINATE
    assert trace.alarm_raised is True
    assert alarms == [trace.input]
