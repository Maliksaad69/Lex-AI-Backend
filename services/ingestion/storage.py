"""
Qdrant vector storage for document chunks.

Stores document chunks as Qdrant points with:
  - vector: embedding of the chunk text
  - payload: metadata (document_id, filename, chunk_index, text, etc.)

Usage:
    from services.ingestion.storage import QdrantStore

    store = QdrantStore(collection_name="documents")
    store.upsert(chunks, embeddings, metadata)
    results = store.search(query_vector, limit=5)
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


# ── Config ─────────────────────────────────────────────────────────────

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "lexai_documents")


# ── Store ──────────────────────────────────────────────────────────────

class QdrantStore:
    """
    High-level Qdrant wrapper for document chunk storage + search.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        url: str = QDRANT_URL,
        api_key: Optional[str] = QDRANT_API_KEY,
        vector_size: int = 384,  # all-MiniLM-L6-v2 dim
        distance: str = "Cosine",
    ):
        self.collection_name = collection_name
        self.vector_size = vector_size

        client_kwargs = {"url": url}
        if api_key:
            client_kwargs["api_key"] = api_key
        self.client = QdrantClient(**client_kwargs)

        self._ensure_collection(distance)

    # ── Collection Management ──────────────────────────────────────

    def _ensure_collection(self, distance: str):
        """Create collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=distance,
                ),
            )

    def collection_exists(self) -> bool:
        return self.client.collection_exists(self.collection_name)

    # ── Upsert ─────────────────────────────────────────────────────

    def upsert(
        self,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
        batch_size: int = 100,
    ) -> int:
        """
        Insert or update document chunks.

        Each chunk dict should have at minimum:
          - document_id: str
          - chunk_index: int
          - text: str

        Args:
            chunks: List of chunk payload dicts.
            embeddings: List of embedding vectors (same order as chunks).
            batch_size: Upload batch size.

        Returns:
            Number of points inserted.
        """
        if not chunks:
            return 0

        points: list[qmodels.PointStruct] = []
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            payload = {
                **chunk,
                "created_at": chunk.get("created_at", ""),
            }
            points.append(qmodels.PointStruct(
                id=point_id,
                vector=vec,
                payload=payload,
            ))

        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total += len(batch)

        return total

    # ── Search ─────────────────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.0,
        filter_document_id: Optional[str] = None,
        filter_user_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar chunks.

        Args:
            query_vector: Embedding of the query text.
            limit: Max results.
            score_threshold: Minimum similarity score (0-1 for Cosine).
            filter_document_id: Optional: restrict to one document.
            filter_user_id: Optional: restrict to one user.

        Returns:
            List of {id, score, payload}.
        """
        query_filter = None
        conditions = []
        if filter_document_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=filter_document_id),
                )
            )
        if filter_user_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=filter_user_id),
                )
            )
        if conditions:
            query_filter = qmodels.Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    # ── Delete ─────────────────────────────────────────────────────

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
        return 0  # Qdrant doesn't return count on delete

    def delete_by_user(self, user_id: int) -> None:
        """Delete all chunks belonging to a user."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="user_id",
                            match=qmodels.MatchValue(value=user_id),
                        )
                    ]
                )
            ),
        )

    # ── Info ───────────────────────────────────────────────────────

    def count(self) -> int:
        """Total points in the collection."""
        info = self.client.count(collection_name=self.collection_name)
        return info.count

    def collection_info(self) -> dict:
        """Get collection details."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
        }