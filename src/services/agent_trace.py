"""Fail-closed correlated lifecycle tracing for agent command handling."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Final, NewType, Protocol
from uuid import UUID

PseudonymousConversationId = NewType("PseudonymousConversationId", str)

_REDACTED: Final = "[REDACTED]"
_SECRET_FIELDS: Final = frozenset({"free_text", "pin", "raw_audio", "secret", "token", "password"})
_ALLOWED_DETAILS: Final = frozenset(
    {
        "interpretation",
        "validation",
        "policy",
        "dispatch",
        "verification",
        "fallback",
        "free_text",
        "pin",
        "raw_audio",
        "secret",
        "token",
        "password",
    }
)


class TracePhase(StrEnum):
    INTERPRETATION = "interpretation"
    VALIDATION = "validation"
    POLICY = "policy"
    DISPATCH = "dispatch"
    VERIFICATION = "verification"
    FALLBACK = "fallback"


class DispatchOutcome(StrEnum):
    NOT_DISPATCHED = "not_dispatched"
    ACKNOWLEDGED = "acknowledged"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class PersistenceError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class TraceInput:
    conversation_id: str
    request_id: UUID
    command_id: UUID
    correlation_id: UUID
    prompt_version: str
    model_version: str
    profile_version: str


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    conversation_id: PseudonymousConversationId
    request_id: UUID
    command_id: UUID
    correlation_id: UUID
    prompt_version: str
    model_version: str
    profile_version: str
    phase: TracePhase
    details: Mapping[str, str | int | float | bool]
    elapsed_ms: int


class TraceSink(Protocol):
    def persist(self, event: LifecycleEvent) -> None:
        """Durably persist one lifecycle event or raise PersistenceError."""


@dataclass(slots=True)
class InMemoryTraceSink:
    """Test sink retaining durable event order."""

    events: list[LifecycleEvent] = field(default_factory=list)

    def persist(self, event: LifecycleEvent) -> None:
        self.events.append(event)


def _raise_alarm(_: TraceInput) -> None:
    """Default alarm seam keeps the service dependency-free."""


@dataclass(slots=True)
class AgentTrace:
    """Trace one command; persistence is required before side-effect dispatch."""

    sink: TraceSink
    input: TraceInput
    redact_free_text: bool = True
    alarm: Callable[[TraceInput], None] = _raise_alarm
    alarm_raised: bool = field(init=False, default=False)

    def record(
        self,
        phase: TracePhase,
        *,
        details: Mapping[str, str | int | float | bool],
        elapsed_ms: int,
    ) -> None:
        """Validate, redact, and persist one event without permitting unknown fields."""
        if elapsed_ms < 0:
            raise ValueError("elapsed_ms must be non-negative")
        if not details.keys() <= _ALLOWED_DETAILS:
            raise ValueError("trace details contain an untrusted field")
        self.sink.persist(
            LifecycleEvent(
                conversation_id=_pseudonymize(self.input.conversation_id),
                request_id=self.input.request_id,
                command_id=self.input.command_id,
                correlation_id=self.input.correlation_id,
                prompt_version=self.input.prompt_version,
                model_version=self.input.model_version,
                profile_version=self.input.profile_version,
                phase=phase,
                details=_redact(details, self.redact_free_text),
                elapsed_ms=elapsed_ms,
            )
        )

    def dispatch(self, action: Callable[[], DispatchOutcome]) -> DispatchOutcome:
        """Persist intent before dispatch; make post-dispatch persistence ambiguity explicit."""
        self.record(TracePhase.DISPATCH, details={"dispatch": "requested"}, elapsed_ms=0)
        outcome = action()
        try:
            self.record(TracePhase.DISPATCH, details={"dispatch": outcome.value}, elapsed_ms=0)
        except PersistenceError:
            self.alarm_raised = True
            self.alarm(self.input)
            return DispatchOutcome.INDETERMINATE
        return outcome


def _pseudonymize(conversation_id: str) -> PseudonymousConversationId:
    return PseudonymousConversationId(sha256(conversation_id.encode()).hexdigest())


def _redact(
    details: Mapping[str, str | int | float | bool], redact_free_text: bool
) -> Mapping[str, str | int | float | bool]:
    return {
        key: _REDACTED if key in _SECRET_FIELDS and (key != "free_text" or redact_free_text) else value
        for key, value in details.items()
    }
