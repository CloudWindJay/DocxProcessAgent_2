"""
DocxProcessAgent — FastAPI Application Entry Point.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import engine, Base
from backend.schema_bootstrap import ensure_user_llm_settings_columns
from backend.routers import auth_router, upload, files, agent, conversations, settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ──
    # Create all database tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created.")
    ensure_user_llm_settings_columns(engine)
    print("✅ User LLM settings columns ready.")

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    print(f"✅ Upload directory ready: {settings.UPLOAD_DIR}")

    # Ensure ChromaDB directory exists
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    print(f"✅ ChromaDB directory ready: {settings.CHROMA_PERSIST_DIR}")

    yield

    # ── Shutdown ──
    print("👋 Application shutting down.")


app = FastAPI(
    title="DocxProcessAgent",
    description="AI-powered .docx document processing and editing platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(auth_router.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(agent.router)
app.include_router(conversations.router)
app.include_router(settings_router.router)


@app.get("/")
def root():
    return {
        "app": "DocxProcessAgent",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
