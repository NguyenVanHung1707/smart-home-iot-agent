from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from src.services.devices import registry
from src.services.mqtt import MqttHub, VerificationStatus, _PendingVerification


@dataclass
class FakeClient:
    responder: Callable[[str, str], None] | None
    publish_count: int = 0

    def publish(self, topic: str, payload: str, *, qos: int) -> None:
        self.publish_count += 1
        if self.responder is not None:
            self.responder(topic, payload)


def message(topic: str, payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())


def enabled_hub(monkeypatch: pytest.MonkeyPatch) -> MqttHub:
    hub = MqttHub()
    monkeypatch.setattr(hub.settings, "mqtt_enabled", True)
    monkeypatch.setattr(hub, "start", lambda: None)
    return hub


def test_matching_ack_and_correlated_expected_state_is_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, payload: str) -> None:
        command_id = json.loads(payload)["command_id"]
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/living-light/ack",
                {"device_id": "living-light", "command_id": command_id, "status": "ok"},
            ),
        )
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/living-light/state",
                {"device_id": "living-light", "command_id": command_id, "state": {"power": True}},
            ),
        )

    client = FakeClient(respond)
    hub.client = client

    # When
    result = hub.command("living-light", "on", timeout=0.01)

    # Then
    assert result.status is VerificationStatus.STATE_VERIFIED
    assert result.device is not None
    assert result.device.state["power"] is True
    assert client.publish_count == 1


def test_commandless_state_after_ack_is_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, payload: str) -> None:
        command_id = json.loads(payload)["command_id"]
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/living-light/ack",
                {"device_id": "living-light", "command_id": command_id, "status": "ok"},
            ),
        )
        hub._on_message(
            None,
            None,
            message("homing/devices/living-light/state", {"device_id": "living-light", "state": {"power": True}}),
        )

    hub.client = FakeClient(respond)

    # When
    result = hub.command("living-light", "on", timeout=0.01)

    # Then
    assert result.status is VerificationStatus.STATE_VERIFIED
    assert result.device is not None
    assert result.device.state["power"] is True


def test_commandless_state_before_ack_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, payload: str) -> None:
        command_id = json.loads(payload)["command_id"]
        hub._on_message(
            None,
            None,
            message("homing/devices/living-light/state", {"device_id": "living-light", "state": {"power": True}}),
        )
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/living-light/ack",
                {"device_id": "living-light", "command_id": command_id, "status": "ok"},
            ),
        )

    hub.client = FakeClient(respond)

    # When
    result = hub.command("living-light", "on", timeout=0.001)

    # Then
    assert result.status is VerificationStatus.INDETERMINATE
    assert result.reason == "state_timeout"
    assert result.device is None


def test_commandless_state_with_same_device_ambiguity_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    hub = enabled_hub(monkeypatch)
    first = _PendingVerification(device_id="living-light")
    second = _PendingVerification(device_id="living-light")
    first.ack.update({"status": "ok"})
    second.ack.update({"status": "ok"})
    first.ack_received.set()
    second.ack_received.set()
    hub._pending.update({"first": first, "second": second})

    # When
    hub._on_message(
        None,
        None,
        message("homing/devices/living-light/state", {"device_id": "living-light", "state": {"power": True}}),
    )

    # Then
    assert not first.state_received.is_set()
    assert not second.state_received.is_set()


