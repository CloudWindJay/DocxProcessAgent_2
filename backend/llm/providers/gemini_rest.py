"""
Gemini REST provider adapter.

Implements a small subset of the Gemini GenerateContent REST API
needed by this project: text generation and function calling.
"""
from __future__ import annotations

import json
from urllib import error, request

from backend.llm.base import BaseLLMProvider
from backend.llm.types import UnifiedChatResponse, UnifiedToolCall


class GeminiRESTProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str, default_model: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    def chat_text(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        payload = self._build_payload(messages, temperature=temperature)
        data = self._post_generate_content(model or self._default_model, payload)
        content, _ = self._parse_response(data)
        return content

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        model: str | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
    ) -> UnifiedChatResponse:
        payload = self._build_payload(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )
        data = self._post_generate_content(model or self._default_model, payload)
        content, tool_calls = self._parse_response(data)
        return UnifiedChatResponse(content=content, tool_calls=tool_calls)

    def _post_generate_content(self, model: str, payload: dict) -> dict:
        url = f"{self._base_url}/models/{model}:generateContent"
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc

    def _build_payload(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        temperature: float | None = None,
    ) -> dict:
        system_instruction, contents = self._convert_messages(messages)
        payload = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}],
            }

        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        self._convert_tool_definition(tool["function"])
                        for tool in tools
                        if tool.get("type") == "function" and tool.get("function")
                    ]
                }
            ]
            if tool_choice:
                payload["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "AUTO" if tool_choice == "auto" else "NONE",
                    }
                }

        if temperature is not None:
            payload["generationConfig"] = {"temperature": temperature}

        return payload

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts: list[str] = []
        contents: list[dict] = []
        tool_name_by_id: dict[str, str] = {}

        for message in messages:
            role = message.get("role")
            content = message.get("content") or ""

            if role == "system":
                if content:
                    system_parts.append(content)
                continue

            if role == "assistant":
                parts = []
                if content:
                    parts.append({"text": content})

                for tool_call in message.get("tool_calls", []) or []:
                    function_data = tool_call.get("function", {})
                    tool_id = tool_call.get("id", "")
                    tool_name = function_data.get("name", "")
                    arguments = function_data.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        parsed_args = {}
                    if tool_id and tool_name:
                        tool_name_by_id[tool_id] = tool_name
                    parts.append(
                        {
                            "functionCall": {
                                "name": tool_name,
                                "args": parsed_args,
                            }
                        }
                    )

                if parts:
                    contents.append({"role": "model", "parts": parts})
                continue

            if role == "tool":
                tool_call_id = message.get("tool_call_id", "")
                function_name = tool_name_by_id.get(tool_call_id, "tool_result")
                try:
                    parsed_content = json.loads(content)
                except json.JSONDecodeError:
                    parsed_content = {"text": content}

                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": function_name,
                                    "response": parsed_content,
                                }
                            }
                        ],
                    }
                )
                continue

            if role in {"user", "assistant"}:
                contents.append(
                    {
                        "role": "user" if role == "user" else "model",
                        "parts": [{"text": content}],
                    }
                )

        return "\n\n".join(system_parts).strip(), contents

    def _convert_tool_definition(self, function: dict) -> dict:
        return {
            "name": function["name"],
            "description": function.get("description", ""),
            "parameters": function.get("parameters", {}),
        }

    def _parse_response(self, data: dict) -> tuple[str, list[UnifiedToolCall]]:
        candidates = data.get("candidates", [])
        if not candidates:
            return "", []

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text_parts: list[str] = []
        tool_calls: list[UnifiedToolCall] = []

        for index, part in enumerate(parts):
            if "text" in part and part["text"]:
                text_parts.append(part["text"])

            function_call = part.get("functionCall")
            if function_call:
                tool_calls.append(
                    UnifiedToolCall(
                        id=function_call.get("id", f"gemini-call-{index}"),
                        name=function_call.get("name", ""),
                        arguments=json.dumps(function_call.get("args", {})),
                    )
                )

        return "".join(text_parts).strip(), tool_calls
