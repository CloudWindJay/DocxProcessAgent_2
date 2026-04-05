"""
SQLAlchemy ORM models for users, files, and conversations.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from backend.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    llm_provider = Column(String(50), nullable=False, default="qwen")
    llm_use_env_key = Column(Boolean, nullable=False, default=True)
    llm_api_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")
    conversations = relationship(
        "Conversation",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "Message",
        back_populates="author",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    local_storage_path = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="files")
    conversations = relationship(
        "Conversation",
        back_populates="file",
        cascade="all, delete-orphan",
    )
    messages = relationship("Message", back_populates="file")

    def __repr__(self):
        return f"<File(id={self.id}, filename={self.filename})>"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id"), nullable=True, index=True)
    conversation_type = Column(String(50), nullable=False, default="file_chat")
    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    owner = relationship("User", back_populates="conversations")
    file = relationship("File", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    summary = relationship(
        "ConversationSummary",
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id"), nullable=True, index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    tool_name = Column(String(100), nullable=True)
    tool_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    conversation = relationship("Conversation", back_populates="messages")
    author = relationship("User", back_populates="messages")
    file = relationship("File", back_populates="messages")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id"),
        primary_key=True,
    )
    summary_text = Column(Text, nullable=False, default="")
    last_summarized_message_id = Column(String(36), nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    conversation = relationship("Conversation", back_populates="summary")
