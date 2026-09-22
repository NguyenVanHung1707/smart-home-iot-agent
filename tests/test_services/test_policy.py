from uuid import uuid4

import pytest

from src.models.actions import ValidatedCommand
from src.services.policy import (
    POLICY_VERSION,
    DeviceFacts,
    InvalidPolicyCommandError,
    PolicyDecisionKind,
    SystemFacts,
    evaluate_policy,
)


class ForgedCommand:
    device_id = "living-light"
    action = "on"


def _command(*, device_id: str = "living-light", action: str = "on") -> ValidatedCommand:
    return ValidatedCommand.model_construct(
        request_id=uuid4(),
        correlation_id=uuid4(),
        device_id=device_id,
        action=action,
        value=None,
    )


@pytest.mark.parametrize(
    ("kind", "action"),
    [
        ("light", "on"),
        ("fan", "toggle"),
        ("aircon", "set"),
        ("blind", "open"),
        ("speaker", "play"),
        ("display", "set"),
        ("lock", "lock"),
    ],
)
def test_allows_valid_low_risk_control_when_facts_match(kind: str, action: str) -> None:
    # Given
    command = _command(device_id=f"{kind}-1", action=action)
    device = DeviceFacts(
        device_id=f"{kind}-1",
        kind=kind,
        online=True,
        capabilities=("on", "off", "toggle", "set", "open", "close", "play", "pause", "stop", "lock"),
    )

    # When
    decision = evaluate_policy(command, device, SystemFacts(control_available=True))

    # Then
    assert decision.kind is PolicyDecisionKind.ALLOW
    assert decision.reason == "low_risk_control"
    assert decision.version == POLICY_VERSION


@pytest.mark.parametrize(
    ("device", "system", "expected_reason"),
    [
        (
            DeviceFacts(
                device_id="living-light",
                kind="light",
                online=False,
                capabilities=("on",),
            ),
            SystemFacts(control_available=True),
            "device_offline",
        ),
        (
            DeviceFacts(
                device_id="living-light",
                kind="light",
                online=True,
                capabilities=("off",),
            ),
            SystemFacts(control_available=True),
            "unsupported_capability",
        ),
        (
            DeviceFacts(
                device_id="other-light",
                kind="light",
                online=True,
                capabilities=("on",),
            ),
            SystemFacts(control_available=True),
            "device_mismatch",
        ),
        (
            DeviceFacts(
                device_id="living-light",
                kind="light",
                online=True,
                capabilities=("on",),
            ),
            SystemFacts(control_available=False),
            "control_unavailable",
        ),
    ],
)
def test_denies_invalid_runtime_or_cross_capability_facts(
    device: DeviceFacts,
    system: SystemFacts,
    expected_reason: str,
) -> None:
    # Given
    command = _command()

    # When
    decision = evaluate_policy(command, device, system)

    # Then
    assert decision.kind is PolicyDecisionKind.DENY
    assert decision.reason == expected_reason


@pytest.mark.parametrize(
    ("kind", "action", "expected_kind", "expected_reason"),
    [
        ("lock", "unlock", PolicyDecisionKind.REQUIRE_EXTERNAL_APPROVAL, "sensitive_security_action"),
        ("security", "on", PolicyDecisionKind.REQUIRE_EXTERNAL_APPROVAL, "sensitive_security_action"),
        ("sensor", "set", PolicyDecisionKind.DENY, "sensor_mutation_forbidden"),
        ("unknown_device", "on", PolicyDecisionKind.DENY, "device_kind_not_permitted"),
    ],
)
def test_sensitive_sensor_and_non_allowlisted_devices_fail_closed(
    kind: str,
    action: str,
    expected_kind: PolicyDecisionKind,
    expected_reason: str,
) -> None:
    # Given
    command = _command(device_id=f"{kind}-1", action=action)
    device = DeviceFacts(
        device_id=f"{kind}-1",
        kind=kind,
        online=True,
        capabilities=(action,),
    )

    # When
    decision = evaluate_policy(command, device, SystemFacts(control_available=True))

    # Then
    assert decision.kind is expected_kind
    assert decision.reason == expected_reason


@pytest.mark.parametrize(
    "forged_command",
    [
        {"device_id": "living-light", "action": "on"},
        ForgedCommand(),
    ],
)
def test_rejects_non_validated_command_before_policy_decision(forged_command: ForgedCommand) -> None:
    # Given
    device = DeviceFacts(
        device_id="living-light",
        kind="light",
        online=True,
        capabilities=("on",),
    )

    # When / Then
    with pytest.raises(InvalidPolicyCommandError):
        evaluate_policy(forged_command, device, SystemFacts(control_available=True))


def test_chat_confirmation_cannot_convert_sensitive_action_to_allow() -> None:
    # Given
    command = _command(device_id="entry-lock", action="unlock")
    device = DeviceFacts(
        device_id="entry-lock",
        kind="lock",
        online=True,
        capabilities=("unlock",),
    )
    system = SystemFacts(control_available=True, chat_confirmed=True)

    # When
    decision = evaluate_policy(command, device, system)

    # Then
    assert decision.kind is PolicyDecisionKind.REQUIRE_EXTERNAL_APPROVAL
    assert decision.reason == "sensitive_security_action"
