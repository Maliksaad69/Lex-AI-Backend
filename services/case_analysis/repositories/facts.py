"""Repository for ExtractedFact — persists, reads, and deletes fact records."""

import json
from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import ExtractedFact


def save_facts(session: Session, case_id: UUID, facts: List[dict[str, Any]]) -> List[ExtractedFact]:
    """Bulk-insert extracted facts for a case.

    Returns the list of created SQLModel instances (committed).
    """
    instances = []
    for f in facts:
        obj = ExtractedFact(
            case_id=case_id,
            statement=f.get("statement", ""),
            source_document=f.get("source_document"),
            page_number=f.get("page"),
            importance_score=f.get("importance", 5),
            is_disputed=f.get("disputed", False),
            ai_confidence=f.get("confidence", 0.0),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_facts(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all extracted facts for *case_id* as plain dicts (for agent use)."""
    stmt = select(ExtractedFact).where(ExtractedFact.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "statement": r.statement,
            "source_document": r.source_document,
            "page": r.page_number,
            "importance": r.importance_score,
            "disputed": r.is_disputed,
            "confidence": r.ai_confidence,
            "human_reviewed": r.human_reviewed,
        }
        for r in rows
    ]


def delete_case_facts(session: Session, case_id: UUID) -> None:
    """Remove all facts belonging to *case_id* (used before re-analysis)."""
    stmt = select(ExtractedFact).where(ExtractedFact.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()