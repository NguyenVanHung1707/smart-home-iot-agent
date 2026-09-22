from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat


class DialogueAct(StrEnum):
    CONTROL = "control"
    CLARIFY = "clarify"
    INFORM = "inform"
    REFUSE = "refuse"


class UnresolvedSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=256)


class DialogueTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    act: DialogueAct
    utterance: str = Field(min_length=1, max_length=5000)
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    unresolved_slots: tuple[UnresolvedSlot, ...] = Field(default=(), max_length=32)
