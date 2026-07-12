"""Repository for Party — persists, reads, and deletes party records."""

from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import Party


def save_parties(
    session: Session, case_id: UUID, parties: List[dict[str, Any]]
) -> List[Party]:
    """Bulk-insert parties for a case."""
    instances = []
    for p in parties:
        obj = Party(
            case_id=case_id,
            name=p.get("name", ""),
            role=p.get("role", ""),
            type=p.get("type", "party"),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_parties(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all parties for *case_id* as plain dicts."""
    stmt = select(Party).where(Party.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "role": r.role,
            "type": r.type,
        }
        for r in rows
    ]


def delete_case_parties(session: Session, case_id: UUID) -> None:
    """Remove all parties belonging to *case_id*."""
    stmt = select(Party).where(Party.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()
