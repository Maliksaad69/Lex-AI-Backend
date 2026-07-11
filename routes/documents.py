"""
Document upload route — full ingestion pipeline + PostgreSQL CRUD.

POST /upload-documents
  Uploads files, runs them through the parse → chunk → embed → store pipeline.
  Saves metadata to PostgreSQL. Supports: PDF, DOCX, PPTX, XLSX, CSV, TXT,
  JSON, HTML, images (OCR), and more.

GET  /documents?case_id=<uuid>
  List documents from PostgreSQL, filtered by case.

GET  /documents/{document_id}/chunks
  Retrieve chunks from Qdrant.

PATCH  /documents/{document_id}
  Update document metadata in PostgreSQL.

DELETE /documents/{document_id}
  Delete from PostgreSQL + all chunks from Qdrant.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlmodel import Session, select

from middleware.user_context import get_user_context
from services.ingestion.pipeline import ingest_document
from services.ingestion.document_ingestor import save_file
from db.session import get_session
from db.models.document import Document
from routes.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Helper: ORM → camelCase dict for frontend ─────────────────────────

def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "userId": doc.user_id,
        "caseId": str(doc.case_id) if doc.case_id else None,
        "filename": doc.filename,
        "fileType": doc.file_type,
        "fileSize": doc.file_size,
        "filePath": doc.file_path,
        "pageCount": doc.page_count,
        "chunksCount": doc.chunks_count,
        "qdrantDocumentId": doc.qdrant_document_id,
        "createdAt": doc.created_at.isoformat() if doc.created_at else None,
        "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ── CREATE: Upload + Ingest ────────────────────────────────────────────

@router.post("/upload-documents")
async def upload_documents(
    files: list[UploadFile] = File(...),
    case_id: UUID = Form(...),
    user: dict = Depends(get_user_context),
    store_in_qdrant: bool = Form(True),
    run_analysis: bool = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Upload one or more documents and run the full ingestion pipeline.

    Each file goes through:
      1. Saved to disk
      2. Parsed (PDF, DOCX, PPTX, XLSX, CSV, TXT, JSON, HTML, images, etc.)
      3. Chunked (sliding window by default)
      4. Embedded (local or OpenAI, auto-detected)
      5. Stored in Qdrant (optional: set store_in_qdrant=false to skip)
      6. Metadata saved to PostgreSQL

    Returns a list of result objects, one per file.
    """
    user_id = user["user_id"]
    results = []

    for file in files:
        doc_id = str(uuid4())

        # Save file to disk
        try:
            file_path = save_file(file)
        except Exception as e:
            results.append({
                "document_id": doc_id,
                "filename": file.filename,
                "error": f"Failed to save file: {e}",
                "chunks_count": 0,
            })
            continue

        # Run pipeline
        try:
            result = ingest_document(
                file_path=str(file_path),
                user_id=user_id,
                document_id=doc_id,
                case_id=case_id,
                chunk_strategy="sliding_window",
                chunk_size=1024,
                chunk_overlap=128,
                store_in_qdrant=store_in_qdrant,
            )
            result["filename"] = file.filename
            result["file_size"] = file_path.stat().st_size if file_path.exists() else 0
            results.append(result)
        except Exception as e:
            results.append({
                "document_id": doc_id,
                "filename": file.filename,
                "error": str(e),
                "chunks_count": 0,
            })

    # ── Auto-trigger analysis if requested ────────────────────────
    if run_analysis and any(r.get("chunks_count", 0) > 0 for r in results):
        background_tasks.add_task(_run_analysis_bg, case_id)

    return results


# ── Background analysis task ────────────────────────────────────────────


def _run_analysis_bg(case_id: UUID) -> None:
    """Run the 7-agent analysis pipeline in a background task."""
    import logging
    logging.basicConfig(level=logging.INFO)
    from services.case_analysis.graph.workflow import run_analysis_pipeline
    from db.session import engine
    from sqlmodel import Session

    with Session(engine) as session:
        try:
            run_analysis_pipeline(case_id, session)
            logging.info("[background] Analysis complete for case %s", case_id)
        except Exception as e:
            logging.exception("[background] Analysis failed for case %s: %s", case_id, e)


# ── READ: List documents (PostgreSQL) ──────────────────────────────────

@router.get("/documents/")
def list_documents(
    case_id: Optional[UUID] = Query(default=None),
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """List documents from PostgreSQL. Filter by ?case_id=<uuid>."""
    stmt = select(Document).where(Document.user_id == user_id)

    if case_id:
        stmt = stmt.where(Document.case_id == case_id)

    stmt = stmt.order_by(Document.created_at.desc())
    docs = session.exec(stmt).all()
    return [_doc_to_dict(d) for d in docs]


# ── READ: Single document ──────────────────────────────────────────────

@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Get a single document by ID."""
    doc = session.get(Document, document_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_dict(doc)


# ── READ: Chunks from Qdrant ───────────────────────────────────────────

@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    user: dict = Depends(get_user_context),
    limit: int = 50,
    offset: int = 0,
):
    """Retrieve chunks for a specific document from Qdrant."""
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels

    user_id = user["user_id"]
    client = QdrantClient(url="http://localhost:6333")
    collection = os.getenv("QDRANT_COLLECTION", "lexai_documents")

    points, next_offset = client.scroll(
        collection_name=collection,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                ),
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id),
                ),
            ]
        ),
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )

    return {
        "document_id": document_id,
        "chunks": [
            {
                "id": p.id,
                "chunk_index": p.payload.get("chunk_index"),
                "text": p.payload.get("text", "")[:500],
                "full_text": p.payload.get("text", ""),
            }
            for p in points
        ],
        "next_offset": next_offset,
        "total_returned": len(points),
    }


# ── UPDATE ──────────────────────────────────────────────────────────────

@router.patch("/documents/{document_id}")
async def update_document(
    document_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Update document metadata fields."""
    doc = session.get(Document, document_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    payload = await request.json()

    field_map = {
        "filename": "filename",
        "fileType": "file_type",
        "fileSize": "file_size",
        "filePath": "file_path",
        "pageCount": "page_count",
        "chunksCount": "chunks_count",
        "qdrantDocumentId": "qdrant_document_id",
    }

    for json_key, db_field in field_map.items():
        if json_key in payload:
            setattr(doc, db_field, payload[json_key])

    doc.updated_at = datetime.utcnow()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _doc_to_dict(doc)


# ── DELETE: PostgreSQL + Qdrant ────────────────────────────────────────

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Delete a document from PostgreSQL AND all its chunks from Qdrant."""
    doc = session.get(Document, document_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete chunks from Qdrant
    from services.ingestion.storage import QdrantStore
    store = QdrantStore(
        collection_name=os.getenv("QDRANT_COLLECTION", "lexai_documents")
    )
    store.delete_by_document(str(document_id))

    # Delete from PostgreSQL
    session.delete(doc)
    session.commit()
    # 204 No Content — no body returned