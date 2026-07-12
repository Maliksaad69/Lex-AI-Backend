"""Fact Extraction Agent — extracts atomic factual statements from case documents."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import MistralLLM

from services.case_analysis.prompts.facts import build_fact_prompt


def run_fact_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Extract all material facts from *state.raw_context*.

    Returns a list of fact dicts matching the prompt schema (statement,
    source_document, page, importance, disputed, confidence).

    On failure, appends to *state.errors* and returns an empty list.
    """
    system_prompt, user_prompt = build_fact_prompt(state["raw_context"])

    try:
        result = MistralLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
        )
        print("facts are ", result)

    except Exception as e:
        state.setdefault("errors", []).append(f"Fact agent failed: {e}")
        print(e)
        return []

    facts_raw = result.get("facts", [])
    return facts_raw
