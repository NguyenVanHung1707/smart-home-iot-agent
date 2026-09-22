from __future__ import annotations

from enum import StrEnum
from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State schema cho Homing Hub LangGraph agent.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.

    Key fields:
        messages: Chat history — ``add_messages`` reducer tự động
                  append tin nhắn mới thay vì overwrite.
        query:    Raw user input (cho fallback / voice endpoint).
        response: Câu trả lời cuối cùng trả về API caller.
    """

    # ── Conversation ─────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Legacy / fallback ────────────────────────────────────────────────
    query: str
    session_id: str
    data_mode: str
    context: str
    analysis: str

    # ── Output ───────────────────────────────────────────────────────────
    response: str
    error: str
    metadata: dict
    fallback_required: bool


class AgentStage(StrEnum):
    LOAD_CONTEXT = "load_context"
    INTERPRET = "interpret"
    RESOLVE = "resolve"
    VALIDATE = "validate"
    POLICY = "policy"
    CLARIFY = "clarify"
    EXECUTE = "execute"
    VERIFY = "verify"
    RESPOND = "respond"
    PERSIST_TRACE = "persist_trace"


class InterpretationStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    REPAIR_REQUIRED = "repair_required"
    INVALID = "invalid"
    GENERIC_FALLBACK = "generic_fallback"


class DispatchStatus(StrEnum):
    NOT_DISPATCHED = "not_dispatched"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    TIMED_OUT = "timed_out"
    VERIFICATION_MISMATCH = "verification_mismatch"


class AgentOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    CLARIFICATION_REQUIRED = "clarification_required"
    INFORMATIONAL = "informational"


class TypedAgentState(TypedDict, total=False):
    """Typed control-plane state; stubs preserve authority boundaries."""

    request_id: UUID
    query: str
    interpretation_status: InterpretationStatus
    dispatch_status: DispatchStatus
    interpretation_attempts: int
    repair_attempts: int
    stage_trace: list[AgentStage]
    outcome: AgentOutcome
    response: str
    error: str
