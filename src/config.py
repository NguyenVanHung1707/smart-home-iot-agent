from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Literal, TypedDict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentRolloutMode(StrEnum):
    """Select which interpreter orchestrates requests."""

    LEGACY_ACTIVE = "legacy_active"
    TYPED_SHADOW = "typed_shadow"
    TYPED_ACTIVE = "typed_active"


@dataclass(frozen=True, slots=True)
class SharedSafetyKernel:
    """Stable authority boundary shared by all rollout modes."""

    validator: str = "validator"
    policy: str = "policy"
    idempotency: str = "idempotency_ledger"
    verification: str = "verification"


_SHARED_SAFETY_KERNEL = SharedSafetyKernel()


@dataclass(frozen=True, slots=True)
class RolloutContract:
    """Fail-closed selection contract with an injectable safety boundary."""

    requested_mode: AgentRolloutMode
    typed_interpreter_enabled: bool
    typed_capability_available: bool
    typed_artifact_available: bool
    safety_kernel: SharedSafetyKernel = _SHARED_SAFETY_KERNEL

    @property
    def typed_is_available(self) -> bool:
        return self.typed_interpreter_enabled and self.typed_capability_available and self.typed_artifact_available

    @property
    def active_mode(self) -> AgentRolloutMode:
        """Return sole publisher; unsafe typed activation falls back to legacy."""
        match self.requested_mode:
            case AgentRolloutMode.TYPED_ACTIVE if self.typed_is_available:
                return AgentRolloutMode.TYPED_ACTIVE
            case AgentRolloutMode.LEGACY_ACTIVE | AgentRolloutMode.TYPED_SHADOW | AgentRolloutMode.TYPED_ACTIVE:
                return AgentRolloutMode.LEGACY_ACTIVE
            case unreachable:
                from typing import assert_never

                assert_never(unreachable)


class RolloutDocsContract(TypedDict):
    requested_mode: str
    active_mode: str
    typed_available: bool
    publisher: str
    safety_kernel: list[str]


def rollout_docs_contract(contract: RolloutContract) -> RolloutDocsContract:
    """Serialize runtime rollout facts for checked documentation evidence."""
    publisher = "typed" if contract.active_mode is AgentRolloutMode.TYPED_ACTIVE else "legacy"
    kernel = contract.safety_kernel
    return {
        "requested_mode": contract.requested_mode.value,
        "active_mode": contract.active_mode.value,
        "typed_available": contract.typed_is_available,
        "publisher": publisher,
        "safety_kernel": [kernel.validator, kernel.policy, kernel.idempotency, kernel.verification],
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Homing Hub"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = Field(default=600, ge=60, le=10000)

    # LLM
    openai_api_key: str = ""
    model_name: str = "qwen2.5-3b-instruct-q4_k_m.gguf"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llama_base_url: str = "http://llama:8080/v1"
    llm_enabled: bool = False
    llm_timeout_seconds: float = Field(default=60.0, ge=1.0, le=120.0)
    llm_max_retries: int = Field(default=0, ge=0, le=3)
    llm_max_tool_call_iterations: int = Field(default=3, ge=1, le=8)
    llm_tool_transport: Literal["homeassistant_protocol", "native"] = "homeassistant_protocol"
    # Opt-in only: grammar-constrained local protocol generation can reduce natural fallback quality.
    llm_local_protocol_grammar_enabled: bool = False
    # Opt-in: generalized local text tool envelope is experimental; legacy protocol remains default.
    llm_local_generic_tool_protocol_enabled: bool = False
    # Opt-in: retrieve a compact schema catalog from the runtime registry per request.
    llm_local_tool_retrieval_enabled: bool = False
    # Opt-in: constrain only the generic fenced JSON envelope, not tool semantics.
    llm_local_generic_tool_grammar_enabled: bool = False
    llm_local_only: bool = True
    device_storage_path: str = "data/devices.json"
    real_device_storage_path: str = "data/devices_real.json"
    simulator_device_storage_path: str = "data/devices.json"

    # AI Queue / Concurrency (Jetson Nano)
    ai_max_concurrent: int = Field(default=1, ge=1, le=10)
    ai_queue_capacity: int = Field(default=10, ge=1, le=50)
    ai_queue_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)

    agent_rollout_mode: AgentRolloutMode = AgentRolloutMode.LEGACY_ACTIVE
    typed_interpreter_enabled: bool = False
    typed_interpreter_capability_available: bool = False
    typed_interpreter_artifact_available: bool = False

    mqtt_broker: str = "mqtt"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_enabled: bool = False
    mqtt_topic_prefix: str = "homing"
    mqtt_qos: int = Field(default=1, ge=0, le=2)
    mqtt_retain_state: bool = True
    mqtt_client_id: str = "homing-hub"
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_tls_enabled: bool = False

    # Local speech runtimes. Text commands remain available when voice is disabled.
    voice_enabled: bool = False
    zipformer_endpoint: str = ""
    zipformer_health_endpoint: str = ""
    zipformer_model_dir: str = "models/zipformer/sherpa-onnx-zipformer-vi-int8-2025-04-20"
    zipformer_num_threads: int = Field(default=2, ge=1, le=4)
    piper_endpoint: str = "http://piper:5000"
    piper_voice: str = "vi_VN-vais1000-medium"
    tts_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    voice_max_audio_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    voice_max_audio_bytes: int = Field(default=1_000_000, ge=44, le=10_000_000)
    voice_max_tts_chars: int = Field(default=1000, ge=1, le=5000)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Auth
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_ttl_days: int = Field(default=14, ge=1, le=90)
    users_file: str = "./data/users.json"
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=50)
    login_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)
    login_lockout_threshold: int = Field(default=10, ge=1, le=100)
    bootstrap_admin_email: str = "admin@homing.dev"
    bootstrap_admin_password: str = ""

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    @property
    def rollout_contract(self) -> RolloutContract:
        return RolloutContract(
            requested_mode=self.agent_rollout_mode,
            typed_interpreter_enabled=self.typed_interpreter_enabled,
            typed_capability_available=self.typed_interpreter_capability_available,
            typed_artifact_available=self.typed_interpreter_artifact_available,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
