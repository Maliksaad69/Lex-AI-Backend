"""Jury Simulation route — triggers and retrieves jury simulations.

POST /cases/{case_id}/jury-simulation    — run a simulation
GET  /cases/{case_id}/jury-simulation     — get latest simulation
GET  /cases/{case_id}/jury-simulations    — list all simulations
GET  /juries/simulations/{sim_id}         — get a specific simulation with details
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlmodel import Session

from db.session import get_session
from db.models.case import Case
from routes.auth import get_current_user

from services.jury_simulation.agents.simulator import run_jury_simulation
from services.jury_simulation.services.database import (
    get_simulation,
    get_simulations_for_case,
    get_latest_simulation_for_case,
    get_personas_for_simulation,
    get_votes_for_simulation,
)
from services.jury_simulation.services.report_pdf import generate_jury_report

logger = logging.getLogger(__name__)

# Separate routers for clean URL structure
cases_router = APIRouter(prefix="/cases", tags=["jury-simulation"])
juries_router = APIRouter(prefix="/juries", tags=["jury-simulation"])
routers = [cases_router, juries_router]


# ── Ownership guard ─────────────────────────────────────────────────────


def _own_case(case_id: UUID, session: Session, user_id: int) -> Case:
    case = session.get(Case, case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ── POST: Run a jury simulation ─────────────────────────────────────────


@cases_router.post("/{case_id}/jury-simulation")
def start_jury_simulation(
    case_id: UUID,
    model: str = Query("mistral-small-latest", description="Mistral model name"),
    temperature: float = Query(0.4, ge=0.0, le=1.0, description="Juror deliberation temperature"),
    juror_count: int = Query(12, ge=1, le=20, description="Number of jurors (default 12)"),
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Run a full jury simulation on a previously analyzed case.

    The simulation pipeline:
      1. Loads existing analysis data (facts, parties, claims, etc.)
      2. Generates a pool specification (demographic targets)
      3. Creates a juror-friendly case stimulus
      4. Generates 12 juror personas
      5. Each juror evaluates the case independently
      6. Votes are aggregated into a verdict split and report
    """
    _own_case(case_id, session, user_id)

    try:
        result = run_jury_simulation(
            case_id=case_id,
            session=session,
            model=model,
            temperature=temperature,
            juror_count=juror_count,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[jury] case=%s — Simulation failed", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Jury simulation failed: {e}",
        )


# ── GET: Retrieve latest simulation ─────────────────────────────────────


@cases_router.get("/{case_id}/jury-simulation")
def get_latest_jury_simulation(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return the most recent simulation for a case, with personas and votes."""
    _own_case(case_id, session, user_id)

    sim = get_latest_simulation_for_case(session, case_id)
    if not sim:
        raise HTTPException(
            status_code=404,
            detail="No jury simulation found for this case. Run one first.",
        )

    return _build_simulation_detail(session, sim)


# ── GET: List all simulations for a case ────────────────────────────────


@cases_router.get("/{case_id}/jury-simulations")
def list_jury_simulations(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return all simulations for a case (summary list, no detail)."""
    _own_case(case_id, session, user_id)

    simulations = get_simulations_for_case(session, case_id)
    return [
        {
            "id": str(s.id),
            "status": s.status,
            "juror_count": s.juror_count,
            "plaintiff_votes": s.plaintiff_votes,
            "defense_votes": s.defense_votes,
            "confidence": s.confidence,
            "average_damages": s.average_damages,
            "summary": s.summary,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in simulations
    ]


# ── GET: Download PDF report ──────────────────────────────────────────


@juries_router.get("/simulations/{sim_id}/report")
def download_jury_report(
    sim_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Download a professionally formatted PDF report for a simulation."""
    sim = get_simulation(session, sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    case = session.get(Case, sim.case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        pdf_bytes = generate_jury_report(sim.case_id, session)
        filename = f"lexai-report-{case.case_name.replace(' ', '_')[:30]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.exception("[jury] report generation failed for sim=%s", sim_id)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


# ── GET: Specific simulation detail ─────────────────────────────────────


@juries_router.get("/simulations/{sim_id}")
def get_simulation_detail(
    sim_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return a specific simulation with full personas and vote details."""
    sim = get_simulation(session, sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Ownership check via the case
    case = session.get(Case, sim.case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return _build_simulation_detail(session, sim)


# ── Shared response builder ─────────────────────────────────────────────


def _build_simulation_detail(session: Session, sim) -> dict:
    """Build the full detail response for a simulation record."""
    personas = get_personas_for_simulation(session, sim.id)
    votes = get_votes_for_simulation(session, sim.id)

    # Build persona-vote pairs
    persona_vote_map = {v.persona_id: v for v in votes}

    jurors = []
    for p in personas:
        v = persona_vote_map.get(p.id)
        jurors.append({
            "persona": {
                "id": str(p.id),
                "juror_number": p.juror_number,
                "name": p.name,
                "demographics": p.demographics,
                "behavioral_profile": p.behavioral_profile,
                "biography": p.biography,
            },
            "vote": {
                "verdict": v.verdict if v else None,
                "confidence": v.confidence if v else None,
                "damages": v.damages if v else None,
                "reasoning": v.reasoning if v else "",
                "evidence_used": v.evidence_used if v else {},
                "witness_scores": v.witness_scores if v else {},
            } if v else None,
        })

    return {
        "simulation": {
            "id": str(sim.id),
            "case_id": str(sim.case_id),
            "status": sim.status,
            "model": sim.model,
            "temperature": sim.temperature,
            "juror_count": sim.juror_count,
            "plaintiff_votes": sim.plaintiff_votes,
            "defense_votes": sim.defense_votes,
            "confidence": sim.confidence,
            "average_damages": sim.average_damages,
            "summary": sim.summary,
            "created_at": sim.created_at.isoformat() if sim.created_at else None,
            "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
        },
        "aggregation": sim.aggregation_data or {},
        "jurors": jurors,
    }