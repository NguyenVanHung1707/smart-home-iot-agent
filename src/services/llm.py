from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.services.model_adapter import ModelAdapter, local_openai_profile


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    is_cloud_api = bool(settings.openai_api_key and settings.openai_api_key.startswith(("sk-", "AIza")))
    if (
        not is_cloud_api
        and getattr(settings, "llm_local_only", False)
        and not _is_local_endpoint(settings.llama_base_url)
    ):
        raise RuntimeError("LLM_LOCAL_ONLY requires a local llama.cpp endpoint")

    kwargs: dict[str, Any] = {
        "model": settings.model_name,
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }

    if is_cloud_api:
        kwargs["api_key"] = settings.openai_api_key
        if settings.llama_base_url and "ollama:11434" not in settings.llama_base_url:
            kwargs["base_url"] = settings.llama_base_url
    else:
        kwargs["api_key"] = settings.openai_api_key or "local-llama"
        kwargs["base_url"] = settings.llama_base_url

    return ChatOpenAI(**kwargs)


def _is_local_endpoint(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").casefold()
    if hostname in {"localhost", "llama", "ollama", "host.docker.internal", "127.0.0.1", "::1"}:
        return True
    try:
        return ip_address(hostname).is_private
    except ValueError:
        return False


def get_model_adapter() -> ModelAdapter:
    """Return conservative adapter for configured local OpenAI-compatible model."""
    settings = get_settings()
    return ModelAdapter(local_openai_profile(settings.model_name), get_llm())
