"""
OpenAI-compatible provider adapter.

Works for DashScope/Qwen and other OpenAI-compatible endpoints.
"""
from __future__ import annotations

from openai import OpenAI

from backend.llm.base import BaseLLMProvider
from backend.llm.types import UnifiedChatResponse, UnifiedToolCall


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str | None, default_model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._default_model = default_model

    def chat_text(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        kwargs = {
            "model": model or self._default_model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        model: str | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
    ) -> UnifiedChatResponse:
        kwargs = {
            "model": model or self._default_model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        tool_calls = [
            UnifiedToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (message.tool_calls or [])
        ]
        return UnifiedChatResponse(
            content=message.content or "",
            tool_calls=tool_calls,
        )

