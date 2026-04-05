# DocxProcessAgent_2

AI-powered document workspace for uploading, previewing, chatting about, and editing `.docx` files.

## Features

- User authentication with JWT
- Upload and preview `.docx` files
- File-scoped chat conversations
- Read-only vs edit request routing with LLM classification
- Paragraph-level `.docx` editing through tool calling
- RAG over document chunks with ChromaDB
- Conversation persistence in MySQL
- Conversation semantic memory in ChromaDB
- Per-user LLM settings in the UI
  - `Qwen`
  - `ChatGPT`
  - `Gemini`
  - environment key or user-supplied key

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PyMySQL
- Frontend: React, Vite, Axios
- Document preview: `docx-preview`
- Vector store: ChromaDB
- Document processing: `python-docx`, `tiktoken`
- LLM runtime: custom provider layer with OpenAI-compatible and Gemini adapters

## Project Structure

```text
backend/
  routers/              API routes
  services/             agent loop, conversation memory, docx tools
  llm/                  unified LLM provider layer
  chromadb_client.py    vector storage and retrieval
  models.py             SQLAlchemy models
  main.py               FastAPI entrypoint

frontend/
  src/components/       UI panels and dialogs
  src/api/client.js     API client helpers

uploads/                uploaded files (gitignored)
chroma_data/            local vector store data (gitignored)
```

## Current Workflow

1. A user uploads a `.docx` file.
2. The backend stores the file, adds paragraph bookmarks, chunks the text, and indexes it in ChromaDB.
3. The user opens a file-scoped conversation.
4. Each message is classified as:
   - `read`
   - `edit`
   - `uncertain` -> safely downgraded to `read`
5. Read requests return document content or summaries.
6. Edit requests may call tools to modify the real `.docx` file and then reindex it.

## Environment Setup

Copy `.env.example` to `.env` and fill in your values.

Example variables:

```env
DATABASE_URL=mysql+pymysql://<user>:<password>@127.0.0.1:3307/docx_agent

LLM_PROVIDER=qwen
LLM_API_KEY=your_api_key_here
LLM_MODEL=qwen-plus

# Optional provider-specific settings
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

CHROMA_PERSIST_DIR=./chroma_data
UPLOAD_DIR=./uploads

JWT_SECRET_KEY=replace_me
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

Notes:

- `.env` is ignored by Git.
- `uploads/` and `chroma_data/` are ignored by Git.
- Users can also override the backend environment key from the UI in **Settings**.

## Install

### Backend

```powershell
pip install -r requirements.txt
```

### Frontend

```powershell
cd frontend
npm install
cd ..
```

## Run

### Option 1: use `start.bat`

```powershell
start.bat
```

This starts:

- FastAPI on `http://localhost:8000`
- Vite on `http://localhost:5173`

### Option 2: start manually

Backend:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

## API Highlights

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/upload`
- `GET /api/files`
- `GET /api/files/{file_id}/download`
- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}/messages`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/settings/llm`
- `PATCH /api/settings/llm`

FastAPI docs:

- `http://localhost:8000/docs`

## Database Notes

This project currently uses `Base.metadata.create_all(...)` plus a small startup bootstrap for newly added user LLM settings columns.

It does **not** use Alembic migrations yet.

For a larger production project, adding Alembic would be a good next step.

## Security Notes

Before publishing or deploying:

- do not commit `.env`
- do not commit real API keys
- do not commit `uploads/`
- do not commit `chroma_data/`
- replace development JWT/database secrets
- consider encrypting user-saved custom API keys before storing them

## Status

This project is actively evolving. The current focus is:

- stable `.docx` chat/edit workflow
- multi-provider LLM support
- cleaner architecture for future PDF / MCP / skill expansion
