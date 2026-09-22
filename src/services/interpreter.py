"""Bounded, side-effect-free Vietnamese dialogue interpretation."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, ValidationError, model_validator

from src.models.actions import ActionProposal
from src.models.dialogue import DialogueAct
from src.services.devices import registry
from src.services.model_adapter import ModelAdapter


class DialogueInterpretation(BaseModel):
    """Typed, non-authoritative result produced by Luna."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    act: DialogueAct
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=128)
    proposals: tuple[ActionProposal, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def proposals_only_for_control(self) -> DialogueInterpretation:
        if self.act is not DialogueAct.CONTROL and self.proposals:
            raise InterpretationSchemaError(detail="non-control result contains proposals")
        if self.act is DialogueAct.CONTROL and not self.proposals:
            raise InterpretationSchemaError(detail="control result has no proposal")
        return self


@dataclass(frozen=True, slots=True)
class InterpretationError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class InterpretationSchemaError(ValueError):
    detail: str

    def __str__(self) -> str:
        return self.detail


_QUOTED_OR_HYPOTHETICAL: Final = ("neu ", "gia su", "cau ", "nghia la gi", "vi du")
_FUTURE_OR_SCHEDULE: Final = ("toi nay", "ngay mai", "lat nua", "hen lich", "luc ")
_SENSITIVE: Final = ("mo khoa", "mo cua", "unlock")
_SCENE: Final = ("che do", "canh ", "scene")
_NEGATION: Final = ("dung ", "khong ", "chua ", "khoi ")
_CANCEL: Final = ("huy", "bo di", "thoi")
_SMALL_TALK: Final = ("xin chao", "chao luna", "cam on", "tam biet")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    plain = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9?]+", " ", plain)).strip()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _device_id(text: str) -> str | None:
    normalized = text.replace("phong khat", "phong khach")
    for device in registry.list():
        if normalized.find(device.id.casefold()) >= 0:
            return device.id
        if normalized.find(_normalize(device.name)) >= 0:
            return device.id
    return None


def _action(text: str) -> str | None:
    has_on = bool(re.search(r"\b(?:bat|mo|turn on)\b", text))
    has_off = bool(re.search(r"\b(?:tat|turn off)\b", text))
    if has_on == has_off:
        return None
    return "on" if has_on else "off"


def _result(act: DialogueAct, reason: str, confidence: float = 1.0) -> DialogueInterpretation:
    return DialogueInterpretation(act=act, confidence=confidence, reason=reason)


class LunaInterpreter:
    """Interpret one utterance, with at most one model repair attempt."""

    def __init__(self, adapter: ModelAdapter) -> None:
        self._adapter = adapter

    async def interpret(self, request_id: UUID, utterance: str) -> DialogueInterpretation:
        text = _normalize(utterance)
        deterministic = self._deterministic(request_id, text)
        if deterministic is not None:
            return deterministic
        return await self._interpret_with_model(utterance)

    def _deterministic(self, request_id: UUID, text: str) -> DialogueInterpretation | None:
        device_id = _device_id(text)
        action = _action(text)
        if _contains_any(text, _SENSITIVE):
            return _result(DialogueAct.REFUSE, "sensitive_action")
        if _contains_any(text, _FUTURE_OR_SCHEDULE):
            return _result(DialogueAct.REFUSE, "unsupported_schedule")
        if _contains_any(text, _SCENE):
            return _result(DialogueAct.REFUSE, "unsupported_scope")
        if _contains_any(text, _QUOTED_OR_HYPOTHETICAL):
            return _result(DialogueAct.INFORM, "non_executable_reference")
        if _contains_any(text, _NEGATION) and action is not None:
            return _result(DialogueAct.INFORM, "negated_request")
        if _contains_any(text, _CANCEL):
            return _result(DialogueAct.INFORM, "cancel_request")
        if _contains_any(text, _SMALL_TALK):
            return _result(DialogueAct.INFORM, "limited_small_talk")
        if "?" in text or "dang " in text:
            if device_id is not None:
                return _result(DialogueAct.INFORM, "state_query")
            if action is None:
                return _result(DialogueAct.INFORM, "general_knowledge")
        if re.search(r"\b(?:bat|tat).+\b(?:bat|tat)\b", text):
            return _result(DialogueAct.CLARIFY, "conflicting_actions")
        if device_id is not None and action is None:
            return _result(DialogueAct.CLARIFY, "ambiguous_action")
        if (
            ("quat" in text or "dieu hoa" in text or "den" in text or "rem" in text or "khoa" in text or "loa" in text)
            and action is not None
            and device_id is None
        ):
            return _result(DialogueAct.CLARIFY, "ambiguous_device")
        if device_id is None or action is None:
            return None
        proposal = ActionProposal(
            request_id=request_id,
            correlation_id=uuid4(),
            device_id=device_id,
            action=action,
            confidence=0.95,
        )
        return DialogueInterpretation(
            act=DialogueAct.CONTROL,
            confidence=0.95,
            reason="low_risk_control_proposal",
            proposals=(proposal,),
        )

    async def _interpret_with_model(self, utterance: str) -> DialogueInterpretation:
        prompt = (
            "Classify this Vietnamese utterance. Return JSON only with act, confidence, reason, proposals. "
            "Only inform, clarify, or refuse are allowed here; proposals must be empty. Utterance: "
            f"{utterance}"
        )
        for attempt in range(2):
            try:
                response = await self._adapter.chat(prompt)
                interpretation = DialogueInterpretation.model_validate(json.loads(response))
                if interpretation.act is DialogueAct.CONTROL or interpretation.proposals:
                    raise InterpretationSchemaError(detail="model output crossed control boundary")
                return interpretation
            except (json.JSONDecodeError, ValidationError, InterpretationSchemaError):
                if attempt == 0:
                    prompt = "Repair once. Return valid JSON only; proposals must be empty."
        raise InterpretationError(detail="model output remained invalid after one repair")
