"""Verdict Prediction Service — synthesizes case analysis + jury simulation into executive prediction."""

import logging
from typing import Any

from services.jury_simulation.services.llm import MistralService

logger = logging.getLogger(__name__)
llm = MistralService()


def generate_verdict_prediction(case_data: dict, aggregation: dict, simulation: dict) -> dict:
    """Generate an executive verdict prediction using the LLM.

    Parameters
    ----------
    case_data : dict
        Full case analysis data (facts, parties, claims, evidence, timeline, etc.)
    aggregation : dict
        Aggregated jury simulation results (decision_drivers, evidence_influence, etc.)
    simulation : dict
        Simulation summary (plaintiff_votes, defense_votes, confidence, etc.)

    Returns
    -------
    dict with keys: predicted_winner, plaintiff_win_probability, defense_win_probability,
    prediction_confidence, litigation_risk, settlement_recommendation,
    attorney_recommendations, executive_summary, expected_damages_min,
    expected_damages_max, expected_damages_most_likely, alternative_outcomes, damages_range
    """
    prompt = _build_prediction_prompt(case_data, aggregation, simulation)
    try:
        result = llm.generate_json(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=0.3,
        )
        logger.info("Verdict prediction generated: winner=%s", result.get("predicted_winner", "?"))
        return _validate_result(result)
    except Exception as e:
        logger.error("Verdict prediction generation failed: %s", e)
        return _fallback_prediction(aggregation, simulation)


def _build_prediction_prompt(case_data: dict, aggregation: dict, simulation: dict) -> dict:
    """Build the LLM prompt for verdict prediction."""

    facts = case_data.get("facts", [])
    parties = case_data.get("parties", [])
    claims = case_data.get("claims", [])
    evidence_links = case_data.get("evidence_links", [])
    assessments = case_data.get("assessments", [])
    decision_drivers = aggregation.get("decision_drivers", [])

    plaintiff_name = next((p.get("name", "Plaintiff") for p in parties if p.get("role", "").lower() == "plaintiff"), "Plaintiff")
    defendant_name = next((p.get("name", "Defendant") for p in parties if p.get("role", "").lower() == "defendant"), "Defendant")

    claim_summary = "; ".join(c.get("claim_type", "") for c in claims[:5]) if claims else "Unknown"
    fact_summary = "\n".join(f"• {f.get('statement','')}" for f in facts[:8])
    driver_summary = "\n".join(f"• {d['driver']} ({d['juror_references']} jurors)" for d in decision_drivers[:5])

    system_prompt = """You are a senior litigation strategist. Given case analysis data and jury simulation results,
produce an executive verdict prediction for attorneys. Be concise, practical, and honest about uncertainties.
Focus on actionable intelligence, not rehashing evidence."""

    user_prompt = f"""SYNTHESIZE the following data into an executive verdict prediction.

--- CASE OVERVIEW ---
Plaintiff: {plaintiff_name}
Defendant: {defendant_name}
Claims: {claim_summary}

--- KEY FACTS ---
{fact_summary}

--- JURY SIMULATION RESULTS ---
Vote Split: {simulation.get('plaintiff_votes',0)} plaintiff - {simulation.get('defense_votes',0)} defense
Avg Confidence: {simulation.get('confidence',0):.0%}
Jury Consensus: {aggregation.get('consensus_level','N/A')}
Avg Damages: ${simulation.get('average_damages',0):,.0f}

--- TOP DECISION DRIVERS ---
{driver_summary}

Return valid JSON with this EXACT schema:
{{
  "predicted_winner": "Plaintiff" | "Defense",
  "plaintiff_win_probability": float (0-100),
  "defense_win_probability": float (0-100),
  "prediction_confidence": float (0-100),
  "litigation_risk": "Low" | "Moderate" | "High" | "Very High",
  "settlement_recommendation": "Settlement Recommended" | "Proceed to Trial" | "Further Discovery Recommended",
  "attorney_recommendations": ["str — recommendation with brief rationale"],
  "executive_summary": "str — 2-4 paragraphs explaining why this outcome is likely, primary factors, and confidence level",
  "expected_damages_min": float,
  "expected_damages_max": float,
  "expected_damages_most_likely": float,
  "alternative_outcomes": {{ "plaintiff_victory": float, "defense_victory": float, "hung_jury": float }},
}}

Probabilities must sum to 100. Be honest — don't overstate confidence."""

    return {"system": system_prompt, "user": user_prompt}


