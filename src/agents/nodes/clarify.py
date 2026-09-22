"""Typed clarification resume and bounded ordered action orchestration."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.models.actions import ActionProposal, ActionProposalBatch, ValidatedCommand
from src.models.dialogue import UnresolvedSlot
from src.services.context_store import Clarification, ContextStore
from src.services.executor import ExecutionResult, ExecutionStatus


class ProposalValidator(Protocol):
    def validate(self, proposal: ActionProposal) -> ValidatedCommand | str: ...


class CommandExecutor(Protocol):
    def execute(self, command: ValidatedCommand) -> ExecutionResult: ...


class BatchOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class ClarificationStatus(StrEnum):
    REQUIRED = "REQUIRED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class ClarificationReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1, max_length=5000)
    batch: ActionProposalBatch
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class ClarificationResult:
    status: ClarificationStatus


@dataclass(frozen=True, slots=True)
class BatchExecution:
    outcome: BatchOutcome
    actions: tuple[ExecutionResult, ...]


ResumeResult = ClarificationResult | BatchExecution


class ActionFlow:
    """Persist clarification and dispatch fully validated actions in request order."""

    def __init__(self, store: ContextStore, validator: ProposalValidator, executor: CommandExecutor) -> None:
        self._store = store
        self._validator = validator
        self._executor = executor

    def clarify(
        self,
        session_id: str,
        batch: ActionProposalBatch,
        prompt: str,
        slots: tuple[UnresolvedSlot, ...],
    ) -> ClarificationResult:
        self._store.set_pending_clarification(
            session_id,
            Clarification(prompt=prompt, unresolved_slots=slots, action_batch=batch),
        )
        return ClarificationResult(ClarificationStatus.REQUIRED)

    def resume(self, session_id: str, reply: ClarificationReply) -> ResumeResult:
        pending = self._store.load(session_id).pending_clarification
        if pending is None:
            return ClarificationResult(ClarificationStatus.EXPIRED)
        if self._is_cancel(reply.answer):
            self._store.set_pending_clarification(session_id, None)
            return ClarificationResult(ClarificationStatus.CANCELLED)
        if reply.sensitive:
            return ClarificationResult(ClarificationStatus.REJECTED)
        if pending.action_batch != reply.batch:
            return ClarificationResult(ClarificationStatus.REJECTED)
        self._store.set_pending_clarification(session_id, None)
        return self.execute(session_id, reply.batch)

    def execute(self, session_id: str, batch: ActionProposalBatch) -> BatchExecution:
        del session_id
        commands: list[ValidatedCommand] = []
        for proposal in batch.actions:
            validated = self._validator.validate(proposal)
            if isinstance(validated, str):
                return BatchExecution(BatchOutcome.FAILED, ())
            commands.append(validated)

        results: list[ExecutionResult] = []
        for index, command in enumerate(commands):
            result = self._executor.execute(command)
            results.append(result)
            if result.status in {ExecutionStatus.FAILED, ExecutionStatus.INDETERMINATE}:
                results.extend(self._not_dispatched(item, "blocked_by_prior_failure") for item in commands[index + 1 :])
                break
        return BatchExecution(self._outcome(tuple(results)), tuple(results))

    @staticmethod
    def _not_dispatched(command: ValidatedCommand, reason: str) -> ExecutionResult:
        return ExecutionResult(command.request_id, "", ExecutionStatus.NOT_DISPATCHED, reason)

    @staticmethod
    def _outcome(results: tuple[ExecutionResult, ...]) -> BatchOutcome:
        succeeded = sum(result.status is ExecutionStatus.SUCCEEDED for result in results)
        if succeeded == len(results):
            return BatchOutcome.SUCCESS
        if succeeded:
            return BatchOutcome.PARTIAL_SUCCESS
        return BatchOutcome.FAILED

    @staticmethod
    def _is_cancel(answer: str) -> bool:
        decomposed = unicodedata.normalize("NFD", answer.casefold()).replace("đ", "d")
        normalized = "".join(character for character in decomposed if unicodedata.category(character) != "Mn").strip()
        return normalized in {"huy", "bo di", "thoi"}
