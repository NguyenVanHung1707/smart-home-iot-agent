import json
from pathlib import Path

import pytest

from src.agents.rollout import select_agent
from src.config import AgentRolloutMode, RolloutContract, Settings, SharedSafetyKernel, rollout_docs_contract


def settings(**overrides: bool | AgentRolloutMode) -> Settings:
    return Settings(_env_file=None, **overrides)


class RequestSpy:
    def __init__(self, publisher: str, publishes: list[str]) -> None:
        self._publisher = publisher
        self._publishes = publishes

    async def ainvoke(self, request: dict[str, str]) -> dict[str, str]:
        self._publishes.append(self._publisher)
        return request


@pytest.mark.parametrize(
    ("configured", "typed_expected"),
    [
        (settings(), False),
        (settings(agent_rollout_mode=AgentRolloutMode.TYPED_SHADOW), False),
        (
            settings(
                agent_rollout_mode=AgentRolloutMode.TYPED_ACTIVE,
                typed_interpreter_enabled=True,
                typed_interpreter_capability_available=True,
                typed_interpreter_artifact_available=True,
            ),
            True,
        ),
    ],
)
def test_selector_chooses_runtime_mode(configured: Settings, typed_expected: bool) -> None:
    # Given
    legacy = object()
    typed = object()
    # When
    selected = select_agent(configured, lambda: legacy, lambda: typed)

    # Then
    assert selected is (typed if typed_expected else legacy)


@pytest.mark.parametrize(
    "overrides",
    [
        {"typed_interpreter_enabled": False},
        {"typed_interpreter_capability_available": False},
        {"typed_interpreter_artifact_available": False},
    ],
)
def test_missing_typed_gate_selects_legacy(overrides: dict[str, bool]) -> None:
    # Given
    configured = settings(
        agent_rollout_mode=AgentRolloutMode.TYPED_ACTIVE,
        typed_interpreter_enabled=overrides.get("typed_interpreter_enabled", True),
        typed_interpreter_capability_available=overrides.get("typed_interpreter_capability_available", True),
        typed_interpreter_artifact_available=overrides.get("typed_interpreter_artifact_available", True),
    )
    legacy = object()

    # When
    selected = select_agent(configured, lambda: legacy, lambda: pytest.fail("typed must remain disabled"))

    # Then
    assert selected is legacy


@pytest.mark.asyncio
async def test_shadow_request_has_zero_typed_executor_and_one_legacy_publisher() -> None:
    # Given
    shadow = settings(
        agent_rollout_mode=AgentRolloutMode.TYPED_SHADOW,
        typed_interpreter_enabled=True,
        typed_interpreter_capability_available=True,
        typed_interpreter_artifact_available=True,
    )
    publishes: list[str] = []
    legacy = RequestSpy("legacy", publishes)
    typed_executor = RequestSpy("typed", publishes)
    # When
    result = await select_agent(shadow, lambda: legacy, lambda: typed_executor).ainvoke({"query": "test"})

    # Then
    assert result == {"query": "test"}
    assert publishes == ["legacy"]


def test_modes_share_injected_kernel_and_rollback_changes_only_selection() -> None:
    # Given
    kernel = SharedSafetyKernel()
    typed = RolloutContract(AgentRolloutMode.TYPED_ACTIVE, True, True, True, kernel)
    rollback = RolloutContract(AgentRolloutMode.LEGACY_ACTIVE, False, False, False, kernel)

    # When
    typed_facts = rollout_docs_contract(typed)
    rollback_facts = rollout_docs_contract(rollback)

    # Then
    assert typed.safety_kernel is rollback.safety_kernel
    assert typed_facts["publisher"] == "typed"
    assert rollback_facts["publisher"] == "legacy"
    assert typed_facts["safety_kernel"] == rollback_facts["safety_kernel"]


def test_docs_contract_artifact_matches_runtime_default() -> None:
    # Given
    artifact = Path("eval/results/task-16/docs-contract.json")

    # When
    facts = json.loads(artifact.read_text(encoding="utf-8"))

    # Then
    assert facts == rollout_docs_contract(settings().rollout_contract)
