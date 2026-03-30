"""
Agent router — AI chat endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, File as FileModel
from backend.schemas import ChatRequest, ChatResponse
from backend.auth import get_current_user
from backend.services.agent_loop import run_agent

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/chat", response_model=ChatResponse)
def agent_chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to the AI agent about a specific document.
    The agent will use RAG to find relevant sections and can
    edit the document via function calling.
    """
    # Verify file ownership
    db_file = (
        db.query(FileModel)
        .filter(FileModel.id == payload.file_id, FileModel.user_id == current_user.id)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found or access denied.")

    result = run_agent(
        db=db,
        user_id=current_user.id,
        file_id=payload.file_id,
        user_message=payload.message,
    )

    return ChatResponse(
        reply=result["reply"],
        file_updated=result["file_updated"],
    )
