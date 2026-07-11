"""Repository for EvidenceLink — persists, reads, and deletes evidence-link records."""

from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import EvidenceLink


def save_evidence_links(
    session: Session,
    claim_ids: List[UUID],
    fact_ids: List[UUID],
    links: List[dict[str, Any]],
) -> List[EvidenceLink]:
    """Bulk-insert evidence links.

    Parameters
    ----------
    claim_ids : list[UUID]
        Claim IDs in the same order as the *claims* list passed to the agent.
    fact_ids : list[UUID]
        Fact IDs in the same order as the *facts* list passed to the agent.
    links : list[dict]
        Evidence-link dicts from the agent (claim_index, fact_index, …).
    """
    instances = []
    for link in links:
        claim_idx = link.get("claim_index")
        fact_idx = link.get("fact_index")
        if claim_idx is None or fact_idx is None:
            continue
        if claim_idx >= len(claim_ids) or fact_idx >= len(fact_ids):
            continue

        obj = EvidenceLink(
            claim_id=claim_ids[claim_idx],
            fact_id=fact_ids[fact_idx],
            relationship=link.get("relationship", "supports"),
            weight_score=link.get("weight_score", 5),
            rationale=link.get("rationale"),
        )
        session.add(obj)
        instances.append(obj)

    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_evidence_links(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all evidence links for *case_id* by joining through claims table."""
    # evidence_links links to claims, which link to cases — join through
    from db.models.analysis import Claim

    stmt = (
        select(EvidenceLink)
        .join(Claim, EvidenceLink.claim_id == Claim.id)
        .where(Claim.case_id == case_id)
    )
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "claim_id": str(r.claim_id),
            "fact_id": str(r.fact_id),
            "relationship": r.relationship,
            "weight_score": r.weight_score,
            "rationale": r.rationale,
        }
        for r in rows
    ]


def delete_case_evidence_links(session: Session, case_id: UUID) -> None:
    """Remove all evidence links for claims belonging to *case_id*."""
    from db.models.analysis import Claim

    subq = select(Claim.id).where(Claim.case_id == case_id)
    stmt = select(EvidenceLink).where(EvidenceLink.claim_id.in_(subq))
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()