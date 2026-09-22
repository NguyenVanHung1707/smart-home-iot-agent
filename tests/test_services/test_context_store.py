from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.models.dialogue import UnresolvedSlot
from src.services.context_store import (
    Clarification,
    ContextStore,
    ContextStoreError,
    ExecutionState,
    RecentTurn,
    VerifiedResult,
)


def _store(path: Path, now: list[datetime], **kwargs: int) -> ContextStore:
    return ContextStore(path, clock=lambda: now[0], **kwargs)


def test_context_is_bounded_by_turn_count_and_token_cap(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store = _store(tmp_path / "context.db", now, max_turns=10, token_cap=12)

    # When
    for index in range(12):
        store.add_turn("browser-session", RecentTurn(user=f"user {index}", assistant=f"reply {index}"))

    # Then
    snapshot = store.load("browser-session")
    assert len(snapshot.recent_turns) == 3
    assert snapshot.recent_turns[0].user == "user 9"
    assert snapshot.recent_turns[-1].assistant == "reply 11"


def test_context_keeps_unique_devices_slots_and_latest_verified_result(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store = _store(tmp_path / "context.db", now)
    slots = (UnresolvedSlot(name="device", reason="ambiguous"),)

    # When
    store.set_last_devices("session", ("lamp", "fan", "lamp"))
    store.set_unresolved_slots("session", slots)
    store.set_verified_result("session", VerifiedResult(correlation_id="old", summary="off"))
    store.set_verified_result("session", VerifiedResult(correlation_id="new", summary="on"))

    # Then
    snapshot = store.load("session")
    assert snapshot.last_device_ids == ("lamp", "fan")
    assert snapshot.unresolved_slots == slots
    assert snapshot.latest_verified_result == VerifiedResult(correlation_id="new", summary="on")


def test_restart_restores_non_expired_clarification(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    first_process = _store(path, now)
    clarification = Clarification(
        prompt="Phòng nào?", unresolved_slots=(UnresolvedSlot(name="device", reason="missing"),)
    )
    first_process.set_pending_clarification("client-key", clarification)

    # When
    restarted = _store(path, now)

    # Then
    assert restarted.load("client-key").pending_clarification == clarification


def test_default_ttl_expires_after_thirty_minutes_and_is_configurable(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    default_store = _store(tmp_path / "default.db", now)
    custom_store = _store(tmp_path / "custom.db", now, ttl_seconds=60)
    default_store.add_turn("default-session", RecentTurn(user="hello", assistant="hi"))
    custom_store.add_turn("custom-session", RecentTurn(user="hello", assistant="hi"))

    # When
    now[0] += timedelta(seconds=61)

    # Then
    assert custom_store.load("custom-session").recent_turns == ()
    now[0] += timedelta(seconds=1740)
    assert default_store.load("default-session").recent_turns == ()


def test_second_live_dispatch_claim_is_rejected_while_executing(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store = _store(tmp_path / "context.db", now)

    # When
    first_claim = store.claim_for_dispatch("session")
    second_claim = store.claim_for_dispatch("session")

    # Then
    assert first_claim
    assert not second_claim
    assert store.load("session").execution_state is ExecutionState.EXECUTING


def test_executing_state_becomes_indeterminate_after_restart_and_cannot_redispatch(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    first_process = _store(path, now)
    first_process.set_execution_state("session", ExecutionState.EXECUTING)

    # When
    restarted = _store(path, now)
    snapshot = restarted.load("session")

    # Then
    assert snapshot.execution_state is ExecutionState.INDETERMINATE
    assert not restarted.claim_for_dispatch("session")


def _row(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT expires_at, recent_turns, last_device_ids, unresolved_slots, pending_clarification, latest_verified_result, execution_state FROM contexts WHERE session_id = ?",
            ("session",),
        ).fetchone()
    assert row is not None
    return tuple(row)


def _corrupt(path: Path, column: str, value: str) -> tuple[str, ...]:
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE contexts SET {column} = ? WHERE session_id = ?", (value, "session"))
    return _row(path)


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("recent_turns", "{bad"),
        ("last_device_ids", "{bad"),
        ("unresolved_slots", "{bad"),
        ("pending_clarification", "{bad"),
        ("latest_verified_result", "{bad"),
        ("execution_state", "unknown"),
    ),
)
@pytest.mark.parametrize(
    "mutate",
    (
        pytest.param(lambda store: store.add_turn("session", RecentTurn(user="next", assistant="reply")), id="turn"),
        pytest.param(lambda store: store.set_last_devices("session", ("lamp",)), id="devices"),
        pytest.param(lambda store: store.set_unresolved_slots("session", ()), id="slots"),
        pytest.param(lambda store: store.set_pending_clarification("session", None), id="clarification"),
        pytest.param(lambda store: store.set_verified_result("session", None), id="result"),
        pytest.param(lambda store: store.set_execution_state("session", ExecutionState.FAILED), id="state"),
    ),
)
def test_mutation_rejects_corrupt_persisted_context_without_changing_row(
    tmp_path: Path,
    column: str,
    value: str,
    mutate: Callable[[ContextStore], None],
) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    store = _store(path, now)
    store.add_turn("session", RecentTurn(user="hello", assistant="hi"))
    corrupt_row = _corrupt(path, column, value)

    # When / Then
    with pytest.raises(ContextStoreError):
        mutate(store)
    assert _row(path) == corrupt_row


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("recent_turns", "{bad"),
        ("last_device_ids", "{bad"),
        ("unresolved_slots", "{bad"),
        ("pending_clarification", "{bad"),
        ("latest_verified_result", "{bad"),
        ("execution_state", "unknown"),
    ),
)
def test_claim_rejects_corrupt_persisted_context_without_changing_row(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    store = _store(path, now)
    store.add_turn("session", RecentTurn(user="hello", assistant="hi"))
    corrupt_row = _corrupt(path, column, value)

    # When / Then
    with pytest.raises(ContextStoreError):
        store.claim_for_dispatch("session")
    assert _row(path) == corrupt_row


def test_load_rejects_malformed_json_without_dispatch_side_effects(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    store = _store(path, now)
    store.add_turn("session", RecentTurn(user="hello", assistant="hi"))
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE contexts SET recent_turns = ? WHERE session_id = ?", ("{bad", "session"))

    # When / Then
    with pytest.raises(ContextStoreError):
        store.load("session")
    with pytest.raises(ContextStoreError):
        store.claim_for_dispatch("session")


def test_load_rejects_invalid_execution_state_without_dispatch_side_effects(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    store = _store(path, now)
    store.set_execution_state("session", ExecutionState.IDLE)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE contexts SET execution_state = ? WHERE session_id = ?", ("unknown", "session"))

    # When / Then
    with pytest.raises(ContextStoreError):
        store.load("session")
    with pytest.raises(ContextStoreError):
        store.claim_for_dispatch("session")


def test_corrupt_database_bytes_raise_typed_error_before_dispatch_operations(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "context.db"
    path.write_bytes(b"not a sqlite database")

    # When / Then
    with pytest.raises(ContextStoreError):
        ContextStore(path)


def test_session_id_is_only_storage_key_and_sensitive_data_is_not_in_schema(tmp_path: Path) -> None:
    # Given
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    path = tmp_path / "context.db"
    store = _store(path, now)

    # When
    store.add_turn("attacker-chosen", RecentTurn(user="hello", assistant="hi"))

    # Then
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(contexts)")}
    assert "session_id" in columns
    assert columns.isdisjoint({"user_id", "identity", "pin", "raw_audio", "preferences"})
