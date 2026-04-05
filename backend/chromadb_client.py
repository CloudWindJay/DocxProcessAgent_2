"""
ChromaDB client — persistent local vector storage for document chunks.
"""
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
    from overrides import override
except Exception as exc:
    raise RuntimeError(
        "ChromaDB could not be imported. Activate the project environment "
        "(for example: `conda run -p E:\\Agent\\env\\qwen python -m backend.mcp_server`) "
        "or install the missing vector dependencies from requirements.txt."
    ) from exc

from backend.config import settings


class NoOpProductTelemetryClient(ProductTelemetryClient):
    """Disable Chroma product telemetry to avoid PostHog version conflicts."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None


chroma_client = None
chroma_error = None
collection = None
conversation_turn_collection = None


def _empty_query_result() -> dict:
    return {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }


def _get_chroma_client():
    global chroma_client
    global chroma_error

    if chroma_client is not None:
        return chroma_client
    if chroma_error is not None:
        return None

    try:
        chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=Settings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="backend.chromadb_client.NoOpProductTelemetryClient",
                chroma_telemetry_impl="backend.chromadb_client.NoOpProductTelemetryClient",
            ),
        )
        return chroma_client
    except Exception as exc:
        chroma_error = exc
        return None


def _get_document_collection():
    global collection
    if collection is None:
        client = _get_chroma_client()
        if client is None:
            return None
        collection = client.get_or_create_collection(
            name="document_chunks",
            metadata={"hnsw:space": "cosine"},
        )
    return collection


def _get_conversation_turn_collection():
    global conversation_turn_collection
    if conversation_turn_collection is None:
        client = _get_chroma_client()
        if client is None:
            return None
        conversation_turn_collection = client.get_or_create_collection(
            name="conversation_turns",
            metadata={"hnsw:space": "cosine"},
        )
    return conversation_turn_collection


def add_chunks(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """
    Batch-upsert text chunks with metadata into ChromaDB.
    Each chunk should have metadata: {user_id, file_id, paragraph_uuid}
    """
    doc_collection = _get_document_collection()
    if doc_collection is None:
        return

    doc_collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def query_chunks(
    query_text: str,
    user_id: str,
    file_id: str,
    n_results: int = 10,
) -> dict:
    """
    Semantic search with mandatory multi-tenant security filter.
    Only returns chunks belonging to the given user AND file.
    """
    doc_collection = _get_document_collection()
    if doc_collection is None:
        return _empty_query_result()

    results = doc_collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where={
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"file_id": {"$eq": file_id}},
            ]
        },
    )
    return results


def delete_file_chunks(file_id: str) -> None:
    """Remove all chunks for a given file (e.g., on file delete or re-ingest)."""
    doc_collection = _get_document_collection()
    if doc_collection is None:
        return

    doc_collection.delete(where={"file_id": {"$eq": file_id}})


def add_conversation_turn(
    record_id: str,
    document: str,
    metadata: dict,
) -> None:
    """Upsert one conversation turn into the chat memory collection."""
    turn_collection = _get_conversation_turn_collection()
    if turn_collection is None:
        return

    turn_collection.upsert(
        ids=[record_id],
        documents=[document],
        metadatas=[metadata],
    )


def query_conversation_turns(
    query_text: str,
    user_id: str,
    conversation_id: str,
    file_id: str | None,
    n_results: int = 4,
) -> dict:
    """Semantic search over persisted conversation turns."""
    filters = [
        {"user_id": {"$eq": user_id}},
        {"conversation_id": {"$eq": conversation_id}},
    ]
    if file_id:
        filters.append({"file_id": {"$eq": file_id}})

    turn_collection = _get_conversation_turn_collection()
    if turn_collection is None:
        return _empty_query_result()

    return turn_collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where={"$and": filters},
    )


def delete_conversation_turns(conversation_id: str) -> None:
    """Remove all semantic memory for a conversation."""
    turn_collection = _get_conversation_turn_collection()
    if turn_collection is None:
        return

    turn_collection.delete(
        where={"conversation_id": {"$eq": conversation_id}},
    )
