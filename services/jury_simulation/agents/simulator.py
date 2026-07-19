"""Simulation Runner — the main orchestrator for the jury simulation pipeline.

Workflow:
  1. Create Simulation record (status='running')
  2. Load existing case analysis from DB (facts, parties, claims, etc.)
  3. Generate pool specification (demographic targets)
  4. Generate case stimulus (juror-friendly summary)
  5. Generate 12 juror personas
  6. Run 12 juror agents in parallel
  7. Store personas and votes
  8. Aggregate results
  9. Mark simulation as completed
"""

import logging
import time
from typing import Any, List
from uuid import UUID

from sqlmodel import Session

from db.models.jury_simulation import Simulation
from services.jury_simulation.services.database import (
    create_simulation,
    complete_simulation,
    delete_case_simulations,
    bulk_create_personas,
    bulk_create_votes,
)
from services.jury_simulation.services.llm import MistralService
from services.jury_simulation.agents.persona_generator import (
    generate_pool_specification,
    generate_juror_personas,
)
from services.jury_simulation.agents.jury_agent import run_juror_agent
from services.jury_simulation.agents.agregator import aggregate_votes
from services.jury_simulation.prompts.jury_prompt import build_stimulus_prompt
from services.jury_simulation.services.verdict_prediction import generate_verdict_prediction

# Reuse the same case-analysis repositories to fetch existing analysis
from services.case_analysis.repositories.facts import get_facts
from services.case_analysis.repositories.parties import get_parties
from services.case_analysis.repositories.claims import get_claims
from services.case_analysis.repositories.evidence import get_evidence_links
from services.case_analysis.repositories.timeline import get_timeline
from services.case_analysis.repositories.contradictions import get_contradictions
from services.case_analysis.repositories.scoring import get_assessments

logger = logging.getLogger(__name__)

llm = MistralService()


