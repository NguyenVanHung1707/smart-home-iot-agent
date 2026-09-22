from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictRequest):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhan tu nguoi dung")
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
        description="Opaque conversation context key; not an authentication token",
    )


class ChatResponse(BaseModel):
    response: str
    analysis: str = ""
    session_id: str


Role = Literal["ADMIN", "MEMBER"]


class UserPublic(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    locked: bool
    created_at: str


class LoginRequest(StrictRequest):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RefreshRequest(StrictRequest):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class CreateUserRequest(StrictRequest):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: Role = "MEMBER"


class UpdateUserRequest(StrictRequest):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    locked: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class Device(BaseModel):
    id: str
    name: str
    room: str
    kind: str
    online: bool = True
    state: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class DeviceCommand(StrictRequest):
    action: str = Field(..., min_length=1, max_length=64)
    value: Any | None = None


class Approval(BaseModel):
    id: str
    device_id: str
    command: DeviceCommand
    requested_by: str | None = None
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    created_at: str
    expires_at: str
    mode: str = "simulator"


class SimulatorFault(StrictRequest):
    mode: Literal["none", "offline", "timeout", "error"] = "none"


class VoiceRequest(StrictRequest):
    transcript: str = Field(..., min_length=1, max_length=1000)
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    language: str
    audio_duration_ms: int
    stt_latency_ms: int
    model: str
    vad_applied: bool


class VoiceSynthesisRequest(StrictRequest):
    text: str = Field(..., min_length=1, max_length=5000)


class RAGQuery(StrictRequest):
    query: str = Field(..., min_length=1, max_length=2000)


class CreateDeviceRequest(StrictRequest):
    id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    room: str = Field(..., min_length=1, max_length=100)
    kind: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    state: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class UpdateDeviceRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    room: str | None = Field(default=None, min_length=1, max_length=100)
    state: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None


class DiscoveredDevice(BaseModel):
    device_id: str
    name: str
    room: str = "Chưa phân loại"
    kind: str = "light"
    state: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    discovered_at: str


class PairDeviceRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    room: str | None = Field(default=None, min_length=1, max_length=100)


class RenameRoomRequest(StrictRequest):
    old_name: str = Field(..., min_length=1, max_length=100)
    new_name: str = Field(..., min_length=1, max_length=100)
