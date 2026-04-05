"""
Conversation router for persistent file-scoped chat.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Conversation, File as FileModel, Message, User
from backend.llm.factory import get_user_llm_provider
from backend.schemas import (
    ChatRequest,
    ConversationChatResponse,
    ConversationCreateRequest,
    ConversationMessagesResponse,
    ConversationResponse,
    MessageResponse,
)
from backend.services.agent_loop import run_agent
from backend.services.conversation_memory import (
    create_file_conversation,
    create_message,
    get_conversation_for_user,
    get_or_create_summary,
    list_recent_messages,
    query_relevant_conversation_turns,
    save_turn_memory,
    update_conversation_summary,
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


def _serialize_conversation(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse.model_validate(conversation)


def _serialize_message(message: Message) -> MessageResponse:
    return MessageResponse.model_validate(message)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_file = (
        db.query(FileModel)
        .filter(FileModel.id == payload.file_id, FileModel.user_id == current_user.id)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found or access denied.")

    conversation = create_file_conversation(db, current_user.id, db_file)
    return _serialize_conversation(conversation)


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    file_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Conversation).filter(
        Conversation.user_id == current_user.id,
        Conversation.status == "active",
    )
    if file_id:
        query = query.filter(Conversation.file_id == file_id)

    conversations = query.order_by(Conversation.last_message_at.desc()).all()
    return [_serialize_conversation(conversation) for conversation in conversations]


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_conversation_for_user(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ConversationMessagesResponse(
        conversation=_serialize_conversation(conversation),
        messages=[_serialize_message(message) for message in messages],
    )


@router.post("/{conversation_id}/messages", response_model=ConversationChatResponse)
def send_conversation_message(
    conversation_id: str,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    conversation = get_conversation_for_user(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if conversation.conversation_type != "file_chat" or not conversation.file_id:
        raise HTTPException(
            status_code=400,
            detail="This conversation is not bound to a file.",
        )

    db_file = (
        db.query(FileModel)
        .filter(FileModel.id == conversation.file_id, FileModel.user_id == current_user.id)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="Conversation file not found.")

    user_message = create_message(
        db=db,
        conversation=conversation,
        role="user",
        content=text,
    )

    summary = get_or_create_summary(db, conversation.id)
    recent_messages = [
        {"role": message.role, "content": message.content}
        for message in list_recent_messages(db, conversation.id)
        if message.id != user_message.id
    ]
    recalled_turns = query_relevant_conversation_turns(
        conversation=conversation,
        query_text=text,
    )

    result = run_agent(
        db=db,
        user_id=current_user.id,
        file_id=conversation.file_id,
        user_message=text,
        file_name=db_file.filename,
        llm_provider=get_user_llm_provider(current_user),
        conversation_summary=summary.summary_text,
        recent_messages=recent_messages,
        retrieved_memory_turns=recalled_turns,
    )

    assistant_message = create_message(
        db=db,
        conversation=conversation,
        role="assistant",
        content=result["reply"],
    )

    background_tasks.add_task(
        save_turn_memory,
        conversation.id,
        user_message.id,
        assistant_message.id,
    )
    background_tasks.add_task(update_conversation_summary, conversation.id)

    db.refresh(conversation)
    return ConversationChatResponse(
        conversation=_serialize_conversation(conversation),
        user_message=_serialize_message(user_message),
        assistant_message=_serialize_message(assistant_message),
        file_updated=result["file_updated"],
    )
