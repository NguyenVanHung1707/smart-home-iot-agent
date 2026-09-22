"""Capability-aware boundary between language models and Task 3 IR."""

import json
from dataclasses import dataclass
from typing import Final, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.actions import ActionProposalBatch


class ModelResponse(Protocol):
    content: str


class InvokableModel(Protocol):
    async def ainvoke(self, messages: list[SystemMessage | HumanMessage]) -> ModelResponse: ...


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    structured_output: bool
    native_tools: bool
    schema_text: bool
    context_window: int

    @property
    def supports_control(self) -> bool:
        return self.structured_output or self.native_tools or self.schema_text


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model: str
    version: str
    capabilities: ModelCapabilities

    @classmethod
    def chat_only(cls, *, model: str, version: str, context_window: int) -> "ModelProfile":
        return cls(
            model=model,
            version=version,
            capabilities=ModelCapabilities(
                structured_output=False,
                native_tools=False,
                schema_text=False,
                context_window=context_window,
            ),
        )


@dataclass(frozen=True, slots=True)
class MalformedModelOutputError(Exception):
    model: str

    def __str__(self) -> str:
        return f"malformed JSON from model {self.model}"


@dataclass(frozen=True, slots=True)
class AdapterTimeoutError(Exception):
    model: str

    def __str__(self) -> str:
        return f"model {self.model} timed out"


@dataclass(frozen=True, slots=True)
class MissingCapabilityError(Exception):
    model: str
    capability: str

    def __str__(self) -> str:
        return f"model {self.model} lacks capability {self.capability}"


_PROFILES: Final = {
    "test-native": ModelProfile(
        model="test-native",
        version="1",
        capabilities=ModelCapabilities(
            structured_output=True,
            native_tools=True,
            schema_text=False,
            context_window=4096,
        ),
    ),
    "test-schema-text": ModelProfile(
        model="test-schema-text",
        version="1",
        capabilities=ModelCapabilities(
            structured_output=False,
            native_tools=False,
            schema_text=True,
            context_window=4096,
        ),
    ),
}


def get_profile(name: str) -> ModelProfile:
    """Return deterministic test profile by name."""
    try:
        return _PROFILES[name]
    except KeyError as error:
        raise MissingCapabilityError(model=name, capability="configured_profile") from error


def local_openai_profile(model: str, *, context_window: int = 8192) -> ModelProfile:
    """Describe configured OpenAI-compatible local model conservatively."""
    return ModelProfile(
        model=model,
        version="openai-compatible-v1",
        capabilities=ModelCapabilities(
            structured_output=False,
            native_tools=False,
            schema_text=False,
            context_window=context_window,
        ),
    )


class ModelAdapter:
    """Translate model output into non-authoritative Task 3 proposals."""

    def __init__(self, profile: ModelProfile, model: InvokableModel) -> None:
        self.profile = profile
        self._model = model

    async def chat(self, prompt: str) -> str:
        try:
            response = await self._model.ainvoke([HumanMessage(content=prompt)])
        except TimeoutError as error:
            raise AdapterTimeoutError(model=self.profile.model) from error
        return response.content

    async def control(self, prompt: str) -> ActionProposalBatch:
        if not self.profile.capabilities.supports_control:
            raise MissingCapabilityError(model=self.profile.model, capability="control")

        messages: list[SystemMessage | HumanMessage] = [
            SystemMessage(content="Return only JSON matching the supplied ActionProposalBatch schema."),
            HumanMessage(content=prompt),
        ]
        for attempt in range(2):
            try:
                response = await self._model.ainvoke(messages)
            except TimeoutError as error:
                raise AdapterTimeoutError(model=self.profile.model) from error
            try:
                payload = json.loads(response.content)
                return ActionProposalBatch.model_validate(payload)
            except (json.JSONDecodeError, ValidationError):
                if attempt == 0:
                    messages = [
                        *messages,
                        HumanMessage(content="Repair once: return only valid JSON matching the schema."),
                    ]
        raise MalformedModelOutputError(model=self.profile.model)
