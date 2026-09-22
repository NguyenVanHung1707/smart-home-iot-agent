from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator

ScalarValue = StrictFloat | StrictInt | StrictStr | bool
CommandValue = ScalarValue | dict[str, Any]
ActionName = str


class ActionProposal(BaseModel):
    """Non-authoritative action suggested by interpretation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    correlation_id: UUID
    device_id: str = Field(min_length=1, max_length=100)
    action: ActionName
    value: CommandValue | None = None
    confidence: StrictFloat = Field(ge=0.0, le=1.0)

    @field_validator("action")
    @classmethod
    def reject_unlock(cls, value: str) -> str:
        if value == "unlock":
            raise ValueError("unlock requires external approval")
        return value


class ActionProposalBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    actions: tuple[ActionProposal, ...] = Field(max_length=5)


class ValidatedCommand(BaseModel):
    """Policy-validated command; runtime capabilities remain authoritative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    correlation_id: UUID
    device_id: str = Field(min_length=1, max_length=100)
    action: ActionName
    value: CommandValue | None = None

    @field_validator("action")
    @classmethod
    def reject_unlock(cls, value: str) -> str:
        if value == "unlock":
            raise ValueError("unlock requires external approval")
        return value
