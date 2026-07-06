"""
Qdrant service — high-level operations for the LexAI application.

Re-exports from services.ingestion.storage for convenience, plus
application-specific helpers (e.g., legal document search with filters).
"""

import os

from services.ingestion.storage import QdrantStore
from services.ingestion.embedding import embed

_COLLECTION = os.getenv("QDRANT_COLLECTION", "lexai_documents")


def search_legal_documents(
    query: str,
    user_id: int,
    case_id: str | None = None,
    limit: int = 10,
    score_threshold: float = 0.5,
) -> list[dict]:
    """
    Search documents semantically and return relevant chunks.

    Args:
        query: Natural language query (e.g., "breach of contract damages").
        user_id: Restrict results to this user.
        case_id: Optional case filter (UUID string).
        limit: Max results.
        score_threshold: Minimum similarity score.

    Returns:
        List of {id, score, payload} dicts.
    """
    store = QdrantStore(collection_name=_COLLECTION)
    query_vec = embed([query])[0]

    return store.search(
        query_vector=query_vec,
        limit=limit,
        score_threshold=score_threshold,
        filter_user_id=user_id,
        filter_document_id=None,
    )


def get_document_stats(user_id: int) -> dict:
    """Get document/chunk counts for a user."""
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels

    client = QdrantClient(url="http://localhost:6333")

    try:
        count_result = client.count(
            collection_name=_COLLECTION,
            count_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="user_id",
                        match=qmodels.MatchValue(value=user_id),
                    )
                ]
            ),
        )
        total_chunks = count_result.count
    except Exception:
        total_chunks = 0

    return {
        "user_id": user_id,
        "total_chunks": total_chunks,
    }