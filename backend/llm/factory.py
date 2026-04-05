"""
Factory helpers for selecting the active runtime LLM provider.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from backend.config import settings
from backend.llm.base import BaseLLMProvider
from backend.llm.providers.gemini_rest import GeminiRESTProvider
from backend.llm.providers.openai_compatible import OpenAICompatibleProvider

if TYPE_CHECKING:
    from backend.models import User


def create_llm_provider(
    provider_name: str,
    *,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> BaseLLMProvider:
    normalized = (provider_name or "").strip().lower()
    if normalized in {"qwen", "openai", "openai_compatible", "dashscope", "chatgpt"}:
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=model,
        )
    if normalized == "gemini":
        return GeminiRESTProvider(
            api_key=api_key,
            base_url=base_url or settings.get_provider_base_url("gemini") or "",
            default_model=model,
        )

    raise ValueError(f"Unsupported LLM provider: {provider_name}")


@lru_cache(maxsize=1)
def get_default_llm_provider() -> BaseLLMProvider:
    return create_llm_provider(
        settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
    )


def get_user_llm_provider(user: "User | None") -> BaseLLMProvider:
    if not user:
        return get_default_llm_provider()

    provider_name = (getattr(user, "llm_provider", None) or settings.LLM_PROVIDER).strip().lower()
    use_env_key = getattr(user, "llm_use_env_key", True)
    custom_api_key = (getattr(user, "llm_api_key", None) or "").strip()

    api_key = settings.get_provider_api_key(provider_name) if use_env_key else custom_api_key
    if not api_key:
        api_key = settings.get_provider_api_key(provider_name)

    return create_llm_provider(
        provider_name,
        api_key=api_key,
        model=settings.get_provider_model(provider_name),
        base_url=settings.get_provider_base_url(provider_name),
    )
