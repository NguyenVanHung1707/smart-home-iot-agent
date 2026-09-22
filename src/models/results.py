from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyDecisionKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    correlation_id: UUID | None = None
    decision: PolicyDecisionKind
    reason: str = Field(min_length=1, max_length=512)


TruthState = Literal["proposed", "validated", "dispatched", "acknowledged", "failed"]
