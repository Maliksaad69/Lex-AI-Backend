"""Claim Identification Agent — identifies all legal claims / causes of action."""

import logging
from typing import Any
from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import MistralLLM
from services.case_analysis.prompts.claims import build_claim_prompt

logger = logging.getLogger(__name__)


def run_claim_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Identify all legal claims and affirmative defences in *state.raw_context*.

    Returns a list of claim dicts (claim_type, legal_basis, elements).

    On failure, appends to *state.errors* and returns an empty list.
    """
    system_prompt, user_prompt = build_claim_prompt(state["raw_context"])

    try:
        result = MistralLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Claim agent failed: {e}")
        return []

    claims_raw = result.get("claims", [])
    if not claims_raw:
        logger.warning(
            "[claim_agent] LLM returned no claims. Response keys: %s | preview: %s",
            list(result.keys()),
            str(result)[:500],
        )
    return claims_raw