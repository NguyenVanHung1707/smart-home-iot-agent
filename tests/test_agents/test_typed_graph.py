from uuid import uuid4

import pytest

from src.agents.graph import build_typed_graph
from src.agents.state import (
    AgentOutcome,
    AgentStage,
    DispatchStatus,
    InterpretationStatus,
    TypedAgentState,
)


async def _run(**overrides: object) -> TypedAgentState:
    request_id = uuid4()
    initial: TypedAgentState = {
        "request_id": request_id,
        "query": "bật đèn phòng khách",
        "interpretation_status": InterpretationStatus.READY,
        "dispatch_status": DispatchStatus.NOT_DISPATCHED,
        **overrides,
    }
    return await build_typed_graph().ainvoke(initial)


@pytest.mark.asyncio
async def test_happy_path_crosses_every_authority_boundary_before_execute() -> None:
    # Given / When
    result = await _run()

    # Then
    assert result["stage_trace"] == [
        AgentStage.LOAD_CONTEXT,
        AgentStage.INTERPRET,
        AgentStage.RESOLVE,
        AgentStage.VALIDATE,
        AgentStage.POLICY,
        AgentStage.EXECUTE,
        AgentStage.VERIFY,
        AgentStage.RESPOND,
        AgentStage.PERSIST_TRACE,
    ]
    assert result["outcome"] is AgentOutcome.INDETERMINATE


@pytest.mark.asyncio
async def test_clarification_never_reaches_executor() -> None:
    # Given / When
    result = await _run(interpretation_status=InterpretationStatus.NEEDS_CLARIFICATION)

    # Then
    assert result["stage_trace"] == [
        AgentStage.LOAD_CONTEXT,
        AgentStage.INTERPRET,
        AgentStage.RESOLVE,
        AgentStage.CLARIFY,
        AgentStage.RESPOND,
        AgentStage.PERSIST_TRACE,
    ]
    assert AgentStage.EXECUTE not in result["stage_trace"]


@pytest.mark.asyncio
async def test_pre_dispatch_error_fails_closed() -> None:
    # Given / When
    result = await _run(interpretation_status=InterpretationStatus.INVALID)

    # Then
    assert result["outcome"] is AgentOutcome.FAILED
    assert result["dispatch_status"] is DispatchStatus.NOT_DISPATCHED
    assert AgentStage.EXECUTE not in result["stage_trace"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [DispatchStatus.TIMED_OUT, DispatchStatus.VERIFICATION_MISMATCH])
async def test_post_dispatch_uncertainty_is_indeterminate(status: DispatchStatus) -> None:
    # Given / When
    result = await _run(dispatch_status=status)

    # Then
    assert result["outcome"] is AgentOutcome.INDETERMINATE
    assert result["stage_trace"].count(AgentStage.EXECUTE) == 1
    assert result["stage_trace"].count(AgentStage.VERIFY) == 1


@pytest.mark.asyncio
async def test_interpretation_and_repair_are_each_bounded_to_one_attempt() -> None:
    # Given / When
    result = await _run(interpretation_status=InterpretationStatus.REPAIR_REQUIRED)

    # Then
    assert result["interpretation_attempts"] == 1
    assert result["repair_attempts"] == 1
    assert result["outcome"] is AgentOutcome.FAILED


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed_status", [None, "garbage", 7])
async def test_malformed_interpretation_status_fails_closed_without_side_effects(
    malformed_status: str | int | None,
) -> None:
    # Given / When
    result = await _run(interpretation_status=malformed_status)

    # Then
    assert result["outcome"] is AgentOutcome.FAILED
    assert result["stage_trace"] == [
        AgentStage.LOAD_CONTEXT,
        AgentStage.INTERPRET,
        AgentStage.RESPOND,
        AgentStage.PERSIST_TRACE,
    ]
    assert AgentStage.POLICY not in result["stage_trace"]
    assert AgentStage.EXECUTE not in result["stage_trace"]
    assert result["dispatch_status"] is DispatchStatus.NOT_DISPATCHED


@pytest.mark.asyncio
async def test_generic_fallback_cannot_reenter_control_graph() -> None:
    # Given / When
    result = await _run(interpretation_status=InterpretationStatus.GENERIC_FALLBACK)

    # Then
    assert result["stage_trace"] == [
        AgentStage.LOAD_CONTEXT,
        AgentStage.INTERPRET,
        AgentStage.RESPOND,
        AgentStage.PERSIST_TRACE,
    ]
    assert result["stage_trace"].count(AgentStage.INTERPRET) == 1
    assert AgentStage.EXECUTE not in result["stage_trace"]
