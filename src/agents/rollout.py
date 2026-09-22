from collections.abc import Callable
from typing import Protocol

from src.config import AgentRolloutMode, Settings


class CompiledAgent(Protocol):
    async def ainvoke(self, state: dict[str, str]) -> dict[str, str]: ...


def select_agent(
    settings: Settings,
    legacy_factory: Callable[[], CompiledAgent],
    typed_factory: Callable[[], CompiledAgent],
) -> CompiledAgent:
    """Build only runtime-selected agent; shadow always selects legacy."""
    match settings.rollout_contract.active_mode:
        case AgentRolloutMode.LEGACY_ACTIVE:
            return legacy_factory()
        case AgentRolloutMode.TYPED_ACTIVE:
            return typed_factory()
        case unreachable:
            from typing import assert_never

            assert_never(unreachable)
