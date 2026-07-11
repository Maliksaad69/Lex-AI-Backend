"""Scoring / Assessment Agent — evaluates the strength of each legal claim."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import GroqLLM
from services.case_analysis.prompts.scoring import build_scoring_prompt


def run_scoring_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Assess the strength of every claim based on evidence, contradictions, and timeline.

    Requires *state.claims*, *state.evidence_links*, *state.contradictions*, and
    *state.timeline* to be populated.

    Returns a list of assessment dicts (claim_index, overall_strength, strengths,
    weaknesses, risk_level, recommendations).

    On failure, appends to *state.errors* and returns an empty list.
    """
    claims = state.get("claims", [])
    evidence_links = state.get("evidence_links", [])
    contradictions = state.get("contradictions", [])
    timeline = state.get("timeline", [])

    if not claims:
        state.setdefault("errors", []).append(
            "Scoring agent skipped: no claims available."
        )
        return []

    system_prompt, user_prompt = build_scoring_prompt(
        claims, evidence_links, contradictions, timeline
    )

    try:
        result = GroqLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,  # slightly higher for strategic recommendations
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Scoring agent failed: {e}")
        return []

    return result.get("assessments", [])