def _validate_result(result: dict) -> dict:
    """Ensure all required keys exist with sensible defaults."""
    defaults = {
        "predicted_winner": "Plaintiff",
        "plaintiff_win_probability": 50.0,
        "defense_win_probability": 50.0,
        "prediction_confidence": 50.0,
        "litigation_risk": "Moderate",
        "settlement_recommendation": "Further Discovery Recommended",
        "attorney_recommendations": ["Consider further case development before trial."],
        "executive_summary": "Insufficient data to generate a reliable prediction.",
        "expected_damages_min": 0.0,
        "expected_damages_max": 0.0,
        "expected_damages_most_likely": 0.0,
        "alternative_outcomes": {"plaintiff_victory": 33.0, "defense_victory": 33.0, "hung_jury": 34.0},
    }
    for k, v in defaults.items():
        if k not in result:
            result[k] = v
    return result


def _fallback_prediction(aggregation: dict, simulation: dict) -> dict:
    """Generate a rule-based fallback when LLM prediction fails."""
    pv = simulation.get("plaintiff_votes", 0)
    dv = simulation.get("defense_votes", 0)
    total = pv + dv or 1
    winner = "Plaintiff" if pv > dv else "Defense"
    plaintiff_prob = round(pv / total * 100)
    defense_prob = round(dv / total * 100)
    consensus = aggregation.get("consensus_level", "Moderate Consensus")

    risk_map = {"Strong Consensus": "Low", "Moderate Consensus": "Moderate", "Split Jury": "High", "Highly Divided": "Very High"}
    risk = risk_map.get(consensus, "Moderate")

    settle_map = {"Strong Consensus": "Proceed to Trial", "Moderate Consensus": "Proceed to Trial", "Split Jury": "Settlement Recommended", "Highly Divided": "Settlement Recommended"}
    settle = settle_map.get(consensus, "Further Discovery Recommended")

    avg_d = simulation.get("average_damages", 0)
    damages_min = round(avg_d * 0.5) if avg_d else 0
    damages_max = round(avg_d * 1.5) if avg_d else 0
    damages_likely = avg_d or 0

    return {
        "predicted_winner": winner,
        "plaintiff_win_probability": float(plaintiff_prob),
        "defense_win_probability": float(defense_prob),
        "prediction_confidence": float(simulation.get("confidence", 0.5) * 100),
        "litigation_risk": risk,
        "settlement_recommendation": settle,
        "attorney_recommendations": [
            f"Current jury simulation suggests a {winner.lower()} verdict is most likely.",
            f"Confidence is {consensus.lower()}. Consider {'settlement discussions' if settle == 'Settlement Recommended' else 'trial preparation'}.",
        ],
        "executive_summary": f"Based on the jury simulation of {total} jurors, the predicted outcome favors the {winner.lower()} "
            f"({plaintiff_prob}% plaintiff / {defense_prob}% defense). The jury reached {consensus.lower()}. "
            f"Litigation risk is assessed as {risk.lower()}.",
        "expected_damages_min": float(damages_min),
        "expected_damages_max": float(damages_max),
        "expected_damages_most_likely": float(damages_likely),
        "alternative_outcomes": {
            "plaintiff_victory": float(plaintiff_prob),
            "defense_victory": float(defense_prob),
            "hung_jury": float(max(0, 100 - plaintiff_prob - defense_prob)),
        },
    }