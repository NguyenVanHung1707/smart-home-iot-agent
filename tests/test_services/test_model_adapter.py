from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.actions import ActionProposalBatch
from src.services import llm
from src.services.model_adapter import (
    AdapterTimeoutError,
    MalformedModelOutputError,
    MissingCapabilityError,
    ModelAdapter,
    ModelProfile,
    get_profile,
    local_openai_profile,
)


def _control_json() -> str:
    request_id = uuid4()
    return (
        '{"request_id":"'
        f"{request_id}"
        '","actions":[{"request_id":"'
        f"{request_id}"
        '","correlation_id":"'
        f"{uuid4()}"
        '","device_id":"living-light","action":"on","value":null,"confidence":0.9}]}'
    )


def test_local_openai_profile_constructs_conservative_capabilities() -> None:
    # Given / When
    profile = local_openai_profile("local-model")

    # Then
    assert profile.capabilities.structured_output is False
    assert profile.capabilities.native_tools is False
    assert profile.capabilities.schema_text is False
    assert profile.capabilities.supports_control is False


def test_get_model_adapter_constructs_local_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    settings = SimpleNamespace(model_name="local-model")
    model = SimpleNamespace(ainvoke=AsyncMock())
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "get_llm", lambda: model)

    # When
    adapter = llm.get_model_adapter()

    # Then
    assert adapter.profile == local_openai_profile("local-model")
    assert adapter.profile.capabilities.supports_control is False


def test_deterministic_profiles_expose_capabilities() -> None:
    # Given / When
    native = get_profile("test-native")
    schema_text = get_profile("test-schema-text")

    # Then
    assert native.capabilities.structured_output is True
    assert native.capabilities.native_tools is True
    assert schema_text.capabilities.structured_output is False
    assert schema_text.capabilities.native_tools is False
    assert schema_text.capabilities.schema_text is True
    assert native.model == "test-native"
    assert schema_text.version == "1"


@pytest.mark.asyncio
async def test_schema_text_repairs_malformed_json_once() -> None:
    # Given
    model = SimpleNamespace(
        ainvoke=AsyncMock(side_effect=[SimpleNamespace(content="not-json"), SimpleNamespace(content=_control_json())])
    )
    profile = get_profile("test-schema-text")
    assert profile.capabilities.schema_text is True
    adapter = ModelAdapter(profile, model)

    # When
    result = await adapter.control("bật đèn")

    # Then
    assert isinstance(result, ActionProposalBatch)
    assert model.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_schema_text_stops_after_one_failed_repair() -> None:
    # Given
    model = SimpleNamespace(
        ainvoke=AsyncMock(side_effect=[SimpleNamespace(content="not-json"), SimpleNamespace(content="still-not-json")])
    )
    adapter = ModelAdapter(get_profile("test-schema-text"), model)

    # When / Then
    with pytest.raises(MalformedModelOutputError):
        await adapter.control("bật đèn")
    assert model.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_control_fails_closed_when_capability_missing_but_chat_remains_available() -> None:
    # Given
    profile = ModelProfile.chat_only(model="chat-only", version="1", context_window=2048)
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="Xin chào")))
    adapter = ModelAdapter(profile, model)

    # When / Then
    with pytest.raises(MissingCapabilityError):
        await adapter.control("bật đèn")
    assert await adapter.chat("xin chào") == "Xin chào"


@pytest.mark.asyncio
async def test_timeout_is_typed() -> None:
    # Given
    model = SimpleNamespace(ainvoke=AsyncMock(side_effect=TimeoutError("late")))
    adapter = ModelAdapter(get_profile("test-native"), model)

    # When / Then
    with pytest.raises(AdapterTimeoutError):
        await adapter.chat("xin chào")
