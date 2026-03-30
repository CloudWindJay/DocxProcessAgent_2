"""
Service B — The AI Agent Loop.

RAG retrieval + Qwen LLM with function calling (tool use) loop.
Uses the OpenAI-compatible DashScope API.
"""
import json
from openai import OpenAI
from sqlalchemy.orm import Session

from backend.config import settings
from backend.chromadb_client import query_chunks
from backend.services.document_tools import (
    edit_docx_paragraph,
    delete_paragraph,
    append_paragraph,
)

# Initialize OpenAI-compatible client pointing at DashScope
llm_client = OpenAI(
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.DASHSCOPE_BASE_URL,
)

# ── Tool Definitions (OpenAI function-calling format) ────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "edit_docx_paragraph",
            "description": (
                "Edit the text of a specific paragraph in the .docx document. "
                "Use this when the user wants to change, rewrite, shorten, expand, "
                "or modify existing text. The paragraph is identified by its UUID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paragraph_uuid": {
                        "type": "string",
                        "description": "The UUID of the paragraph to edit.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text content to replace the paragraph with.",
                    },
                },
                "required": ["paragraph_uuid", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_paragraph",
            "description": (
                "Delete a specific paragraph from the .docx document. "
                "Use this when the user wants to remove a section or paragraph."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paragraph_uuid": {
                        "type": "string",
                        "description": "The UUID of the paragraph to delete.",
                    },
                },
                "required": ["paragraph_uuid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_paragraph",
            "description": (
                "Add a new paragraph after a specific existing paragraph. "
                "Use this when the user wants to insert new content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "after_paragraph_uuid": {
                        "type": "string",
                        "description": "The UUID of the paragraph after which to insert new text.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The text content of the new paragraph.",
                    },
                },
                "required": ["after_paragraph_uuid", "text"],
            },
        },
    },
]


def _build_system_prompt(retrieved_chunks: dict) -> str:
    """
    Build the system prompt with RAG context.
    Includes the retrieved document chunks and their paragraph UUIDs
    so the LLM knows which paragraphs to edit.
    """
    context_parts = []

    if retrieved_chunks and retrieved_chunks.get("documents"):
        docs = retrieved_chunks["documents"][0]  # First query results
        metas = retrieved_chunks["metadatas"][0]

        for doc_text, meta in zip(docs, metas):
            uuids = meta.get("paragraph_uuids", "")
            context_parts.append(
                f"[Paragraph UUIDs: {uuids}]\n{doc_text}"
            )

    context_block = "\n\n---\n\n".join(context_parts) if context_parts else "(No relevant content found)"

    return f"""You are an AI document editing assistant. You help users edit their .docx documents.

You have access to tools that can edit, delete, or append paragraphs in the document.
Each paragraph is identified by a [ParaID: uuid] prefix in the context below.

IMPORTANT RULES:
1. When the user asks to edit content, find the line in the text below and use the EXACT UUID from its [ParaID: ...] prefix.
2. Always preserve the meaning and tone the user requests.
3. If you need to edit multiple paragraphs, call the tools multiple times.
4. After making edits, confirm what you changed in your response.
5. If the user's request is unclear or you can't find the relevant paragraph, ask for clarification.
6. NEVER fabricate a paragraph_uuid — only use UUIDs from the [ParaID: ...] tags in the context provided below.

── DOCUMENT CONTEXT ──
The following are relevant sections from the user's document, with inline paragraph IDs:

{context_block}
"""


def _execute_tool_call(
    tool_name: str,
    tool_args: dict,
    db: Session,
    file_id: str,
    user_id: str,
) -> dict:
    """Execute a tool call and return the result."""
    if tool_name == "edit_docx_paragraph":
        return edit_docx_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=tool_args["paragraph_uuid"],
            new_text=tool_args["new_text"],
            user_id=user_id,
        )
    elif tool_name == "delete_paragraph":
        return delete_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=tool_args["paragraph_uuid"],
            user_id=user_id,
        )
    elif tool_name == "append_paragraph":
        return append_paragraph(
            db=db,
            file_id=file_id,
            after_paragraph_uuid=tool_args["after_paragraph_uuid"],
            text=tool_args["text"],
            user_id=user_id,
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def run_agent(
    db: Session,
    user_id: str,
    file_id: str,
    user_message: str,
) -> dict:
    """
    Full agent loop:
    1. RAG query to get relevant chunks
    2. Build messages with system prompt + context
    3. Call Qwen with tools
    4. Execute tool calls in a loop until final text response
    5. Return {reply, file_updated}
    """
    file_updated = False

    # ── 1. RAG Retrieval ──
    retrieved = query_chunks(
        query_text=user_message,
        user_id=user_id,
        file_id=file_id,
        n_results=10,
    )

    # ── 2. Build messages ──
    system_prompt = _build_system_prompt(retrieved)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # ── 3. Agent Loop (max 10 iterations to prevent infinite loops) ──
    for iteration in range(10):
        response = llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # If no tool calls, we have our final response
        if not assistant_message.tool_calls:
            return {
                "reply": assistant_message.content or "Done.",
                "file_updated": file_updated,
            }

        # ── 4. Execute tool calls ──
        # Add assistant message (with tool_calls) to history
        messages.append({
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_message.tool_calls
            ],
        })

        for tool_call in assistant_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"🛠️ [Agent] Calling tool: {func_name} with args: {func_args}")
            
            result = _execute_tool_call(
                tool_name=func_name,
                tool_args=func_args,
                db=db,
                file_id=file_id,
                user_id=user_id,
            )

            print(f"✅ [Agent] Tool Result: {result}")
            
            if result.get("success"):
                file_updated = True

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    # If we hit max iterations
    return {
        "reply": "I completed the available edits. Please check the document.",
        "file_updated": file_updated,
    }
