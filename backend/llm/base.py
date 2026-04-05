"""
Base interface for provider-specific LLM adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.llm.types import UnifiedChatResponse


class BaseLLMProvider(ABC):
    @abstractmethod
    def chat_text(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        model: str | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
    ) -> UnifiedChatResponse:
        raise NotImplementedError

