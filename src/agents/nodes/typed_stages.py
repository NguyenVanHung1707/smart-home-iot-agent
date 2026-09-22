"""Typed, side-effect-free stage stubs for the control graph."""

from src.agents.state import (
    AgentOutcome,
    AgentStage,
    DispatchStatus,
    InterpretationStatus,
    TypedAgentState,
)


def _advance(state: TypedAgentState, stage: AgentStage) -> list[AgentStage]:
    return [*state.get("stage_trace", []), stage]


async def load_context(state: TypedAgentState) -> TypedAgentState:
    return {"stage_trace": _advance(state, AgentStage.LOAD_CONTEXT)}


async def interpret(state: TypedAgentState) -> TypedAgentState:
    status = state.get("interpretation_status", InterpretationStatus.INVALID)
    update: TypedAgentState = {
        "stage_trace": _advance(state, AgentStage.INTERPRET),
        "interpretation_attempts": 1,
    }
    if status is InterpretationStatus.REPAIR_REQUIRED:
        update["repair_attempts"] = 1
        update["interpretation_status"] = InterpretationStatus.INVALID
    return update


async def resolve(state: TypedAgentState) -> TypedAgentState:
    return {"stage_trace": _advance(state, AgentStage.RESOLVE)}


async def validate(state: TypedAgentState) -> TypedAgentState:
    return {"stage_trace": _advance(state, AgentStage.VALIDATE)}


async def policy(state: TypedAgentState) -> TypedAgentState:
    """Fail-safe policy seam; real policy is intentionally deferred."""
    return {"stage_trace": _advance(state, AgentStage.POLICY)}


async def clarify(state: TypedAgentState) -> TypedAgentState:
    return {
        "stage_trace": _advance(state, AgentStage.CLARIFY),
        "outcome": AgentOutcome.CLARIFICATION_REQUIRED,
    }


async def execute(state: TypedAgentState) -> TypedAgentState:
    """Record dispatch boundary without implementing an executor."""
    status = state.get("dispatch_status", DispatchStatus.NOT_DISPATCHED)
    return {
        "stage_trace": _advance(state, AgentStage.EXECUTE),
        "dispatch_status": DispatchStatus.DISPATCHED if status is DispatchStatus.NOT_DISPATCHED else status,
    }


async def verify(state: TypedAgentState) -> TypedAgentState:
    """Preserve uncertainty until authoritative MQTT verification exists."""
    return {
        "stage_trace": _advance(state, AgentStage.VERIFY),
        "outcome": AgentOutcome.INDETERMINATE,
    }


async def respond(state: TypedAgentState) -> TypedAgentState:
    outcome = state.get("outcome")
    if outcome is None:
        status = state.get("interpretation_status", InterpretationStatus.INVALID)
        outcome = AgentOutcome.INFORMATIONAL if status is InterpretationStatus.GENERIC_FALLBACK else AgentOutcome.FAILED
    return {"stage_trace": _advance(state, AgentStage.RESPOND), "outcome": outcome}


async def persist_trace(state: TypedAgentState) -> TypedAgentState:
    """Trace persistence seam; durable storage is intentionally deferred."""
    return {"stage_trace": _advance(state, AgentStage.PERSIST_TRACE)}
