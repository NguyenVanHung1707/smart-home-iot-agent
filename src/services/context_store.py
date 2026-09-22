"""Restart-safe, bounded short-term conversation context backed by SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.models.actions import ActionProposalBatch
from src.models.dialogue import UnresolvedSlot

_DEFAULT_TTL_SECONDS: Final = 30 * 60
_DEVICES = TypeAdapter(tuple[str, ...])
_SLOTS = TypeAdapter(tuple[UnresolvedSlot, ...])


class ExecutionState(StrEnum):
    IDLE = "idle"
    EXECUTING = "executing"
    INDETERMINATE = "indeterminate"
    VERIFIED = "verified"
    FAILED = "failed"


class RecentTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user: str = Field(min_length=1, max_length=5000)
    assistant: str = Field(min_length=1, max_length=5000)


_TURNS = TypeAdapter(tuple[RecentTurn, ...])


class ContextStoreError(RuntimeError):
    """Stored context is unavailable or fails validation."""


class Clarification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=1, max_length=5000)
    unresolved_slots: tuple[UnresolvedSlot, ...] = Field(default=(), max_length=32)
    action_batch: ActionProposalBatch | None = None


class VerifiedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=5000)


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    recent_turns: tuple[RecentTurn, ...] = ()
    last_device_ids: tuple[str, ...] = ()
    unresolved_slots: tuple[UnresolvedSlot, ...] = ()
    pending_clarification: Clarification | None = None
    latest_verified_result: VerifiedResult | None = None
    execution_state: ExecutionState = ExecutionState.IDLE


class ContextStore:
    """Persist privacy-minimal context keyed only by caller-supplied session ID."""

    def __init__(
        self,
        path: str | Path,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_turns: int = 10,
        token_cap: int = 4096,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._path = Path(path)
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._token_cap = token_cap
        self._clock = clock
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS contexts (
                        session_id TEXT PRIMARY KEY,
                        expires_at TEXT NOT NULL,
                        recent_turns TEXT NOT NULL DEFAULT '[]',
                        last_device_ids TEXT NOT NULL DEFAULT '[]',
                        unresolved_slots TEXT NOT NULL DEFAULT '[]',
                        pending_clarification TEXT,
                        latest_verified_result TEXT,
                        execution_state TEXT NOT NULL DEFAULT 'idle'
                    )"""
                )
                connection.execute(
                    "UPDATE contexts SET execution_state = ? WHERE execution_state = ?",
                    (ExecutionState.INDETERMINATE, ExecutionState.EXECUTING),
                )
        except sqlite3.DatabaseError as exc:
            raise ContextStoreError("corrupt context database") from exc

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5)

    def _expiry(self) -> str:
        return (self._clock() + self._ttl).isoformat()

    def _ensure(self, connection: sqlite3.Connection, session_id: str) -> None:
        connection.execute("DELETE FROM contexts WHERE expires_at <= ?", (self._clock().isoformat(),))
        connection.execute(
            "INSERT INTO contexts (session_id, expires_at) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET expires_at=excluded.expires_at",
            (session_id, self._expiry()),
        )

    @staticmethod
    def _snapshot(row: sqlite3.Row | tuple[str | None, ...]) -> ContextSnapshot:
        pending = Clarification.model_validate_json(row[3]) if row[3] is not None else None
        result = VerifiedResult.model_validate_json(row[4]) if row[4] is not None else None
        return ContextSnapshot(
            recent_turns=_TURNS.validate_json(row[0]),
            last_device_ids=_DEVICES.validate_json(row[1]),
            unresolved_slots=_SLOTS.validate_json(row[2]),
            pending_clarification=pending,
            latest_verified_result=result,
            execution_state=ExecutionState(row[5]),
        )

    def _validate_existing(self, connection: sqlite3.Connection, session_id: str) -> None:
        row = connection.execute(
            "SELECT recent_turns, last_device_ids, unresolved_slots, pending_clarification, latest_verified_result, execution_state FROM contexts WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is not None:
            self._snapshot(row)

    def load(self, session_id: str) -> ContextSnapshot:
        try:
            with self._connect() as connection:
                self._validate_existing(connection, session_id)
                self._ensure(connection, session_id)
                row = connection.execute(
                    "SELECT recent_turns, last_device_ids, unresolved_slots, pending_clarification, latest_verified_result, execution_state FROM contexts WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if row is None:
                    raise ContextStoreError("context row missing")
                return self._snapshot(row)
        except ContextStoreError:
            raise
        except (sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise ContextStoreError("corrupt context") from exc

    def add_turn(self, session_id: str, turn: RecentTurn) -> None:
        turns = [*self.load(session_id).recent_turns, turn][-self._max_turns :]
        while turns and sum(len(item.user.split()) + len(item.assistant.split()) for item in turns) > self._token_cap:
            turns.pop(0)
        self._update(session_id, "recent_turns", _TURNS.dump_json(tuple(turns)).decode())

    def set_last_devices(self, session_id: str, device_ids: tuple[str, ...]) -> None:
        unique = tuple(dict.fromkeys(device_ids))
        self._update(session_id, "last_device_ids", _DEVICES.dump_json(unique).decode())

    def set_unresolved_slots(self, session_id: str, slots: tuple[UnresolvedSlot, ...]) -> None:
        self._update(session_id, "unresolved_slots", _SLOTS.dump_json(slots).decode())

    def set_pending_clarification(self, session_id: str, clarification: Clarification | None) -> None:
        payload = clarification.model_dump_json() if clarification is not None else None
        self._update(session_id, "pending_clarification", payload)

    def set_verified_result(self, session_id: str, result: VerifiedResult | None) -> None:
        payload = result.model_dump_json() if result is not None else None
        self._update(session_id, "latest_verified_result", payload)

    def set_execution_state(self, session_id: str, state: ExecutionState) -> None:
        self._update(session_id, "execution_state", state)

    def claim_for_dispatch(self, session_id: str) -> bool:
        try:
            with self._connect() as connection:
                self._validate_existing(connection, session_id)
                self._ensure(connection, session_id)
                cursor = connection.execute(
                    "UPDATE contexts SET execution_state = ?, expires_at = ? WHERE session_id = ? AND execution_state = ?",
                    (ExecutionState.EXECUTING, self._expiry(), session_id, ExecutionState.IDLE),
                )
                return cursor.rowcount == 1
        except (sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise ContextStoreError("corrupt context") from exc

    def _update(self, session_id: str, column: str, value: str | ExecutionState | None) -> None:
        allowed: Final = {
            "recent_turns",
            "last_device_ids",
            "unresolved_slots",
            "pending_clarification",
            "latest_verified_result",
            "execution_state",
        }
        assert column in allowed
        try:
            with self._connect() as connection:
                self._validate_existing(connection, session_id)
                self._ensure(connection, session_id)
                connection.execute(
                    f"UPDATE contexts SET {column} = ?, expires_at = ? WHERE session_id = ?",
                    (value, self._expiry(), session_id),
                )
        except (sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise ContextStoreError("corrupt context") from exc
