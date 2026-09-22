"""Fact-locked Vietnamese response rendering."""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import assert_never


class ResponseKind(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    TIMEOUT = "TIMEOUT"
    INDETERMINATE = "INDETERMINATE"
    PARTIAL = "PARTIAL"
    CLARIFICATION = "CLARIFICATION"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ActionFact:
    device_id: str
    device_name: str
    action: str
    value: str | None
    status: ResponseKind
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class ResponseFacts:
    kind: ResponseKind
    actions: tuple[ActionFact, ...] = ()


@dataclass(frozen=True, slots=True)
class ResponseCandidate:
    text: str
    kind: ResponseKind
    actions: tuple[ActionFact, ...]


@dataclass(frozen=True, slots=True)
class CandidateValidation:
    accepted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class GeneratedResponse:
    text: str
    kind: ResponseKind
    used_candidate: bool


class ResponseValidator:
    """Accept paraphrases only when their structured claims equal verified facts."""

    @staticmethod
    def validate(facts: ResponseFacts, candidate: ResponseCandidate) -> CandidateValidation:
        accepted = bool(candidate.text.strip()) and candidate.kind is facts.kind and candidate.actions == facts.actions
        return CandidateValidation(accepted, "accepted" if accepted else "factual_mutation")


def _is_verified(action: ActionFact) -> bool:
    return action.status is ResponseKind.SUCCESS and action.evidence in {"STATE_VERIFIED", "COMPLETED"}


def _safe_facts(facts: ResponseFacts) -> ResponseFacts:
    if facts.kind is ResponseKind.SUCCESS and not facts.actions:
        return replace(facts, kind=ResponseKind.INDETERMINATE)
    if facts.kind is ResponseKind.SUCCESS and not all(_is_verified(action) for action in facts.actions):
        return replace(facts, kind=ResponseKind.INDETERMINATE)
    return facts


def _description(action: ActionFact) -> str:
    value = f" ở mức {action.value}" if action.value is not None else ""
    return f"{action.action} {action.device_name}{value}"


def _render_action(action: ActionFact) -> str:
    description = _description(action)
    match action.status:
        case ResponseKind.SUCCESS:
            return f"đã {description}" if _is_verified(action) else f"chưa thể xác nhận {description}"
        case ResponseKind.DENIED:
            return f"không thể {description}"
        case ResponseKind.TIMEOUT:
            return f"chưa nhận được xác nhận cho {description}"
        case ResponseKind.INDETERMINATE:
            return f"chưa thể xác nhận {description}"
        case ResponseKind.FAILED:
            return f"không {description} được"
        case ResponseKind.CLARIFICATION:
            return f"cần làm rõ việc {description}"
        case ResponseKind.PARTIAL:
            return f"chưa thể xác nhận {description}"
        case unreachable:
            assert_never(unreachable)


def _template(facts: ResponseFacts) -> str:
    details = "; ".join(_render_action(action) for action in facts.actions)
    match facts.kind:
        case ResponseKind.SUCCESS:
            return f"Xong rồi nhé, mình {details}."
        case ResponseKind.DENIED:
            return f"Mình không thể thực hiện việc này{f': {details}' if details else ''}."
        case ResponseKind.TIMEOUT:
            return f"Mình chưa nhận được xác nhận{f': {details}' if details else ''}."
        case ResponseKind.INDETERMINATE:
            return f"Mình chưa thể xác nhận kết quả{f': {details}' if details else ''}."
        case ResponseKind.PARTIAL:
            return f"Mình xử lý được một phần: {details}."
        case ResponseKind.CLARIFICATION:
            return "Bạn cho mình biết rõ thiết bị hoặc thao tác nhé."
        case ResponseKind.FAILED:
            return f"Mình chưa thực hiện được{f': {details}' if details else ''}."
        case unreachable:
            assert_never(unreachable)


def generate_response(facts: ResponseFacts, candidate: ResponseCandidate | None = None) -> GeneratedResponse:
    """Render safe response, using optional paraphrase only for identical claims."""
    safe = _safe_facts(facts)
    if candidate is not None and ResponseValidator.validate(safe, candidate).accepted:
        return GeneratedResponse(candidate.text.strip(), safe.kind, True)
    return GeneratedResponse(_template(safe), safe.kind, False)
