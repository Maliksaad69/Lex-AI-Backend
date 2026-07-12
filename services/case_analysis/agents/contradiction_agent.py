"""Contradiction Detection Agent — finds inconsistencies between extracted facts."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import MistralLLM

from services.case_analysis.prompts.contradictions import build_contradiction_prompt


def run_contradiction_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Detect contradictions and inconsistencies between extracted facts.

    Requires *state.facts* to be populated.

    Returns a list of contradiction dicts (fact_a_index, fact_b_index, nature,
    impact).

    On failure, appends to *state.errors* and returns an empty list.
    """
    facts = state.get("facts", [])

    if not facts:
        state.setdefault("errors", []).append(
            "Contradiction agent skipped: no facts available."
        )
        return []

    system_prompt, user_prompt = build_contradiction_prompt(facts)

    try:
        result = MistralLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.15,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Contradiction agent failed: {e}")
        return []

    return result.get("contradictions", [])