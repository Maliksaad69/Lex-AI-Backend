"""Claim Identification Agent — identifies all legal claims / causes of action."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import GroqLLM
from services.case_analysis.prompts.claims import build_claim_prompt


def run_claim_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Identify all legal claims and affirmative defences in *state.raw_context*.

    Returns a list of claim dicts (claim_type, legal_basis, elements).

    On failure, appends to *state.errors* and returns an empty list.
    """
    system_prompt, user_prompt = build_claim_prompt(state["raw_context"])

    try:
        result = GroqLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Claim agent failed: {e}")
        return []

    return result.get("claims", [])