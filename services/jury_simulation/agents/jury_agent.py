"""Single juror agent — evaluates a case from one persona's perspective."""

import logging
from typing import Any, Optional

from services.jury_simulation.prompts.jury_prompt import build_juror_prompt
from services.jury_simulation.services.llm import MistralService

logger = logging.getLogger(__name__)

llm = MistralService()


def run_juror_agent(
    persona: dict,
    stimulus: dict,
    temperature: Optional[float] = None,
) -> dict:
    """Run a single juror LLM agent.

    Parameters
    ----------
    persona : dict
        The juror's persona data (demographics + behavioral profile).
    stimulus : dict
        The case stimulus (jury-friendly summary).
    temperature : float, optional
        Reasoning temperature. Defaults to 0.4 for balanced deliberation.

    Returns
    -------
    dict with keys: verdict, confidence, damages, reasoning, evidence_referenced,
    witness_credibility, key_doubts
    """
    prompt = build_juror_prompt(persona, stimulus)
    temp = temperature if temperature is not None else 0.4

    try:
        result = llm.generate_json(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=temp,
        )
        logger.info(
            "Juror '%s' verdict: %s (confidence: %.2f)",
            persona.get("name", "?"),
            result.get("verdict", "?"),
            result.get("confidence", 0),
        )
        return result
    except Exception as e:
        logger.error(
            "Juror agent failed for '%s': %s",
            persona.get("name", "?"),
            e,
        )
        return {
            "verdict": "defense",
            "confidence": 0.5,
            "damages": None,
            "reasoning": "Juror agent encountered an error during deliberation.",
            "evidence_referenced": [],
            "witness_credibility": {},
            "key_doubts": str(e),
        }