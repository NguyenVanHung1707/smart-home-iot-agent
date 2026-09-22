"""Canonical authorization and idempotent device-mutation boundary."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import UUID

from src.models.actions import ValidatedCommand
from src.models.schemas import Device
from src.services.mqtt import CommandVerification, VerificationStatus
from src.services.policy import (
    DeviceFacts,
    PolicyDecision,
    PolicyDecisionKind,
    SystemFacts,
    evaluate_policy,
)


class ExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    NOT_DISPATCHED = "NOT_DISPATCHED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    command_id: UUID
    command_hash: str
    status: ExecutionStatus
    reason: str
    device: Device | None = None


@dataclass(frozen=True, slots=True)
class InvalidExecutionInputError(TypeError):
    received_type: type

    def __str__(self) -> str:
        return f"executor requires ValidatedCommand and internal authority, received {self.received_type.__name__}"


class Registry(Protocol):
    def get(self, device_id: str): ...

    def validate_command(self, device_id: str, action: str, value=None): ...

    def capabilities(self, device): ...


class Transport(Protocol):
    def command(self, device_id: str, action: str, value=None) -> CommandVerification: ...


class SensitiveApproval(Protocol):
    approval_id: UUID
    device_id: str
    action: str
    value: object
    expires_at: datetime

    @property
    def authentic(self) -> bool: ...


class ExecutionLedger(Protocol):
    def claim(self, command_id: UUID, command_hash: str) -> ExecutionResult | None: ...

    def finish(self, result: ExecutionResult) -> None: ...


class InMemoryExecutionLedger:
    """Process-durable ledger for tests and explicitly ephemeral deployments."""

    def __init__(self) -> None:
        self._items: dict[UUID, tuple[str, ExecutionResult | None]] = {}
        self._lock = Lock()

    def claim(self, command_id: UUID, command_hash: str) -> ExecutionResult | None:
        with self._lock:
            existing = self._items.get(command_id)
            if existing is None:
                self._items[command_id] = (command_hash, None)
                return None
            prior_hash, result = existing
            if prior_hash != command_hash:
                return ExecutionResult(
                    command_id, command_hash, ExecutionStatus.NOT_DISPATCHED, "command_hash_mismatch"
                )
            return result or ExecutionResult(
                command_id, command_hash, ExecutionStatus.INDETERMINATE, "dispatch_in_progress"
            )

    def finish(self, result: ExecutionResult) -> None:
        with self._lock:
            self._items[result.command_id] = (result.command_hash, result)


class SqliteExecutionLedger:
    """SQLite-backed ledger retaining terminal outcomes across restarts."""

    def __init__(self, path: Path) -> None:
        self._path = path
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS executions (command_id TEXT PRIMARY KEY, command_hash TEXT NOT NULL, result TEXT)"
            )

    def claim(self, command_id: UUID, command_hash: str) -> ExecutionResult | None:
        with sqlite3.connect(self._path, isolation_level="IMMEDIATE") as connection:
            row = connection.execute(
                "SELECT command_hash, result FROM executions WHERE command_id = ?", (str(command_id),)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO executions(command_id, command_hash, result) VALUES (?, ?, NULL)",
                    (str(command_id), command_hash),
                )
                return None
            prior_hash, payload = row
        if prior_hash != command_hash:
            return ExecutionResult(command_id, command_hash, ExecutionStatus.NOT_DISPATCHED, "command_hash_mismatch")
        if payload is None:
            return ExecutionResult(command_id, command_hash, ExecutionStatus.INDETERMINATE, "dispatch_in_progress")
        data = json.loads(payload)
        device = Device.model_validate(data["device"]) if data["device"] is not None else None
        return ExecutionResult(command_id, command_hash, ExecutionStatus(data["status"]), data["reason"], device)

    def finish(self, result: ExecutionResult) -> None:
        payload = json.dumps(
            {
                "status": result.status,
                "reason": result.reason,
                "device": result.device.model_dump(mode="json") if result.device else None,
            },
            separators=(",", ":"),
        )
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "UPDATE executions SET result = ? WHERE command_id = ? AND command_hash = ?",
                (payload, str(result.command_id), result.command_hash),
            )


class _ExecutionAuthority:
    __slots__ = ("decision",)

    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision


class Executor:
    def __init__(
        self,
        registry: Registry,
        transport: Transport,
        ledger: ExecutionLedger,
        *,
        mode: str | None = None,
    ) -> None:
        self._registry = registry
        self._transport = transport
        self._ledger = ledger
        self._mode = mode

    def execute(
        self,
        command: ValidatedCommand,
        authority: _ExecutionAuthority | None = None,
        *,
        approval: SensitiveApproval | None = None,
    ) -> ExecutionResult:
        if not isinstance(command, ValidatedCommand) or authority is not None:
            raise InvalidExecutionInputError(received_type=type(command if authority is None else authority))
        command_hash = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
        if approval is not None and approval.expires_at <= datetime.now(UTC):
            return ExecutionResult(
                command.request_id,
                command_hash,
                ExecutionStatus.NOT_DISPATCHED,
                "approval_expired",
            )
        prior = self._ledger.claim(command.request_id, command_hash)
        if prior is not None:
            return prior

        sensitive = approval is not None
        if sensitive and (
            not approval.authentic
            or approval.approval_id != command.request_id
            or approval.device_id != command.device_id
            or approval.action != command.action
            or approval.value != command.value
        ):
            return self._finish(command, command_hash, ExecutionStatus.NOT_DISPATCHED, "approval_command_mismatch")
        device, validation_error = self._registry.validate_command(
            command.device_id,
            command.action,
            command.value,
            approved_sensitive=sensitive,
        )
        if validation_error is not None or device is None:
            return self._finish(command, command_hash, ExecutionStatus.NOT_DISPATCHED, validation_error or "not_found")
        listed_capabilities = tuple(self._registry.capabilities(device)["actions"])
        capabilities = (*listed_capabilities, command.action) if sensitive else listed_capabilities
        decision = evaluate_policy(
            command,
            DeviceFacts(device.id, device.kind, device.online, capabilities),
            SystemFacts(control_available=True),
        )
        authority = _ExecutionAuthority(decision)
        approved_by_capability = sensitive and authority.decision.kind is PolicyDecisionKind.REQUIRE_EXTERNAL_APPROVAL
        if authority.decision.kind is not PolicyDecisionKind.ALLOW and not approved_by_capability:
            return self._finish(command, command_hash, ExecutionStatus.NOT_DISPATCHED, authority.decision.reason)

        transport_command = (
            getattr(self._transport, "authorized_command", self._transport.command)
            if sensitive
            else self._transport.command
        )
        try:
            if self._mode:
                verification = transport_command(command.device_id, command.action, command.value, mode=self._mode)
            else:
                verification = transport_command(command.device_id, command.action, command.value)
        except TypeError:
            verification = transport_command(command.device_id, command.action, command.value)
        match verification:
            case CommandVerification():
                pass
            case (data, error):
                verification = (
                    CommandVerification(
                        VerificationStatus.INDETERMINATE if error == "timeout" else VerificationStatus.FAILED,
                        error or "transport_failed",
                    )
                    if error is not None or data is None
                    else CommandVerification(
                        VerificationStatus.STATE_VERIFIED,
                        "state_verified",
                        Device.model_validate(data),
                    )
                )
        match verification.status:
            case VerificationStatus.STATE_VERIFIED:
                if verification.device is None:
                    return self._finish(command, command_hash, ExecutionStatus.FAILED, "transport_failed")
                return self._finish(
                    command,
                    command_hash,
                    ExecutionStatus.SUCCEEDED,
                    "state_verified",
                    verification.device,
                )
            case VerificationStatus.INDETERMINATE:
                return self._finish(command, command_hash, ExecutionStatus.INDETERMINATE, verification.reason)
            case VerificationStatus.FAILED:
                return self._finish(command, command_hash, ExecutionStatus.FAILED, verification.reason)

    def _finish(
        self,
        command: ValidatedCommand,
        command_hash: str,
        status: ExecutionStatus,
        reason: str,
        device: Device | None = None,
    ) -> ExecutionResult:
        result = ExecutionResult(command.request_id, command_hash, status, reason, device)
        self._ledger.finish(result)
        return result
