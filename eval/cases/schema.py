"""Strict schema for frozen behavior cases and reports."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DialogueAct = Literal["CONTROL", "CLARIFY", "INFORM", "REFUSE"]
CounterName = Literal[
    "executor",
    "publish",
    "simulator_mutation",
    "approval_consumption",
    "verified_success_claim",
]


class ExpectedBehavior(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    act: DialogueAct
    slots: dict[str, str] = Field(default_factory=dict)


class ActionCounters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executor: int = Field(default=0, ge=0)
    publish: int = Field(default=0, ge=0)
    simulator_mutation: int = Field(default=0, ge=0)
    approval_consumption: int = Field(default=0, ge=0)
    verified_success_claim: int = Field(default=0, ge=0)


class AdversarialCase(BaseModel):
    """Frozen hostile input with an explicitly non-mutating expected outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    utterance: str = Field(min_length=1)
    categories: frozenset[str] = Field(min_length=1)
    llm_mode: Literal["on", "off"]
    profile: Literal["fixture", "chat-only"]
    expected: ExpectedBehavior
    simulator_mode: Literal["fake-mqtt", "simulator-offline", "simulator-timeout"]


class AdversarialOutcome(BaseModel):
    """Observed outcome for a hostile input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    categories: frozenset[str]
    observed: ExpectedBehavior
    counters: ActionCounters
    passed: bool


class BehaviorCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    utterance: str = Field(min_length=1)
    history: tuple[str, ...] = ()
    categories: frozenset[str] = Field(min_length=1)
    expected: ExpectedBehavior
    allowed_tools: frozenset[str] = frozenset()
    must_claim: tuple[str, ...] = ()
    must_not_claim: tuple[str, ...] = ()


class CaseOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    utterance: str
    history: tuple[str, ...]
    categories: frozenset[str]
    expected: ExpectedBehavior
    allowed_tools: frozenset[str]
    must_claim: tuple[str, ...]
    must_not_claim: tuple[str, ...]
    observed: ExpectedBehavior
    counters: ActionCounters
    passed: bool


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    counters: ActionCounters


class BehaviorReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_version: Literal["behavior-v1"]
    suite: Literal["behavior"]
    profile: Literal["fixture"]
    run_id: str = Field(min_length=1)
    cases: tuple[CaseOutcome, ...]
    summary: Summary


class AdversarialSummary(BaseModel):
    """Fail-closed summary with thresholds for every unsafe side effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    unsafe_action: int = Field(ge=0)
    hallucinated_success: int = Field(ge=0)
    counters: ActionCounters


class AdversarialReport(BaseModel):
    """Deterministic Task 14 adversarial evaluation artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_version: Literal["adversarial-v1"]
    suite: Literal["adversarial"]
    profile: Literal["fixture"]
    run_id: str = Field(min_length=1)
    adapter: Literal["safe", "unsafe"]
    cases: tuple[AdversarialOutcome, ...]
    summary: AdversarialSummary
