"""
Service B - The AI agent loop.

RAG retrieval + LLM routing + function calling loop.
Uses the unified backend LLM provider layer.
"""
import json
import logging
import re

from sqlalchemy.orm import Session

from backend.chromadb_client import query_chunks
from backend.llm.base import BaseLLMProvider
from backend.llm.factory import get_default_llm_provider
from backend.services.document_tools import (
    append_paragraph,
    delete_paragraph,
    edit_docx_paragraph,
)

logger = logging.getLogger(__name__)

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


def _build_document_context_block(retrieved_chunks: dict) -> str:
    context_parts = []

    if retrieved_chunks and retrieved_chunks.get("documents"):
        docs = retrieved_chunks["documents"][0]
        metas = retrieved_chunks["metadatas"][0]

        for doc_text, meta in zip(docs, metas):
            uuids = meta.get("paragraph_uuids", "")
            context_parts.append(f"[Paragraph UUIDs: {uuids}]\n{doc_text}")

    return "\n\n---\n\n".join(context_parts) if context_parts else "(No relevant content found)"


def _build_read_system_prompt(retrieved_chunks: dict, file_name: str | None = None) -> str:
    context_block = _build_document_context_block(retrieved_chunks)
    file_label = file_name or "the current document"
    return f"""You are an AI document reading assistant. You help users inspect, explain, and summarize their .docx documents.

IMPORTANT RULES:
1. You are in READ-ONLY mode. Never claim that you edited the file.
2. Never expose internal tags such as ParaID, UUID, paragraph_uuid, or [Paragraph UUIDs: ...].
3. When the user asks to show content, return clean readable document text or a concise explanation.
4. If relevant content is not found, say that clearly.
5. If the request is ambiguous, ask a brief clarifying question instead of guessing.

DOCUMENT CONTEXT
The following are relevant sections from the user's document. Internal IDs may appear in the raw context for retrieval, but you must never repeat them in your final answer:

CURRENT DOCUMENT NAME
{file_label}

{context_block}
"""


def _build_edit_system_prompt(retrieved_chunks: dict, file_name: str | None = None) -> str:
    context_block = _build_document_context_block(retrieved_chunks)
    file_label = file_name or "the current document"
    return f"""You are an AI document editing assistant. You help users edit their .docx documents.

You have access to tools that can edit, delete, or append paragraphs in the document.
Each paragraph is identified by a [ParaID: uuid] prefix in the context below.

IMPORTANT RULES:
1. When the user asks to edit content, find the line in the text below and use the exact UUID from its [ParaID: ...] prefix.
2. Always preserve the meaning and tone the user requests.
3. If you need to edit multiple paragraphs, call the tools multiple times.
4. After making edits, confirm what you changed in your response.
5. If the user's request is unclear or you cannot find the relevant paragraph, ask for clarification.
6. Never fabricate a paragraph_uuid; only use UUIDs from the [ParaID: ...] tags in the provided context.

DOCUMENT CONTEXT
The following are relevant sections from the user's document, with inline paragraph IDs:

CURRENT DOCUMENT NAME
{file_label}

{context_block}
"""


def _format_recent_messages(recent_messages: list[dict] | None) -> list[dict]:
    if not recent_messages:
        return []

    formatted = []
    for message in recent_messages:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        formatted.append({"role": role, "content": message.get("content", "")})
    return formatted


def _build_recent_messages_block(recent_messages: list[dict] | None) -> str:
    if not recent_messages:
        return "(none)"

    lines = []
    for message in recent_messages[-6:]:
        role = (message.get("role") or "").upper()
        content = (message.get("content") or "").strip()
        if role and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(none)"


def _build_conversation_summary_block(conversation_summary: str | None) -> str:
    if not conversation_summary:
        return ""
    return f"\n\nCONVERSATION SUMMARY\n{conversation_summary.strip()}\n"


def _build_memory_block(retrieved_memory_turns: list[dict] | None) -> str:
    if not retrieved_memory_turns:
        return ""

    memory_parts = []
    for memory in retrieved_memory_turns:
        meta = memory.get("metadata", {})
        turn_index = meta.get("turn_index", "?")
        memory_parts.append(f"[Turn {turn_index}]\n{memory.get('text', '')}")

    return "\n\nRELEVANT PAST CHAT\n" + "\n\n---\n\n".join(memory_parts) + "\n"


