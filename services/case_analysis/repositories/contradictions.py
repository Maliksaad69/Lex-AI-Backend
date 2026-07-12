"""Repository for Contradiction — persists, reads, and deletes contradiction records."""

from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import Contradiction


def save_contradictions(
    session: Session,
    case_id: UUID,
    fact_ids: List[UUID],
    contradictions: List[dict[str, Any]],
) -> List[Contradiction]:
    """Bulk-insert contradictions.

    Parameters
    ----------
    fact_ids : list[UUID]
        Fact IDs in the same order as the *facts* list passed to the agent.
    contradictions : list[dict]
        Contradiction dicts (fact_a_index, fact_b_index, nature, impact).
    """
    instances = []
    for c in contradictions:
        a_idx = c.get("fact_a_index")
        b_idx = c.get("fact_b_index")
        if a_idx is None or b_idx is None:
            continue
        if a_idx >= len(fact_ids) or b_idx >= len(fact_ids):
            continue

        obj = Contradiction(
            case_id=case_id,
            fact_a_id=fact_ids[a_idx],
            fact_b_id=fact_ids[b_idx],
            nature=c.get("nature"),
            impact=c.get("impact"),
        )
        session.add(obj)
        instances.append(obj)

    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_contradictions(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all contradictions for *case_id* as plain dicts."""
    stmt = select(Contradiction).where(Contradiction.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "fact_a_id": str(r.fact_a_id),
            "fact_b_id": str(r.fact_b_id),
            "nature": r.nature,
            "impact": r.impact,
        }
        for r in rows
    ]


def delete_case_contradictions(session: Session, case_id: UUID) -> None:
    """Remove all contradictions belonging to *case_id*."""
    stmt = select(Contradiction).where(Contradiction.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()
