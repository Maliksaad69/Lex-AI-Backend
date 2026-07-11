"""Timeline Builder Agent — constructs a chronological sequence of case events."""

from typing import Any

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.llm import GroqLLM
from services.case_analysis.prompts.timeline import build_timeline_prompt


def run_timeline_agent(state: CaseAnalysisState) -> list[dict[str, Any]]:
    """Build a chronological timeline from extracted facts.

    Requires *state.facts* to be populated.

    Returns a list of timeline-event dicts (date, event, significance) sorted
    oldest-first.

    On failure, appends to *state.errors* and returns an empty list.
    """
    facts = state.get("facts", [])

    if not facts:
        state.setdefault("errors", []).append(
            "Timeline agent skipped: no facts available."
        )
        return []

    system_prompt, user_prompt = build_timeline_prompt(facts)

    try:
        result = GroqLLM.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.15,
        )
    except Exception as e:
        state.setdefault("errors", []).append(f"Timeline agent failed: {e}")
        return []

    return result.get("timeline", [])