def _extract_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _classify_request_mode(
    user_message: str,
    file_name: str | None = None,
    conversation_summary: str | None = None,
    recent_messages: list[dict] | None = None,
    llm: BaseLLMProvider | None = None,
) -> dict:
    provider = llm or get_default_llm_provider()
    system_prompt = """You classify requests for a .docx document assistant.

Return JSON only with this schema:
{
  \"mode\": \"read\" | \"edit\" | \"uncertain\",
  \"confidence\": 0.0,
  \"reason\": \"short explanation\"
}

Rules:
- read: the user wants to view, inspect, explain, quote, or summarize document content without changing the file.
- edit: the user wants to rewrite, modify, delete, append, shorten, expand, polish, or otherwise change document content.
- uncertain: the intent is too ambiguous to trust.
- If unsure, prefer uncertain.
- Do not answer the document question. Only classify it."""

    user_prompt = (
        f"Current document name:\n{(file_name or 'the current document').strip()}\n\n"
        f"Conversation summary:\n{(conversation_summary or '(none)').strip()}\n\n"
        f"Recent messages:\n{_build_recent_messages_block(recent_messages)}\n\n"
        f"Current user message:\n{user_message.strip()}\n"
    )

    try:
        content = provider.chat_text(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        parsed = _extract_json_object(content)
        if not parsed:
            raise ValueError("Classifier did not return valid JSON.")

        mode = parsed.get("mode", "uncertain")
        if mode not in {"read", "edit", "uncertain"}:
            mode = "uncertain"

        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        reason = str(parsed.get("reason", "")).strip() or "No reason provided."
        result = {
            "mode": mode,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": reason,
        }
        logger.info("Classifier raw result: %s", result)
        return result
    except Exception as exc:
        logger.warning("Request mode classification failed: %s", exc)
        fallback = {
            "mode": "uncertain",
            "confidence": 0.0,
            "reason": "Classifier failed; defaulting to safe read mode.",
        }
        logger.info("Classifier fallback result: %s", fallback)
        return fallback


def _resolve_execution_mode(classification: dict) -> str:
    if classification.get("mode") == "edit":
        return "edit"
    return "read"


def _strip_internal_ids(text: str) -> str:
    cleaned = re.sub(r"\[ParaID:\s*[^\]]+\]\s*", "", text)
    cleaned = re.sub(r"\[Paragraph UUIDs:\s*[^\]]+\]\s*", "", cleaned)
    return cleaned.strip()


def _extract_readable_context(retrieved_chunks: dict) -> str:
    if not retrieved_chunks or not retrieved_chunks.get("documents"):
        return ""

    docs = retrieved_chunks["documents"][0]
    for doc_text in docs:
        cleaned = _strip_internal_ids(doc_text)
        if cleaned:
            return cleaned
    return ""


def _finalize_reply(raw_reply: str | None, retrieved_chunks: dict) -> str:
    reply = (raw_reply or "").strip()
    cleaned_reply = _strip_internal_ids(reply)

    if cleaned_reply and cleaned_reply != reply:
        return cleaned_reply

    if reply and "ParaID" not in reply and "UUID" not in reply:
        return reply

    fallback = _extract_readable_context(retrieved_chunks)
    if fallback:
        return fallback

    return reply or "Done."


def _execute_tool_call(
    tool_name: str,
    tool_args: dict,
    db: Session,
    file_id: str,
    user_id: str,
) -> dict:
    if tool_name == "edit_docx_paragraph":
        return edit_docx_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=tool_args["paragraph_uuid"],
            new_text=tool_args["new_text"],
            user_id=user_id,
        )
    if tool_name == "delete_paragraph":
        return delete_paragraph(
            db=db,
            file_id=file_id,
            paragraph_uuid=tool_args["paragraph_uuid"],
            user_id=user_id,
        )
    if tool_name == "append_paragraph":
        return append_paragraph(
            db=db,
            file_id=file_id,
            after_paragraph_uuid=tool_args["after_paragraph_uuid"],
            text=tool_args["text"],
            user_id=user_id,
        )
    return {"error": f"Unknown tool: {tool_name}"}


def run_agent(
    db: Session,
    user_id: str,
    file_id: str,
    user_message: str,
    file_name: str | None = None,
    llm_provider: BaseLLMProvider | None = None,
    conversation_summary: str | None = None,
    recent_messages: list[dict] | None = None,
    retrieved_memory_turns: list[dict] | None = None,
) -> dict:
    file_updated = False
    llm = llm_provider or get_default_llm_provider()

    classification = _classify_request_mode(
        user_message=user_message,
        file_name=file_name,
        conversation_summary=conversation_summary,
        recent_messages=recent_messages,
        llm=llm,
    )
    execution_mode = _resolve_execution_mode(classification)
    logger.info("Execution mode resolved to: %s", execution_mode)
    logger.info(
        "Agent request classified as %s (confidence=%.2f): %s",
        classification["mode"],
        classification["confidence"],
        classification["reason"],
    )

    retrieved = query_chunks(
        query_text=user_message,
        user_id=user_id,
        file_id=file_id,
        n_results=10,
    )

    if execution_mode == "edit":
        system_prompt = _build_edit_system_prompt(retrieved, file_name=file_name)
    else:
        system_prompt = _build_read_system_prompt(retrieved, file_name=file_name)

    system_prompt += _build_conversation_summary_block(conversation_summary)
    system_prompt += _build_memory_block(retrieved_memory_turns)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_format_recent_messages(recent_messages))
    messages.append({"role": "user", "content": user_message})

    if execution_mode == "read":
        content = llm.chat_text(
            messages=messages,
            temperature=0.2,
        )
        return {
            "reply": _finalize_reply(content, retrieved),
            "file_updated": False,
        }

    for _ in range(10):
        assistant_response = llm.chat_with_tools(
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        if not assistant_response.tool_calls:
            return {
                "reply": _finalize_reply(assistant_response.content, retrieved),
                "file_updated": file_updated,
            }

        messages.append(
            {
                "role": "assistant",
                "content": assistant_response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in assistant_response.tool_calls
                ],
            }
        )

        for tool_call in assistant_response.tool_calls:
            func_name = tool_call.name
            func_args = json.loads(tool_call.arguments)

            logger.info("[Agent] Calling tool: %s with args: %s", func_name, func_args)
            result = _execute_tool_call(
                tool_name=func_name,
                tool_args=func_args,
                db=db,
                file_id=file_id,
                user_id=user_id,
            )
            logger.info("[Agent] Tool result: %s", result)

            if result.get("success"):
                file_updated = True

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    return {
        "reply": "I completed the available edits. Please check the document.",
        "file_updated": file_updated,
    }
