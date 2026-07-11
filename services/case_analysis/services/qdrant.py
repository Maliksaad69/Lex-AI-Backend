"""Qdrant vector-database service — retrieves document chunks for a case.

The returned chunks are sorted by (document_name, page, chunk_index) so that
downstream LLM agents receive them in reading order.
"""

import os
from typing import List

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "lexai_documents")


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection = DEFAULT_COLLECTION

    def get_case_chunks(self, case_id: str) -> List[dict]:
        """Scroll through every point belonging to *case_id* in Qdrant."""
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="case_id",
                        match=MatchValue(value=str(case_id)),
                    )
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )

        chunks = []
        for point in points:
            payload = point.payload
            chunks.append(
                {
                    "document_name": payload.get("document_name"),
                    "page": payload.get("page"),
                    "chunk_index": payload.get("chunk_index", 0),
                    "text": payload.get("text", ""),
                }
            )

        chunks.sort(key=lambda x: (x["document_name"], x["page"] or 0, x["chunk_index"]))
        return chunks

    def build_context(self, case_id: str) -> str:
        """Build a human-readable text blob from all document chunks for *case_id*."""
        chunks = self.get_case_chunks(case_id)

        if not chunks:
            return ""

        context_parts = []
        for chunk in chunks:
            context_parts.append(
                f"[Source: {chunk['document_name']} "
                f"Page: {chunk['page']}]\n"
                f"{chunk['text']}\n"
            )
        return "\n".join(context_parts)


qdrant_service = QdrantService()