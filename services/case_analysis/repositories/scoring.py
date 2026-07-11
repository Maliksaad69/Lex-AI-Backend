"""Repository for Assessment — persists, reads, and deletes assessment/score records."""

import json
from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import Assessment


def save_assessments(
    session: Session,
    case_id: UUID,
    claim_ids: List[UUID],
    assessments: List[dict[str, Any]],
) -> List[Assessment]:
    """Bulk-insert assessments.

    Parameters
    ----------
    claim_ids : list[UUID]
        Claim IDs in the same order as the *claims* list passed to the agent.
    assessments : list[dict]
        Assessment dicts (claim_index, overall_strength, strengths, …).
    """
    instances = []
    for a in assessments:
        claim_idx = a.get("claim_index")
        if claim_idx is None or claim_idx >= len(claim_ids):
            continue

        strengths_raw = a.get("strengths", [])
        weaknesses_raw = a.get("weaknesses", [])
        recommendations_raw = a.get("recommendations", [])

        obj = Assessment(
            case_id=case_id,
            claim_id=claim_ids[claim_idx],
            overall_strength=a.get("overall_strength", 5),
            strengths=json.dumps(strengths_raw) if isinstance(strengths_raw, list) else str(strengths_raw),
            weaknesses=json.dumps(weaknesses_raw) if isinstance(weaknesses_raw, list) else str(weaknesses_raw),
            risk_level=a.get("risk_level", "medium"),
            recommendations=json.dumps(recommendations_raw) if isinstance(recommendations_raw, list) else str(recommendations_raw),
        )
        session.add(obj)
        instances.append(obj)

    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_assessments(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all assessments for *case_id* as plain dicts (lists deserialised)."""
    stmt = select(Assessment).where(Assessment.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "claim_id": str(r.claim_id),
            "overall_strength": r.overall_strength,
            "strengths": json.loads(r.strengths) if r.strengths else [],
            "weaknesses": json.loads(r.weaknesses) if r.weaknesses else [],
            "risk_level": r.risk_level,
            "recommendations": json.loads(r.recommendations) if r.recommendations else [],
        }
        for r in rows
    ]


def delete_case_assessments(session: Session, case_id: UUID) -> None:
    """Remove all assessments belonging to *case_id*."""
    stmt = select(Assessment).where(Assessment.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()