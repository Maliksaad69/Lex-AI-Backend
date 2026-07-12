"""Analysis route — triggers the 7-agent case analysis pipeline and returns results.

POST /cases/{case_id}/analyze   — run the full pipeline
GET  /cases/{case_id}/analysis  — retrieve last analysis results
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from db.session import get_session
from db.models.case import Case
from routes.auth import get_current_user

from services.case_analysis.graph.workflow import run_analysis_pipeline
from services.case_analysis.repositories.facts import get_facts
from services.case_analysis.repositories.parties import get_parties
from services.case_analysis.repositories.claims import get_claims
from services.case_analysis.repositories.evidence import get_evidence_links
from services.case_analysis.repositories.timeline import get_timeline
from services.case_analysis.repositories.contradictions import get_contradictions
from services.case_analysis.repositories.scoring import get_assessments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["analysis"])


# ── Ownership guard ─────────────────────────────────────────────────────


def _own_case(case_id: UUID, session: Session, user_id: int) -> Case:
    case = session.get(Case, case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ── POST: Run analysis pipeline ─────────────────────────────────────────


@router.post("/{case_id}/analyze")
def analyze_case(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Run the full 7-agent analysis pipeline on *case_id*.

    The pipeline:
      1. Fetches all document chunks from Qdrant.
      2. Extracts structured facts, parties, claims, evidence links,
         timeline, contradictions, and assessments.
      3. Persists everything to PostgreSQL analysis tables.
      4. Updates ``case.analysis`` with a summary status.

    Returns the full analysis state as JSON.
    """
    _own_case(case_id, session, user_id)

    try:
        state = run_analysis_pipeline(case_id, session)
    except Exception as e:
        logger.exception("[analyze] case=%s pipeline crashed", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline failed: {e}",
        )

    # Update the case record with a status summary
    case = session.get(Case, case_id)
    if case:
        error_count = len(state.get("errors", []))
        case.analysis = (
            f"Complete — {len(state['facts'])} facts, "
            f"{len(state['parties'])} parties, "
            f"{len(state['claims'])} claims, "
            f"{len(state['assessments'])} assessments"
            + (f" ({error_count} errors)" if error_count else "")
        )
        session.add(case)
        session.commit()

    return state


# ── GET: Retrieve stored analysis ───────────────────────────────────────


@router.get("/{case_id}/analysis")
def get_case_analysis(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return the persisted analysis for *case_id* (read-only)."""
    _own_case(case_id, session, user_id)

    facts = get_facts(session, case_id)
    parties = get_parties(session, case_id)
    claims = get_claims(session, case_id)
    evidence_links = get_evidence_links(session, case_id)
    timeline = get_timeline(session, case_id)
    contradictions = get_contradictions(session, case_id)
    assessments = get_assessments(session, case_id)

    return {
        "case_id": str(case_id),
        "facts": facts,
        "parties": parties,
        "claims": claims,
        "evidence_links": evidence_links,
        "timeline": timeline,
        "contradictions": contradictions,
        "assessments": assessments,
        "status": "retrieved",
    }