def run_jury_simulation(
    case_id: UUID,
    session: Session,
    model: str = "mistral-small-latest",
    temperature: float = 0.4,
    juror_count: int = 12,
) -> dict:
    """Execute the full jury simulation pipeline for *case_id*.

    Parameters
    ----------
    case_id : UUID
        The case to simulate.
    session : Session
        Active database session.
    model : str
        Mistral model name.
    temperature : float
        Reasoning temperature for juror agents.
    juror_count : int
        Number of juror agents (default 12).

    Returns
    -------
    dict with the complete simulation state (matches the API response schema).
    """
    # ── 1. Delete any previous simulations for this case ────────────
    logger.info("[jury-sim] case=%s — Deleting previous simulation data", case_id)
    delete_case_simulations(session, case_id)

    # ── 2. Create simulation record ──────────────────────────────────
    logger.info("[jury-sim] case=%s — Creating simulation record", case_id)
    simulation: Simulation = create_simulation(
        session,
        case_id=case_id,
        model=model,
        temperature=temperature,
        juror_count=juror_count,
    )
    sim_id = simulation.id
    logger.info("[jury-sim] sim=%s — Simulation record created", sim_id)

    try:
        # ── 3. Retrieve existing case analysis ──────────────────────────
        logger.info("[jury-sim] sim=%s — Loading case analysis data", sim_id)
        case_data: dict[str, Any] = {
            "case_id": str(case_id),
            "facts": get_facts(session, case_id),
            "parties": get_parties(session, case_id),
            "claims": get_claims(session, case_id),
            "evidence_links": get_evidence_links(session, case_id),
            "timeline": get_timeline(session, case_id),
            "contradictions": get_contradictions(session, case_id),
            "assessments": get_assessments(session, case_id),
        }

        fact_count = len(case_data["facts"])
        logger.info(
            "[jury-sim] sim=%s — Loaded %d facts, %d parties, %d claims",
            sim_id,
            fact_count,
            len(case_data["parties"]),
            len(case_data["claims"]),
        )

        if fact_count == 0:
            raise ValueError(
                "No analysis data found. Run the case analysis pipeline first."
            )

        # ── 3. Generate pool specification ──────────────────────────
        logger.info("[jury-sim] sim=%s — Generating pool specification", sim_id)
        pool_spec = generate_pool_specification(case_data)

        # Persist pool_spec on the simulation record
        simulation.pool_spec = pool_spec
        session.add(simulation)
        session.commit()

        # ── 4. Generate case stimulus ───────────────────────────────
        logger.info("[jury-sim] sim=%s — Generating case stimulus", sim_id)
        stimulus_prompt = build_stimulus_prompt(case_data)
        stimulus = llm.generate_json(
            system_prompt=stimulus_prompt["system"],
            user_prompt=stimulus_prompt["user"],
            temperature=0.3,
        )
        logger.info("[jury-sim] sim=%s — Stimulus generated (%d chars)", sim_id, len(stimulus.get("stimulus", "")))

        # Persist stimulus on the simulation record
        simulation.stimulus = stimulus.get("stimulus", "")
        session.add(simulation)
        session.commit()

        # ── 5. Generate juror personas ──────────────────────────────
        logger.info("[jury-sim] sim=%s — Generating %d juror personas", sim_id, juror_count)
        personas = generate_juror_personas(pool_spec, case_data, count=juror_count)
        logger.info("[jury-sim] sim=%s — Generated %d personas", sim_id, len(personas))

        # Restructure personas: flatten top-level fields into demographics
        for p in personas:
            p["demographics"] = {
                "age": p.pop("age", None),
                "gender": p.pop("gender", None),
                "education": p.pop("education", None),
                "occupation": p.pop("occupation", None),
            }

        # Persist personas
        db_personas = bulk_create_personas(session, sim_id, personas)
        logger.info("[jury-sim] sim=%s — Persisted %d personas", sim_id, len(db_personas))

        # ── 6. Run juror agents ─────────────────────────────────────
        logger.info("[jury-sim] sim=%s — Running %d juror agents", sim_id, juror_count)
        votes: List[dict] = []
        for i, (persona_dict, db_persona) in enumerate(zip(personas, db_personas)):
            logger.info(
                "[jury-sim] sim=%s — Juror %d/%d: %s",
                sim_id,
                i + 1,
                juror_count,
                persona_dict.get("name", "?"),
            )
            vote = run_juror_agent(persona_dict, stimulus, temperature=temperature)
            vote["persona_id"] = db_persona.id
            votes.append(vote)
            # Small delay to avoid rate limits
            if i < juror_count - 1:
                time.sleep(1.5)

        # ── 7. Persist votes ────────────────────────────────────────
        db_votes = bulk_create_votes(session, sim_id, votes)
        logger.info("[jury-sim] sim=%s — Persisted %d votes", sim_id, len(db_votes))

        # ── 8. Aggregate results ────────────────────────────────────
        logger.info("[jury-sim] sim=%s — Aggregating results", sim_id)
        aggregated = aggregate_votes(votes, personas)

        # ── 9. Generate verdict prediction ─────────────────────────────
        logger.info("[jury-sim] sim=%s — Generating verdict prediction", sim_id)
        sim_summary = {"plaintiff_votes": aggregated["plaintiff_votes"], "defense_votes": aggregated["defense_votes"],
                       "confidence": aggregated["confidence"], "average_damages": aggregated["average_damages"]}
        verdict_prediction = generate_verdict_prediction(case_data, aggregated, sim_summary)
        aggregated["verdict_prediction"] = verdict_prediction
        logger.info("[jury-sim] sim=%s — Verdict prediction: %s", sim_id, verdict_prediction.get("predicted_winner", "?"))

        # ── 10. Mark simulation as completed and persist aggregation ──
        complete_simulation(
            session,
            sim_id,
            plaintiff_votes=aggregated["plaintiff_votes"],
            defense_votes=aggregated["defense_votes"],
            confidence=aggregated["confidence"],
            average_damages=aggregated["average_damages"],
            summary=aggregated["summary"],
        )
        # Persist full aggregation data for GET endpoint
        simulation.aggregation_data = aggregated
        session.add(simulation)
        session.commit()
        logger.info("[jury-sim] sim=%s — Simulation completed", sim_id)

        # ── 11. Build response ──────────────────────────────────────
        return _build_response(simulation, case_data, personas, db_personas, votes, db_votes, aggregated)

    except Exception as e:
        logger.exception("[jury-sim] sim=%s — Simulation failed: %s", sim_id, e)
        # Mark as failed
        complete_simulation(
            session,
            sim_id,
            summary=f"Simulation failed: {e}",
        )
        # Re-raise so the API route can set the correct status code
        raise


