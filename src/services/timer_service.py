"""In-memory delay and countdown timer service for smart home device actions."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from src.services.device_control import control_device

logger = logging.getLogger(__name__)


@dataclass
class TimerItem:
    id: str
    device_id: str
    device_name: str
    room: str
    action: str
    value: dict[str, Any] | None
    duration_seconds: float
    created_at: str
    execute_at: str
    status: str  # "pending", "completed", "cancelled", "failed"
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimerManager:
    def __init__(self) -> None:
        self._timers: dict[str, TimerItem] = {}
        self._threads: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Cancel all active timers and clear memory (used for tests/shutdown)."""
        with self._lock:
            for t in self._threads.values():
                t.cancel()
            self._threads.clear()
            self._timers.clear()

    def _execute_callback(self, timer_id: str) -> None:
        item = None
        with self._lock:
            item = self._timers.get(timer_id)
            if not item or item.status != "pending":
                return
            self._threads.pop(timer_id, None)

        try:
            logger.info("Executing timer %s for device %s (action=%s)", timer_id, item.device_id, item.action)
            _, err = control_device(item.device_id, item.action, item.value)
            with self._lock:
                if err:
                    item.status = "failed"
                    logger.warning("Timer %s execution failed: %s", timer_id, err)
                else:
                    item.status = "completed"
        except Exception as exc:
            logger.exception("Timer %s execution exception: %s", timer_id, exc)
            with self._lock:
                item.status = "failed"

    def create_timer(
        self,
        device_id: str,
        device_name: str,
        room: str,
        action: str,
        duration_seconds: float,
        value: dict[str, Any] | None = None,
        label: str | None = None,
        *,
        timer_id: str | None = None,
    ) -> TimerItem:
        now = datetime.now(UTC)
        execute_dt = now + timedelta(seconds=max(0.1, duration_seconds))
        resolved_timer_id = timer_id or str(uuid4())
        if not resolved_timer_id.strip():
            raise ValueError("timer_id must not be blank")

        item = TimerItem(
            id=resolved_timer_id,
            device_id=device_id,
            device_name=device_name,
            room=room,
            action=action,
            value=value,
            duration_seconds=duration_seconds,
            created_at=now.isoformat(),
            execute_at=execute_dt.isoformat(),
            status="pending",
            label=label,
        )

        with self._lock:
            self._prune_old_timers_unlocked()
            if resolved_timer_id in self._timers:
                raise ValueError("timer_id already exists")
            self._timers[resolved_timer_id] = item
            thread = threading.Timer(duration_seconds, self._execute_callback, args=[resolved_timer_id])
            thread.daemon = True
            self._threads[resolved_timer_id] = thread
            thread.start()

        return item

    def _prune_old_timers_unlocked(self, max_history: int = 50) -> None:
        completed = [
            (tid, item) for tid, item in self._timers.items() if item.status in {"completed", "failed", "cancelled"}
        ]
        if len(completed) > max_history:
            completed.sort(key=lambda x: x[1].created_at)
            for tid, _ in completed[: len(completed) - max_history]:
                self._timers.pop(tid, None)
                self._threads.pop(tid, None)

    def list_timers(self, active_only: bool = False) -> list[TimerItem]:
        with self._lock:
            self._prune_old_timers_unlocked()
            items = list(self._timers.values())
            if active_only:
                return [i for i in items if i.status == "pending"]
            return items

    def cancel_timer(self, timer_id: str) -> bool:
        with self._lock:
            item = self._timers.get(timer_id)
            if not item or item.status != "pending":
                return False
            thread = self._threads.pop(timer_id, None)
            if thread:
                thread.cancel()
            item.status = "cancelled"
            return True

    def cancel_by_device(self, device_id: str) -> int:
        cancelled_count = 0
        with self._lock:
            for item in list(self._timers.values()):
                if item.device_id == device_id and item.status == "pending":
                    thread = self._threads.pop(item.id, None)
                    if thread:
                        thread.cancel()
                    item.status = "cancelled"
                    cancelled_count += 1
        return cancelled_count


timer_service = TimerManager()
