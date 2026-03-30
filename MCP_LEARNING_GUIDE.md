# DocxProcessAgent MCP Learning Guide

This project did not originally include MCP. I added a small MCP server in [backend/mcp_server.py](e:/Agent/DocxProcessAgent_2/backend/mcp_server.py) so you can study a realistic example that matches your app.

## Why this MCP type fits your project

Your app already behaves like a document workspace:

- it stores user-owned `.docx` files
- it can read document structure paragraph by paragraph
- it has explicit document-editing functions
- it has semantic search over document chunks

That makes a **workspace/document MCP server** the best learning fit.

This kind of MCP is useful when an external host agent such as Claude Desktop, Codex, or another MCP client needs:

- read-only context about project files and document paragraphs
- approved tools for safe document edits
- reusable prompt templates for common workflows

## What I added

The server exposes all three MCP primitives:

1. Resources

- `docxprocessagent://project/overview`
- `docxprocessagent://files`
- `docxprocessagent://files/{file_id}/paragraphs`

Resources are good for "read this context" style access.

2. Tools

- `list_users`
- `list_files`
- `read_document`
- `search_document`
- `edit_paragraph`
- `append_paragraph`
- `delete_paragraph`

Tools are good for "do work" style actions.

3. Prompts

- `document_review_prompt`
- `document_editing_prompt`

Prompts are optional helpers that MCP hosts can surface as reusable templates.

## How it maps to your existing backend

- `read_document` reads the physical `.docx` and returns paragraph UUID anchors already created by your ingestion pipeline.
- `search_document` uses your existing ChromaDB retrieval.
- `edit_paragraph`, `append_paragraph`, and `delete_paragraph` call your existing document tool functions.

So the MCP server is not a second system. It is a thin protocol layer on top of code you already wrote.

## Important MCP lesson: stdout matters

For stdio MCP servers, `stdout` is reserved for protocol messages.

That means normal `print(...)` debugging can break the MCP connection.

I changed [backend/services/document_tools.py](e:/Agent/DocxProcessAgent_2/backend/services/document_tools.py) to use `logging` instead of `print` for document tool activity. That is a real MCP-specific integration detail worth learning early.

## Install dependencies

Your Python requirements now include:

```txt
mcp[cli]>=1.2.0,<2.0
```

Install with your existing environment, for example:

```powershell
pip install -r requirements.txt
```

## Run the MCP server

From the project root:

```powershell
python -m backend.mcp_server
```

Default transport is `stdio`, which is what most desktop MCP hosts use.

If you want to experiment with HTTP transport for the MCP Inspector:

```powershell
$env:DOCX_MCP_TRANSPORT = "streamable-http"
python -m backend.mcp_server
```

## What to read first in the code

Start here:

- [backend/mcp_server.py](e:/Agent/DocxProcessAgent_2/backend/mcp_server.py)

Then compare it with the app code it wraps:

- [backend/services/ingestion.py](e:/Agent/DocxProcessAgent_2/backend/services/ingestion.py)
- [backend/services/document_tools.py](e:/Agent/DocxProcessAgent_2/backend/services/document_tools.py)
- [backend/chromadb_client.py](e:/Agent/DocxProcessAgent_2/backend/chromadb_client.py)

## Best mental model

Think of MCP as:

- your app logic stays where it is
- MCP adds a standard doorway that outside agents can use
- resources provide context
- tools provide actions
- prompts provide reusable workflows

In your case, MCP is a clean way to expose your document workspace to agent clients without rebuilding your whole backend around a new protocol.
