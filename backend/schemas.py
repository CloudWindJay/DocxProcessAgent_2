"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional
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


# ── Agent Chat ────────────────────────────────────────
class ChatRequest(BaseModel):
    file_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    file_updated: bool = False
