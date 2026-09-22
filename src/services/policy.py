"""Deterministic authorization policy for validated device commands."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from src.models.actions import ActionName, ValidatedCommand

POLICY_VERSION: Final = "1.0"


class PolicyDecisionKind(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_EXTERNAL_APPROVAL = "REQUIRE_EXTERNAL_APPROVAL"


@dataclass(frozen=True, slots=True)
class DeviceFacts:
    device_id: str
    kind: str
    online: bool
    capabilities: tuple[ActionName, ...]


@dataclass(frozen=True, slots=True)
class SystemFacts:
    control_available: bool
    chat_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    kind: PolicyDecisionKind
    reason: str
    version: str = POLICY_VERSION


@dataclass(frozen=True, slots=True)
class InvalidPolicyCommandError(TypeError):
    received_type: type

    def __str__(self) -> str:
        return f"policy requires ValidatedCommand, received {self.received_type.__name__}"


def evaluate_policy(
    command: ValidatedCommand,
    device: DeviceFacts,
    system: SystemFacts,
) -> PolicyDecision:
    """Return fail-closed policy decision from typed command and authoritative facts."""
    if not isinstance(command, ValidatedCommand):
        raise InvalidPolicyCommandError(received_type=type(command))

    if command.device_id != device.device_id:
        return PolicyDecision(PolicyDecisionKind.DENY, "device_mismatch")
    if not system.control_available:
        return PolicyDecision(PolicyDecisionKind.DENY, "control_unavailable")
    if not device.online:
        return PolicyDecision(PolicyDecisionKind.DENY, "device_offline")
    if command.action not in device.capabilities:
        return PolicyDecision(PolicyDecisionKind.DENY, "unsupported_capability")

    if command.action == "unlock" or device.kind in {"security"}:
        return PolicyDecision(
            PolicyDecisionKind.REQUIRE_EXTERNAL_APPROVAL,
            "sensitive_security_action",
        )

    match device.kind:
        case "light" | "fan" | "aircon" | "blind" | "speaker" | "display" | "lock":
            return PolicyDecision(PolicyDecisionKind.ALLOW, "low_risk_control")
        case "sensor":
            return PolicyDecision(PolicyDecisionKind.DENY, "sensor_mutation_forbidden")
        case _:
            return PolicyDecision(PolicyDecisionKind.DENY, "device_kind_not_permitted")
