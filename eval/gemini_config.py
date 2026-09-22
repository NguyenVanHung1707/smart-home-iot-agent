"""Secret-safe configuration for native Gemini evaluation."""

from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

_API_KEY_NAME: Final = "GEMINI_API_KEY"


class GeminiConfigurationError(Exception):
    """Gemini configuration cannot be loaded safely."""


class GeminiConfig(BaseModel):
    """Non-secret Gemini run configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(pattern=r"^gemini-[a-z0-9.-]+$")
    run_id: str = Field(min_length=1)
    timeout_seconds: float = Field(gt=0)
    output: Path

    @classmethod
    def from_environment(
        cls,
        *,
        repo_root: Path,
        model: str,
        run_id: str,
        timeout_seconds: float,
        output: Path,
    ) -> "GeminiConfig":
        """Load repo dotenv without retaining its secret in serializable config."""
        load_gemini_api_key(repo_root)
        return cls(model=model, run_id=run_id, timeout_seconds=timeout_seconds, output=output)


def load_gemini_api_key(repo_root: Path) -> SecretStr:
    """Load key from repo dotenv while preserving exported environment precedence."""
    load_dotenv(repo_root / ".env", override=False)
    import os

    value = os.environ.get(_API_KEY_NAME)
    if not value:
        raise GeminiConfigurationError
    return SecretStr(value)