@pytest.mark.parametrize(
    ("responder_kind", "expected_status", "expected_reason"),
    [
        ("ack_only", VerificationStatus.INDETERMINATE, "state_timeout"),
        ("wrong_correlation", VerificationStatus.INDETERMINATE, "ack_timeout"),
        ("wrong_state", VerificationStatus.FAILED, "state_mismatch"),
        ("negative_ack", VerificationStatus.FAILED, "rejected"),
    ],
)
def test_unverified_mqtt_outcomes_never_complete(
    monkeypatch: pytest.MonkeyPatch,
    responder_kind: str,
    expected_status: VerificationStatus,
    expected_reason: str,
) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, payload: str) -> None:
        command_id = json.loads(payload)["command_id"]
        correlated = command_id if responder_kind != "wrong_correlation" else "different-command"
        status = "error" if responder_kind == "negative_ack" else "ok"
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/living-light/ack",
                {"device_id": "living-light", "command_id": correlated, "status": status},
            ),
        )
        if responder_kind == "wrong_state":
            hub._on_message(
                None,
                None,
                message(
                    "homing/devices/living-light/state",
                    {"device_id": "living-light", "command_id": command_id, "state": {"power": False}},
                ),
            )

    client = FakeClient(respond)
    hub.client = client

    # When
    result = hub.command("living-light", "on", timeout=0.001)

    # Then
    assert result.status is expected_status
    assert result.reason == expected_reason
    assert result.device is None
    assert client.publish_count == 1


def test_same_command_id_from_wrong_device_cannot_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, payload: str) -> None:
        command_id = json.loads(payload)["command_id"]
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/entry-lock/ack", {"device_id": "entry-lock", "command_id": command_id, "status": "ok"}
            ),
        )
        hub._on_message(
            None,
            None,
            message(
                "homing/devices/entry-lock/state",
                {"device_id": "entry-lock", "command_id": command_id, "state": {"power": True}},
            ),
        )

    client = FakeClient(respond)
    hub.client = client

    # When
    result = hub.command("living-light", "on", timeout=0.001)

    # Then
    assert result.status is VerificationStatus.INDETERMINATE
    assert result.reason == "ack_timeout"
    assert result.device is None
    assert client.publish_count == 1


def test_stale_unmatched_state_never_mutates_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)
    mutations = 0

    def update_state(*_args: Any, **_kwargs: Any) -> None:
        nonlocal mutations
        mutations += 1

    monkeypatch.setattr(registry, "update_state", update_state)

    # When
    hub._on_message(
        None,
        None,
        message(
            "homing/devices/living-light/state",
            {"device_id": "living-light", "command_id": "stale-command", "state": {"power": True}},
        ),
    )

    # Then
    assert mutations == 0


@pytest.mark.parametrize(
    ("topic_suffix", "payload"),
    [
        ("ack", {"device_id": "living-light", "status": "ok"}),
        ("state", {"device_id": "living-light", "state": "not-an-object"}),
    ],
)
def test_malformed_correlated_payload_cannot_succeed(
    monkeypatch: pytest.MonkeyPatch,
    topic_suffix: str,
    payload: dict[str, Any],
) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    def respond(_topic: str, command_payload: str) -> None:
        malformed = {**payload, "command_id": json.loads(command_payload)["command_id"]}
        hub._on_message(None, None, message(f"homing/devices/living-light/{topic_suffix}", malformed))

    client = FakeClient(respond)
    hub.client = client

    # When
    result = hub.command("living-light", "on", timeout=0.001)

    # Then
    assert result.status is not VerificationStatus.STATE_VERIFIED
    assert result.device is None
    assert client.publish_count == 1


def test_unavailable_transport_fails_without_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = enabled_hub(monkeypatch)

    # When
    result = hub.command("living-light", "on", timeout=0.001)

    # Then
    assert result.status is VerificationStatus.FAILED
    assert result.reason == "unavailable"
    assert result.device is None


def test_simulator_mode_uses_typed_verified_result_and_single_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    hub = MqttHub()
    monkeypatch.setattr(hub.settings, "mqtt_enabled", False)
    mutation_count = 0
    original_command = registry.command

    def counted_command(device_id: str, action: str, value: Any = None):
        nonlocal mutation_count
        mutation_count += 1
        return original_command(device_id, action, value)

    monkeypatch.setattr(registry, "command", counted_command)

    # When
    result = hub.command("living-light", "off")

    # Then
    assert result.status is VerificationStatus.STATE_VERIFIED
    assert result.device is not None
    assert result.device.state["power"] is False
    assert mutation_count == 1
