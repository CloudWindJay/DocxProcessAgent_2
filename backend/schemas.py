"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Files ─────────────────────────────────────────────
class FileResponse(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    uploaded_at: datetime
    message: str = "File uploaded and processed successfully."


class LLMSettingsResponse(BaseModel):
    provider: Literal["qwen", "chatgpt", "gemini"]
    use_env_key: bool
    has_custom_api_key: bool
    masked_custom_api_key: Optional[str] = None


class LLMSettingsUpdateRequest(BaseModel):
    provider: Literal["qwen", "chatgpt", "gemini"]
    use_env_key: bool = True
    api_key: Optional[str] = None


# ── Agent Chat ────────────────────────────────────────
class ConversationCreateRequest(BaseModel):
    file_id: str


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    file_id: Optional[str] = None
    conversation_type: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    file_id: Optional[str] = None
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_payload: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    file_id: Optional[str] = None
    message: str


class ConversationChatResponse(BaseModel):
    conversation: ConversationResponse
    user_message: MessageResponse
    assistant_message: MessageResponse
    file_updated: bool = False


class ChatResponse(BaseModel):
    reply: str
    file_updated: bool = False
