"""
Learning-oriented MCP server for DocxProcessAgent.

This server exposes the project's document workspace to any MCP host.
It is intentionally small and readable so new agent developers can trace
how resources, tools, and prompts map onto an existing application.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any

from docx import Document
from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import File, User
from backend.chromadb_client import query_chunks
from backend.services.ingestion import get_paragraph_bookmark
from backend.services.document_tools import (
    append_paragraph as append_docx_paragraph,
    delete_paragraph as delete_docx_paragraph,
    edit_docx_paragraph,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("DocxProcessAgent Workspace", json_response=True)


@contextmanager
def db_session() -> Session:
    """Small helper so every MCP handler uses a fresh SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_file_or_raise(db: Session, file_id: str) -> File:
    db_file = db.query(File).filter(File.id == file_id).first()
    if not db_file:
        raise ValueError(f"File {file_id} was not found.")
    return db_file


def _serialize_file(db_file: File) -> dict[str, Any]:
    return {
        "id": db_file.id,
        "user_id": db_file.user_id,
        "filename": db_file.filename,
        "uploaded_at": db_file.uploaded_at.isoformat() if db_file.uploaded_at else None,
        "local_storage_path": db_file.local_storage_path,
    }


def _read_paragraphs(file_path: str) -> list[dict[str, Any]]:
    doc = Document(file_path)
    paragraphs: list[dict[str, Any]] = []

    for index, paragraph in enumerate(doc.paragraphs):
        paragraphs.append(
            {
                "index": index,
                "paragraph_uuid": get_paragraph_bookmark(paragraph),
                "text": paragraph.text,
            }
        )

    return paragraphs


@mcp.resource("docxprocessagent://project/overview")
def project_overview() -> dict[str, Any]:
    """High-level project metadata that an MCP host can read as context."""
    return {
        "name": "DocxProcessAgent",
        "purpose": "Upload, retrieve, preview, and edit .docx files with RAG-backed agents.",
        "backend": "FastAPI + SQLAlchemy + MySQL + ChromaDB",
        "frontend": "React + Vite + docx-preview",
        "mcp_fit": (
            "A workspace/document MCP is a natural fit because agents often need "
            "safe read access to document context plus a few explicit edit tools."
        ),
        "storage": {
            "upload_dir": settings.UPLOAD_DIR,
            "chroma_persist_dir": settings.CHROMA_PERSIST_DIR,
        },
    }


@mcp.resource("docxprocessagent://files")
def files_resource() -> list[dict[str, Any]]:
    """List every indexed document known to the application."""
    with db_session() as db:
        files = db.query(File).order_by(File.uploaded_at.desc()).all()
        return [_serialize_file(db_file) for db_file in files]


@mcp.resource("docxprocessagent://files/{file_id}/paragraphs")
def file_paragraphs_resource(file_id: str) -> dict[str, Any]:
    """Read a file as paragraph records so an MCP client can inspect UUID anchors."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        return {
            "file": _serialize_file(db_file),
            "paragraphs": _read_paragraphs(db_file.local_storage_path),
        }


@mcp.tool()
def list_users() -> list[dict[str, Any]]:
    """List application users so an MCP host can discover the workspace."""
    with db_session() as db:
        users = db.query(User).order_by(User.created_at.asc()).all()
        return [
            {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "file_count": len(user.files),
            }
            for user in users
        ]


@mcp.tool()
def list_files(username: str | None = None) -> list[dict[str, Any]]:
    """List files, optionally filtered to one username."""
    with db_session() as db:
        query = db.query(File)
        if username:
            query = query.join(User).filter(User.username == username)
        files = query.order_by(File.uploaded_at.desc()).all()
        return [_serialize_file(db_file) for db_file in files]


@mcp.tool()
def read_document(file_id: str, include_empty: bool = False) -> dict[str, Any]:
    """Return the document as ordered paragraphs with bookmark UUIDs."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        paragraphs = _read_paragraphs(db_file.local_storage_path)
        if not include_empty:
            paragraphs = [p for p in paragraphs if p["text"].strip()]
        return {
            "file": _serialize_file(db_file),
            "paragraphs": paragraphs,
        }


@mcp.tool()
def search_document(file_id: str, query: str, n_results: int = 5) -> dict[str, Any]:
    """Semantic search over the ChromaDB chunks for one document."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        results = query_chunks(
            query_text=query,
            user_id=db_file.user_id,
            file_id=file_id,
            n_results=n_results,
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        matches = []
        for index, doc_text in enumerate(docs):
            matches.append(
                {
                    "rank": index + 1,
                    "text": doc_text,
                    "distance": distances[index] if index < len(distances) else None,
                    "metadata": metas[index] if index < len(metas) else {},
                }
            )

        return {
            "file": _serialize_file(db_file),
            "query": query,
            "matches": matches,
        }


@mcp.tool()
def edit_paragraph(file_id: str, paragraph_uuid: str, new_text: str) -> dict[str, Any]:
    """Edit one paragraph in the stored .docx and re-index the document."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        return edit_docx_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=paragraph_uuid,
            new_text=new_text,
            user_id=db_file.user_id,
        )


@mcp.tool()
def append_paragraph(file_id: str, after_paragraph_uuid: str, text: str) -> dict[str, Any]:
    """Insert a new paragraph after an existing anchored paragraph."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        return append_docx_paragraph(
            db=db,
            file_id=file_id,
            after_paragraph_uuid=after_paragraph_uuid,
            text=text,
            user_id=db_file.user_id,
        )


@mcp.tool()
def delete_paragraph(file_id: str, paragraph_uuid: str) -> dict[str, Any]:
    """Delete one paragraph from the stored .docx and re-index the document."""
    with db_session() as db:
        db_file = _get_file_or_raise(db, file_id)
        return delete_docx_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=paragraph_uuid,
            user_id=db_file.user_id,
        )


@mcp.prompt()
def document_review_prompt(file_id: str, goal: str = "improve clarity and structure") -> str:
    """Prompt template an MCP host can offer for reviewing one document."""
    return (
        f"Review the document with file_id={file_id}. "
        f"Use the available MCP tools to inspect the document and focus on this goal: {goal}. "
        "When suggesting edits, reference paragraph UUIDs and explain why each change helps."
    )


@mcp.prompt()
def document_editing_prompt(file_id: str, user_request: str) -> str:
    """Prompt template for turning a user request into a tool-using edit workflow."""
    return (
        f"The user wants to modify the document with file_id={file_id}. "
        f"Request: {user_request}. "
        "First read the document or search for relevant sections, then propose or apply edits "
        "using paragraph UUIDs from the MCP tools instead of guessing."
    )


def main() -> None:
    """Run the MCP server using stdio by default."""
    transport = os.getenv("DOCX_MCP_TRANSPORT", "stdio")
    logger.info("Starting DocxProcessAgent MCP server with transport=%s", transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
