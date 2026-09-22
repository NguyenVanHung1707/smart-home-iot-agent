"""Small in-memory conversation context for the single-process Hub runtime."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Literal

MissingSlot = Literal["device", "action", "value"]
MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class PendingClarification:
    query: str
    missing_slot: MissingSlot


@dataclass(frozen=True)
class ConversationSnapshot:
    messages: tuple[tuple[MessageRole, str], ...] = ()
    last_device_ids: tuple[str, ...] = ()
    pending: PendingClarification | None = None


@dataclass
class _Conversation:
    expires_at: float
    messages: deque[tuple[MessageRole, str]] = field(default_factory=deque)
    last_device_ids: tuple[str, ...] = ()
    pending: PendingClarification | None = None
    data_mode: str | None = None


class ConversationStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = 600,
        max_turns: int = 10,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_turns * 2
        self.clock = clock
        self._items: dict[str, _Conversation] = {}
        self._lock = Lock()

    def _session(self, session_id: str, mode: str | None = None) -> _Conversation:
        now = self.clock()
        for expired_id in [key for key, item in self._items.items() if item.expires_at <= now]:
            del self._items[expired_id]
        session = self._items.get(session_id)
        if session is None:
            session = _Conversation(expires_at=now + self.ttl_seconds, data_mode=mode)
            self._items[session_id] = session
        else:
            session.expires_at = now + self.ttl_seconds
            if session.data_mode is not None and mode is not None and session.data_mode != mode:
                session.last_device_ids = ()
                session.pending = None
            if mode is not None:
                session.data_mode = mode
        return session

    def snapshot(self, session_id: str, mode: str | None = None) -> ConversationSnapshot:
        with self._lock:
            session = self._session(session_id, mode=mode)
            return ConversationSnapshot(
                messages=tuple(session.messages),
                last_device_ids=session.last_device_ids,
                pending=session.pending,
            )

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        with self._lock:
            session = self._session(session_id)
            session.messages.extend((("user", user), ("assistant", assistant)))
            while len(session.messages) > self.max_messages:
                session.messages.popleft()

    def set_pending(self, session_id: str, pending: PendingClarification | None, mode: str | None = None) -> None:
        with self._lock:
            self._session(session_id, mode=mode).pending = pending

    def set_last_devices(self, session_id: str, device_ids: tuple[str, ...], mode: str | None = None) -> None:
        with self._lock:
            self._session(session_id, mode=mode).last_device_ids = tuple(dict.fromkeys(device_ids))

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)


# ponytail: process-local context is enough for the simulator; use SQLite or
# Redis when restart persistence or multiple API workers become requirements.
conversations = ConversationStore()
