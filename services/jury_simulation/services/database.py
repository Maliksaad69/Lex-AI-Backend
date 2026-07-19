"""Database repository for jury simulation entities."""
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from sqlmodel import Session, select
from db.models.jury_simulation import Simulation, Persona, Vote


# ── Simulation ──────────────────────────────────────────────────────────

def create_simulation(
    session: Session, case_id: UUID, model: Optional[str] = None,
    temperature: Optional[float] = None, juror_count: int = 12,
    pool_spec: Optional[dict] = None,
) -> Simulation:
    sim = Simulation(
        case_id=case_id, status="running", model=model,
        temperature=temperature, juror_count=juror_count, pool_spec=pool_spec or {},
    )
    session.add(sim)
    session.commit()
    session.refresh(sim)
    return sim


def get_simulation(session: Session, simulation_id: UUID) -> Optional[Simulation]:
    return session.get(Simulation, simulation_id)


def get_simulations_for_case(session: Session, case_id: UUID, limit: int = 20) -> List[Simulation]:
    stmt = select(Simulation).where(Simulation.case_id == case_id).order_by(Simulation.created_at.desc()).limit(limit)
    return list(session.exec(stmt).all())


def get_latest_simulation_for_case(session: Session, case_id: UUID) -> Optional[Simulation]:
    stmt = select(Simulation).where(Simulation.case_id == case_id).order_by(Simulation.created_at.desc()).limit(1)
    return session.exec(stmt).first()


def update_simulation(session: Session, simulation_id: UUID, **kwargs: Any) -> Optional[Simulation]:
    sim = session.get(Simulation, simulation_id)
    if not sim:
        return None
    for key, value in kwargs.items():
        if hasattr(sim, key):
            setattr(sim, key, value)
    session.add(sim)
    session.commit()
    session.refresh(sim)
    return sim


def complete_simulation(session: Session, simulation_id: UUID, **kwargs) -> Optional[Simulation]:
    return update_simulation(
        session, simulation_id,
        status="completed", completed_at=datetime.utcnow(), **kwargs,
    )


def delete_simulation(session: Session, simulation_id: UUID) -> bool:
    sim = session.get(Simulation, simulation_id)
    if not sim:
        return False
    for v in session.exec(select(Vote).where(Vote.simulation_id == simulation_id)).all():
        session.delete(v)
    for p in session.exec(select(Persona).where(Persona.simulation_id == simulation_id)).all():
        session.delete(p)
    session.delete(sim)
    session.commit()
    return True


def delete_case_simulations(session: Session, case_id: UUID) -> None:
    """Delete ALL simulations for a case (children first)."""
    for sim in session.exec(select(Simulation).where(Simulation.case_id == case_id)).all():
        for v in session.exec(select(Vote).where(Vote.simulation_id == sim.id)).all():
            session.delete(v)
        for p in session.exec(select(Persona).where(Persona.simulation_id == sim.id)).all():
            session.delete(p)
        session.delete(sim)
    session.commit()


# ── Persona ─────────────────────────────────────────────────────────────

def bulk_create_personas(session: Session, simulation_id: UUID, personas: List[dict]) -> List[Persona]:
    instances = []
    for pdata in personas:
        obj = Persona(
            simulation_id=simulation_id, juror_number=pdata.get("juror_number", 0),
            name=pdata.get("name"), demographics=pdata.get("demographics", {}),
            behavioral_profile=pdata.get("behavioral_profile", {}), biography=pdata.get("biography"),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_personas_for_simulation(session: Session, simulation_id: UUID) -> List[Persona]:
    stmt = select(Persona).where(Persona.simulation_id == simulation_id).order_by(Persona.juror_number)
    return list(session.exec(stmt).all())


# ── Vote ────────────────────────────────────────────────────────────────

def bulk_create_votes(session: Session, simulation_id: UUID, votes: List[dict]) -> List[Vote]:
    instances = []
    for vdata in votes:
        obj = Vote(
            simulation_id=simulation_id, persona_id=vdata["persona_id"],
            verdict=vdata["verdict"], confidence=vdata["confidence"],
            damages=vdata.get("damages"), reasoning=vdata.get("reasoning", ""),
            evidence_used=vdata.get("evidence_used", {}), witness_scores=vdata.get("witness_scores", {}),
            prompt_version=vdata.get("prompt_version"),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_votes_for_simulation(session: Session, simulation_id: UUID) -> List[Vote]:
    stmt = select(Vote).where(Vote.simulation_id == simulation_id).order_by(Vote.created_at)
    return list(session.exec(stmt).all())