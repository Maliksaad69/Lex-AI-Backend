"""Evidence Linkage Agent — connects facts to the claims they support or undermine."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import MistralLLM

from services.case_analysis.prompts.evidence import build_evidence_prompt


def run_evidence_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Link facts to claims with relationship type, weight score, and rationale.

    Requires *state.facts* and *state.claims* to be populated first.

    Returns a list of evidence-link dicts (claim_index, fact_index, relationship,
    weight_score, rationale).

    On failure, appends to *state.errors* and returns an empty list.
    """
    facts = state.get("facts", [])
    claims = state.get("claims", [])

    if not facts or not claims:
        state.setdefault("errors", []).append(
            "Evidence agent skipped: facts or claims missing."
        )
        return []

    system_prompt, user_prompt = build_evidence_prompt(facts, claims)

    try:
        result = MistralLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Evidence agent failed: {e}")
        return []

    return result.get("evidence_links", [])