def _build_response(
    simulation: Simulation,
    case_data: dict,
    persona_dicts: List[dict],
    db_personas: list,
    vote_dicts: List[dict],
    db_votes: list,
    aggregated: dict,
) -> dict:
    """Build the full API response dict from simulation state."""
    # Map persona IDs to vote data
    persona_votes = []
    for p_dict, db_p in zip(persona_dicts, db_personas):
        matching_vote = next(
            (v for v in vote_dicts if v.get("persona_id") == db_p.id),
            None,
        )
        persona_votes.append({
            "persona": {
                "id": str(db_p.id),
                "juror_number": p_dict.get("juror_number"),
                "name": p_dict.get("name"),
                "age": p_dict.get("age"),
                "gender": p_dict.get("gender"),
                "education": p_dict.get("education"),
                "occupation": p_dict.get("occupation"),
                "biography": p_dict.get("biography"),
                "behavioral_profile": p_dict.get("behavioral_profile", {}),
            },
            "vote": {
                "verdict": matching_vote.get("verdict") if matching_vote else "unknown",
                "confidence": matching_vote.get("confidence", 0) if matching_vote else 0,
                "damages": matching_vote.get("damages") if matching_vote else None,
                "reasoning": matching_vote.get("reasoning", "") if matching_vote else "",
                "evidence_referenced": matching_vote.get("evidence_referenced", []) if matching_vote else [],
                "witness_credibility": matching_vote.get("witness_credibility", {}) if matching_vote else {},
                "key_doubts": matching_vote.get("key_doubts", "") if matching_vote else "",
            } if matching_vote else None,
        })

    return {
        "simulation": {
            "id": str(simulation.id),
            "case_id": str(simulation.case_id),
            "status": simulation.status,
            "model": simulation.model,
            "temperature": simulation.temperature,
            "juror_count": simulation.juror_count,
            "plaintiff_votes": aggregated["plaintiff_votes"],
            "defense_votes": aggregated["defense_votes"],
            "confidence": aggregated["confidence"],
            "average_damages": aggregated["average_damages"],
            "summary": aggregated["summary"],
            "created_at": simulation.created_at.isoformat() if simulation.created_at else None,
            "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
        },
        "aggregation": {
            "consensus_level": aggregated.get("consensus_level", ""),
            "jury_deliberation_summary": aggregated.get("jury_deliberation_summary", ""),
            "decision_drivers": aggregated.get("decision_drivers", []),
            "damages_distribution": aggregated.get("damages_distribution"),
            "confidence_distribution": aggregated.get("confidence_distribution", []),
            "evidence_influence": aggregated.get("evidence_influence", []),
            "witness_credibility_ranking": aggregated.get("witness_credibility_ranking", []),
            "common_themes": aggregated.get("common_themes", []),
        },
        "jurors": persona_votes,
        "case_data": {
            "facts_count": len(case_data.get("facts", [])),
            "parties_count": len(case_data.get("parties", [])),
            "claims_count": len(case_data.get("claims", [])),
            "timeline_count": len(case_data.get("timeline", [])),
        },
    }