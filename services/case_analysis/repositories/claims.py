"""Repository for Claim — persists, reads, and deletes claim records."""

import json
from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import Claim


def save_claims(session: Session, case_id: UUID, claims: List[dict[str, Any]]) -> List[Claim]:
    """Bulk-insert claims for a case.

    The *elements* field (a list) is serialised to JSON for storage.
    """
    instances = []
    for c in claims:
        elements_raw = c.get("elements", [])
        obj = Claim(
            case_id=case_id,
            claim_type=c.get("claim_type", ""),
            legal_basis=c.get("legal_basis"),
            elements=json.dumps(elements_raw) if isinstance(elements_raw, list) else str(elements_raw),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_claims(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all claims for *case_id* as plain dicts (elements deserialised)."""
    stmt = select(Claim).where(Claim.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "claim_type": r.claim_type,
            "legal_basis": r.legal_basis,
            "elements": json.loads(r.elements) if r.elements else [],
        }
        for r in rows
    ]


def delete_case_claims(session: Session, case_id: UUID) -> None:
    """Remove all claims belonging to *case_id*."""
    stmt = select(Claim).where(Claim.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()