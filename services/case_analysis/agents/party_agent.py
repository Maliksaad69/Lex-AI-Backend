"""Party Identification Agent — identifies all parties, witnesses, and legal reps."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import GroqLLM
from services.case_analysis.prompts.parties import build_party_prompt


def run_party_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Identify all parties and participants mentioned in *state.raw_context*.

    Returns a list of party dicts (name, role, type).

    On failure, appends to *state.errors* and returns an empty list.
    """
    system_prompt, user_prompt = build_party_prompt(state["raw_context"])

    try:
        result = GroqLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Party agent failed: {e}")
        return []

    return result.get("parties", [])