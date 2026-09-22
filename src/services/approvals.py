"""Small in-memory approval store for sensitive simulator actions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID, uuid4

from src.models.schemas import Approval, DeviceCommand

_APPROVAL_SEAL: Final = object()


@dataclass(frozen=True, slots=True)
class ApprovalCapability:
    approval_id: UUID
    device_id: str
    action: str
    value: Any
    expires_at: datetime
    _seal: object
    mode: str = "simulator"

    @property
    def authentic(self) -> bool:
        return self._seal is _APPROVAL_SEAL


class ApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, Approval] = {}

    def clear(self) -> None:
        self._items.clear()

    def create(
        self,
        device_id: str,
        command: DeviceCommand,
        requested_by: str | None = None,
        mode: str = "simulator",
    ) -> Approval:
        now = datetime.now(UTC)
        item = Approval(
            id=str(uuid4()),
            device_id=device_id,
            command=command,
            requested_by=requested_by,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=2)).isoformat(),
            mode=mode,
        )
        self._items[item.id] = item
        return item

    def list(self, mode: str | None = None) -> list[Approval]:
        now = datetime.now(UTC)
        for item in self._items.values():
            if item.status == "pending" and datetime.fromisoformat(item.expires_at) <= now:
                item.status = "expired"
        if mode is not None:
            norm_mode = "real" if mode.strip().lower() in {"real", "live", "hardware"} else "simulator"
            return [item for item in self._items.values() if item.mode == norm_mode]
        return list(self._items.values())

    def approve(self, approval_id: str, *, now: datetime | None = None) -> ApprovalCapability | None:
        decided_at = now or datetime.now(UTC)
        item = self._items.get(approval_id)
        if item is None or item.status != "pending" or datetime.fromisoformat(item.expires_at) <= decided_at:
            if item is not None and item.status == "pending":
                item.status = "expired"
            return None
        item.status = "approved"
        return ApprovalCapability(
            approval_id=UUID(item.id),
            device_id=item.device_id,
            action=item.command.action,
            value=item.command.value,
            expires_at=datetime.fromisoformat(item.expires_at),
            _seal=_APPROVAL_SEAL,
            mode=item.mode,
        )

    def decide(self, approval_id: str, approved: bool) -> Approval | None:
        self.list()
        item = self._items.get(approval_id)
        if item is None or item.status != "pending":
            return None
        if approved:
            capability = self.approve(approval_id)
            return item if capability is not None else None
        item.status = "rejected"
        return item

    def issue_capability(
        self,
        device_id: str,
        action: str,
        value: Any = None,
        *,
        request_id: UUID | None = None,
        ttl_minutes: float = 2.0,
        mode: str = "simulator",
    ) -> ApprovalCapability:
        now = datetime.now(UTC)
        app_id = request_id if request_id is not None else uuid4()
        return ApprovalCapability(
            approval_id=app_id,
            device_id=device_id,
            action=action,
            value=value,
            expires_at=now + timedelta(minutes=ttl_minutes),
            _seal=_APPROVAL_SEAL,
            mode=mode,
        )


approvals = ApprovalStore()
