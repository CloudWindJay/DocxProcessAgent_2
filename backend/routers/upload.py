"""
Upload router — handles .docx file uploads and triggers ingestion.
"""
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import FileUploadResponse
from backend.auth import get_current_user
from backend.services.ingestion import run_ingestion

router = APIRouter(prefix="/api", tags=["Upload"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a .docx file.
    Triggers the full ingestion pipeline (save → tag → chunk → embed).
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are supported.",
        )

    file_id = str(uuid.uuid4())
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    db_file = run_ingestion(
        db=db,
        user_id=current_user.id,
        file_id=file_id,
        filename=file.filename,
        file_bytes=file_bytes,
    )

    return FileUploadResponse(
        file_id=db_file.id,
        filename=db_file.filename,
        uploaded_at=db_file.uploaded_at,
    )
