"""
Full document ingestion pipeline orchestrator.

Ties together: parse → chunk → embed → store (Qdrant) + metadata.

Usage:
    from services.ingestion.pipeline import ingest_document

    result = ingest_document(
        file_path="complaint.pdf",
        user_id=1,
        document_id="doc-123",
        case_id=None,
    )
    # result: {"chunks_stored": 12, "metadata": {...}, "document_id": "doc-123"}
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from services.ingestion.parser import parse, ParsedDocument
from services.ingestion.chunker import chunk, Chunk
from services.ingestion.embedding import EmbeddingModel
from services.ingestion.metadata import extract_metadata
from services.ingestion.storage import QdrantStore

from sqlmodel import Session
from db.session import engine
from db.models.document import Document as DocumentDB

# ── Pipeline ───────────────────────────────────────────────────────────

def ingest_document(
    file_path: str | Path,
    user_id: int,
    document_id: str,
    case_id: Optional[UUID] = None,
    *,
    chunk_strategy: str = "sliding_window",
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
    embedding_provider: Optional[str] = None,
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "lexai_documents"),
    store_in_qdrant: bool = True,
) -> dict[str, Any]:
    """
    Full ingestion pipeline for a single document.

    1. Parse document into text + metadata
    2. Split into chunks
    3. Generate embeddings
    4. Store in Qdrant (optional)
    5. Return result summary

    Args:
        file_path: Path to the document file.
        user_id: Owner user ID.
        document_id: Unique document identifier (UUID string).
        case_id: Optional case this document belongs to.
        chunk_strategy: 'sliding_window', 'semantic', 'recursive', 'fixed'.
        chunk_size: Target characters per chunk.
        chunk_overlap: Overlap between chunks.
        embedding_provider: 'local' or 'openai'. Auto-detect if None.
        qdrant_collection: Qdrant collection name.
        store_in_qdrant: If False, skip Qdrant storage (returns chunks only).

    Returns:
        Dict with: document_id, chunks_count, metadata, text_preview,
                   qdrant_stored (bool), chunk_texts (if not stored).
    """
    file_path = Path(file_path)

    # ── Step 1: Parse ──────────────────────────────────────────────
    parsed: ParsedDocument = parse(file_path)

    if parsed.error and not parsed.text:
        return {
            "document_id": document_id,
            "error": parsed.error,
            "chunks_count": 0,
            "metadata": {},
        }

    # ── Step 2: Extract metadata ───────────────────────────────────
    meta = extract_metadata(
        text=parsed.text,
        parsed_meta=parsed.metadata,
        file_path=str(file_path),
    )

    # ── Step 3: Chunk ──────────────────────────────────────────────
    chunks: list[Chunk] = chunk(
        text=parsed.text,
        strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not chunks:
        return {
            "document_id": document_id,
            "chunks_count": 0,
            "metadata": meta,
            "text_preview": parsed.text[:500] if parsed.text else "",
        }

    # ── Step 4: Embed ──────────────────────────────────────────────
    model = EmbeddingModel(provider=embedding_provider)
    chunk_texts = [c.text for c in chunks]
    embeddings = model.embed(chunk_texts)

    # ── Step 5: Prepare chunk payloads ─────────────────────────────
    chunk_payloads = [
        {
            "document_id": document_id,
            "user_id": user_id,
            "case_id": case_id,
            "chunk_index": c.index,
            "text": c.text,
            "start_char": c.start_char,
            "end_char": c.end_char,
            "filename": meta.get("filename", file_path.name),
            "file_type": parsed.file_type,
            "chunk_strategy": chunk_strategy,
        }
        for c in chunks
    ]

    # ── Step 6: Store in Qdrant (optional) ─────────────────────────
    if store_in_qdrant:
        store = QdrantStore(
            collection_name=qdrant_collection,
            vector_size=model.dim,
        )
        stored_count = store.upsert(chunk_payloads, embeddings)
    else:
        stored_count = 0
    
    # step 7: store in postgresql
    with Session(engine) as session:
       db_doc = DocumentDB(
           id=UUID(document_id),
           user_id=user_id,
           case_id=case_id,
           filename=meta.get("filename", file_path.name),
           file_type=parsed.file_type,
           file_size=file_path.stat().st_size if file_path.exists() else 0,
           file_path=str(file_path),
           page_count=parsed.metadata.get("pages", 0) if parsed.metadata else 0,
           chunks_count=len(chunks),
           qdrant_document_id=document_id if store_in_qdrant else None,
       )
       session.add(db_doc)
       session.commit()


    return {
        "document_id": document_id,
        "chunks_count": len(chunks),
        "stored_in_qdrant": stored_count,
        "metadata": meta,
        "text_preview": parsed.text[:500] if parsed.text else "",
        "embedding_dim": model.dim,
    }