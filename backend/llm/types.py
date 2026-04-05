"""
Shared types for unified LLM provider responses.
"""
from dataclasses import dataclass, field


@dataclass
class UnifiedToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class UnifiedChatResponse:
    content: str = ""
    tool_calls: list[UnifiedToolCall] = field(default_factory=list)

