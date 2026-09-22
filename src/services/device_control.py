"""One command path for HTTP, voice and agent actions."""

from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from src.models.actions import ValidatedCommand
from src.models.schemas import Device
from src.services.approvals import ApprovalCapability
from src.services.executor import ExecutionStatus, Executor, InMemoryExecutionLedger
from src.services.mqtt import get_mqtt_hub

_LEDGER = InMemoryExecutionLedger()


def control_device(
    device_id: str,
    action: str,
    value: Any = None,
    *,
    approved_sensitive: bool = False,
    approval: ApprovalCapability | None = None,
    command_id: str | UUID | None = None,
    registry: Any | None = None,
    mode: str | None = None,
) -> tuple[Device | None, str | None]:
    # mqtt imports the registry, so this direction must stay lazy.
    import src.services.devices as devices_mod
    from src.services.approvals import approvals

    if mode is None:
        if registry is not None and getattr(registry, "mode", None) in {"real", "simulator"}:
            mode = registry.mode
        else:
            mode = devices_mod.get_active_data_mode()
    mode = "real" if str(mode or "").strip().lower() in {"real", "live", "hardware"} else "simulator"

    if registry is not None:
        active_registry = registry
    else:
        active_registry = devices_mod.get_registry(mode)
        if active_registry.get(device_id) is None:
            for candidate in devices_mod.list_all_active_registries():
                if candidate.get(device_id) is not None:
                    active_registry = candidate
                    cand_mode = getattr(candidate, "mode", None)
                    if cand_mode in {"real", "simulator"}:
                        mode = cand_mode
                    break

    identity = command_id or (approval.approval_id if approval is not None else uuid4())
    try:
        request_id = identity if isinstance(identity, UUID) else UUID(str(identity))
    except (ValueError, TypeError):
        request_id = uuid5(NAMESPACE_URL, str(identity))

    if approved_sensitive and approval is None:
        approval = approvals.issue_capability(
            device_id=device_id,
            action=action,
            value=value,
            request_id=request_id,
            mode=mode,
        )

    _, validation_error = active_registry.validate_command(
        device_id,
        action,
        value,
        approved_sensitive=approved_sensitive or (approval is not None),
    )
    if validation_error is not None:
        return None, validation_error
    try:
        command = ValidatedCommand(
            request_id=request_id,
            correlation_id=request_id,
            device_id=device_id,
            action=action,
            value=value,
        )
    except (TypeError, ValueError):
        if approval is None:
            _, validation_error = active_registry.validate_command(device_id, action, value)
            return None, validation_error or "unsupported_action"
        command = ValidatedCommand.model_construct(
            request_id=request_id,
            correlation_id=request_id,
            device_id=device_id,
            action=action,
            value=value,
        )
    result = Executor(active_registry, get_mqtt_hub(), _LEDGER, mode=mode).execute(command, approval=approval)
    match result.status:
        case ExecutionStatus.SUCCEEDED:
            return result.device, None
        case ExecutionStatus.NOT_DISPATCHED | ExecutionStatus.FAILED | ExecutionStatus.INDETERMINATE:
            return None, result.reason
