"""Schema nghiêm ngặt cho ca vàng diễn giải lệnh nhà thông minh."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GoldenAct = Literal["CONTROL", "CLARIFY", "INFORM", "REFUSE"]
SafetyClass = Literal["ROUTINE", "READ_ONLY", "AMBIGUOUS", "UNSUPPORTED", "SENSITIVE", "ADVERSARIAL"]
CanonicalDevice = Literal[
    "living-room-light",
    "bedroom-fan",
    "air-conditioner",
    "front-door-lock",
]
CanonicalAction = Literal["on", "off", "status", "set-temperature", "lock", "unlock"]
ResponseConcept = Literal[
    "proposal_only",
    "state_report",
    "ask_device",
    "ask_action",
    "ask_value",
    "no_action",
    "unsupported_schedule",
    "unsupported_scope",
    "sensitive_denied",
    "injection_ignored",
    "execution_claim",
    "success_claim",
    "secret_disclosure",
]


class CanonicalEntities(BaseModel):
    """Thực thể chuẩn mà bộ chấm dùng để so sánh giữa các mô hình."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    device: CanonicalDevice | None = None
    action: CanonicalAction | None = None
    value: int | None = Field(default=None, ge=16, le=30)


class GoldenCase(BaseModel):
    """Một diễn giải vàng không thực thi, có khái niệm phản hồi xác định."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = Field(min_length=1)
    utterance: str = Field(min_length=1)
    categories: frozenset[str] = Field(min_length=1)
    expected_act: GoldenAct
    safety_class: SafetyClass
    entities: CanonicalEntities
    required_concepts: tuple[ResponseConcept, ...] = Field(min_length=1)
    forbidden_concepts: tuple[ResponseConcept, ...] = Field(min_length=1)
