"""
Files router — list files and download .docx for preview.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, File as FileModel
from backend.schemas import FileResponse as FileSchema
from backend.auth import get_current_user
from backend.chromadb_client import delete_file_chunks

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.get("", response_model=list[FileSchema])
def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all files for the authenticated user."""
    files = (
        db.query(FileModel)
        .filter(FileModel.user_id == current_user.id)
        .order_by(FileModel.uploaded_at.desc())
        .all()
    )
    return files


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download the raw .docx file for rendering in docx-preview.
    Enforces file ownership.
    """
    db_file = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.user_id == current_user.id)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found.")

    if not os.path.exists(db_file.local_storage_path):
        raise HTTPException(status_code=404, detail="File missing from storage.")

    return FileResponse(
        path=db_file.local_storage_path,
        filename=db_file.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document from storage, database, and vector index."""
    # 1. Enforce ownership
    db_file = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.user_id == current_user.id)
        .first()
    )
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found.")

    # 2. Delete physical file
    if os.path.exists(db_file.local_storage_path):
        try:
            os.remove(db_file.local_storage_path)
        except Exception as e:
            print(f"Error deleting physical file: {e}")

    # 3. Clean up ChromaDB chunks
    try:
        delete_file_chunks(file_id)
    except Exception as e:
        print(f"Error deleting ChromaDB chunks: {e}")

    # 4. Delete database record
    db.delete(db_file)
    db.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "File deleted successfully."},
    )
