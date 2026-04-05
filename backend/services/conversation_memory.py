"""
Conversation persistence and memory helpers.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.chromadb_client import add_conversation_turn, query_conversation_turns
from backend.database import SessionLocal
from backend.llm.factory import get_user_llm_provider
from backend.models import Conversation, ConversationSummary, File, Message

SUMMARY_MAX_RECENT_MESSAGES = 12
RECENT_CHAT_MESSAGES = 8

def build_conversation_title(filename: str, created_at: datetime | None = None) -> str:
    created_at = created_at or datetime.now(timezone.utc)
    stem = filename.rsplit(".", 1)[0]
    return f"{stem} · {created_at.strftime('%Y-%m-%d %H:%M')}"


def create_file_conversation(db: Session, user_id: str, db_file: File) -> Conversation:
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        user_id=user_id,
        file_id=db_file.id,
        conversation_type="file_chat",
        title=build_conversation_title(db_file.filename, now),
        status="active",
        created_at=now,
        updated_at=now,
        last_message_at=now,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_for_user(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .first()
    )


def create_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_payload: str | None = None,
) -> Message:
    now = datetime.now(timezone.utc)
    message = Message(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        file_id=conversation.file_id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_payload=tool_payload,
        created_at=now,
    )
    db.add(message)
    conversation.last_message_at = now
    conversation.updated_at = now
    db.commit()
    db.refresh(message)
    db.refresh(conversation)
    return message


def list_recent_messages(
    db: Session,
    conversation_id: str,
    limit: int = RECENT_CHAT_MESSAGES,
) -> list[Message]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def get_or_create_summary(db: Session, conversation_id: str) -> ConversationSummary:
    summary = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.conversation_id == conversation_id)
        .first()
    )
    if summary:
        return summary

    summary = ConversationSummary(
        conversation_id=conversation_id,
        summary_text="",
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def query_relevant_conversation_turns(
    conversation: Conversation,
    query_text: str,
    n_results: int = 4,
) -> list[dict]:
    results = query_conversation_turns(
        query_text=query_text,
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        file_id=conversation.file_id,
        n_results=n_results,
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    turns = []
    for index, doc_text in enumerate(docs):
        turns.append(
            {
                "text": doc_text,
                "metadata": metas[index] if index < len(metas) else {},
                "distance": distances[index] if index < len(distances) else None,
            }
        )
    return turns


def build_turn_document(user_message: Message, assistant_message: Message) -> str:
    return f"[User]\n{user_message.content}\n\n[Assistant]\n{assistant_message.content}"


def save_turn_memory(conversation_id: str, start_message_id: str, end_message_id: str) -> None:
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation or not conversation.file_id:
            return

        messages = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.id.in_([start_message_id, end_message_id]),
            )
            .order_by(Message.created_at.asc())
            .all()
        )
        if len(messages) < 2:
            return

        user_message = next((msg for msg in messages if msg.id == start_message_id), None)
        assistant_message = next((msg for msg in messages if msg.id == end_message_id), None)
        if not user_message or not assistant_message:
            return

        turn_count = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
            )
            .count()
        )

        add_conversation_turn(
            record_id=f"{conversation_id}_turn_{assistant_message.id}",
            document=build_turn_document(user_message, assistant_message),
            metadata={
                "conversation_id": conversation.id,
                "user_id": conversation.user_id,
                "file_id": conversation.file_id,
                "conversation_type": conversation.conversation_type,
                "turn_index": turn_count,
                "start_message_id": user_message.id,
                "end_message_id": assistant_message.id,
                "memory_type": "turn",
            },
        )
    finally:
        db.close()


def update_conversation_summary(conversation_id: str) -> None:
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return

        summary = get_or_create_summary(db, conversation_id)
        query = db.query(Message).filter(Message.conversation_id == conversation_id)

        if summary.last_summarized_message_id:
            checkpoint = db.query(Message).filter(Message.id == summary.last_summarized_message_id).first()
            if checkpoint:
                query = query.filter(Message.created_at > checkpoint.created_at)

        new_messages = query.order_by(Message.created_at.asc()).limit(SUMMARY_MAX_RECENT_MESSAGES).all()
        if not new_messages:
            return

        summary.summary_text = _summarize_conversation(
            conversation=conversation,
            previous_summary=summary.summary_text,
            new_messages=new_messages,
        )
        summary.last_summarized_message_id = new_messages[-1].id
        summary.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _summarize_conversation(
    conversation: Conversation,
    previous_summary: str,
    new_messages: list[Message],
) -> str:
    transcript = "\n".join(
        f"{message.role.upper()}: {message.content}"
        for message in new_messages
    )
    file_label = conversation.file.filename if conversation.file else "the current document"
    prompt = (
        "You summarize file-scoped editing conversations.\n"
        "Preserve only high-signal memory for future turns:\n"
        "- current goal\n"
        "- confirmed edits\n"
        "- user preferences\n"
        "- pending work\n"
        "Keep it under 180 words.\n\n"
        f"Document: {file_label}\n"
        f"Previous summary:\n{previous_summary or '(none)'}\n\n"
        f"New messages:\n{transcript}\n"
    )

    try:
        provider = get_user_llm_provider(conversation.owner)
        content = provider.chat_text(
            messages=[{"role": "system", "content": prompt}],
            temperature=0,
        ).strip()
        if content:
            return content
    except Exception:
        pass

    return _fallback_summary(previous_summary, new_messages)


def _fallback_summary(previous_summary: str, new_messages: list[Message]) -> str:
    snippets = [previous_summary.strip()] if previous_summary.strip() else []
    for message in new_messages[-4:]:
        prefix = "User" if message.role == "user" else "Assistant"
        snippets.append(f"{prefix}: {message.content[:180]}")
    return "\n".join(snippets[-6:])
