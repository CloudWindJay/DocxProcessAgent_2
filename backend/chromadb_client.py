"""
ChromaDB client — persistent local vector storage for document chunks.
"""
import chromadb
from backend.config import settings

# Initialize persistent client
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

# The single collection for all document chunks.
# Uses ChromaDB's default embedding: all-MiniLM-L6-v2 (local, free).
collection = chroma_client.get_or_create_collection(
    name="document_chunks",
    metadata={"hnsw:space": "cosine"},
)


def add_chunks(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """
    Batch-upsert text chunks with metadata into ChromaDB.
    Each chunk should have metadata: {user_id, file_id, paragraph_uuid}
    """
    collection.upsert(
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
    results = collection.query(
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
    collection.delete(where={"file_id": {"$eq": file_id}})
