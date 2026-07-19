"""Pool specification and juror persona generation.

Step 1 — Generate a demographic pool spec from the case context.
Step 2 — Generate 12 unique juror personas matching that spec.
"""

import logging
import random
from typing import Any, List

from services.jury_simulation.prompts.jury_prompt import (
    build_pool_spec_prompt,
    build_persona_prompt,
)
from services.jury_simulation.services.llm import MistralService

logger = logging.getLogger(__name__)

llm = MistralService()


def generate_pool_specification(case_data: dict) -> dict:
    """Generate the target demographic jury composition from case context."""
    prompt = build_pool_spec_prompt(case_data)
    try:
        result = llm.generate_json(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=0.2,
        )
        logger.info("Pool specification generated: %d jurors", result.get("total_jurors", 0))
        return result
    except Exception as e:
        logger.error("Pool spec generation failed: %s", e)
        return {
            "total_jurors": 12,
            "gender_split": {"male": 6, "female": 6},
            "age_distribution": [
                {"range": "25-34", "count": 3},
                {"range": "35-44", "count": 3},
                {"range": "45-54", "count": 3},
                {"range": "55-64", "count": 3},
            ],
            "education_distribution": [
                {"level": "High School", "count": 3},
                {"level": "Bachelor's", "count": 5},
                {"level": "Graduate", "count": 4},
            ],
            "occupation_distribution": [
                {"category": "Professional", "count": 4},
                {"category": "Skilled Trades", "count": 3},
                {"category": "Service", "count": 3},
                {"category": "Retired", "count": 2},
            ],
            "political_leaning": {"liberal": 0.35, "moderate": 0.35, "conservative": 0.30},
            "rationale": "Default balanced composition.",
        }


def generate_juror_personas(
    pool_spec: dict,
    case_data: dict,
    count: int = 12,
) -> List[dict]:
    """Generate *count* unique juror personas matching the pool spec.

    Tracks used names and occupations to prevent repetition across calls.
    Uses higher temperature and targeted uniqueness constraints in each prompt.
    """
    personas: List[dict] = []
    used_names: List[str] = []
    used_occupations: List[str] = []

    # Shuffle the intended demographic buckets so we cycle through them
    occupation_bucket = pool_spec.get("occupation_distribution", [])
    expanded_occs = []
    for b in occupation_bucket:
        expanded_occs.extend([b["category"]] * b["count"])
    random.shuffle(expanded_occs)
    # Pad if needed
    while len(expanded_occs) < count:
        expanded_occs.append("Professional")

    for i in range(1, count + 1):
        target_occ = expanded_occs[(i - 1) % len(expanded_occs)]

        prompt = build_persona_prompt(
            pool_spec,
            i,
            case_data,
            used_names=used_names,
            used_occupations=used_occupations,
            target_occupation=target_occ,
        )
        try:
            result = llm.generate_json(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                temperature=0.85,  # Higher temp for maximum diversity
            )
            result["juror_number"] = i

            # Track uniqueness
            name = result.get("name", "")
            if name:
                used_names.append(name)
            occ = result.get("occupation", "")
            if occ:
                used_occupations.append(occ)

            personas.append(result)
            logger.info("Persona %d/%d: %s — %s", i, count, name or "?", occ or "?")

        except Exception as e:
            logger.error("Persona %d generation failed: %s", i, e)
            fallback = _fallback_persona(i, target_occ)
            personas.append(fallback)
            used_names.append(fallback["name"])

    return personas


def _fallback_persona(juror_number: int, target_occ: str = "Professional") -> dict:
    """Return a safe fallback persona when LLM generation fails."""
    first_names = ["James", "Maria", "David", "Aisha", "Robert", "Yuki",
                   "Linda", "Carlos", "Susan", "Wei", "Michael", "Fatima"]
    last_names = ["Chen", "Okafor", "Miller", "Patel", "Kim", "Garcia",
                  "Thompson", "Ali", "Rodriguez", "Nguyen", "O'Brien", "Sato"]
    idx = (juror_number - 1) % len(first_names)
    name = f"{first_names[idx]} {last_names[idx]}"

    occ_descriptions = {
        "Professional": {"occupation": "Accountant", "bio": "works at a regional accounting firm."},
        "Skilled Trades": {"occupation": "Electrician", "bio": "runs a small electrical contracting business."},
        "Service": {"occupation": "Restaurant Manager", "bio": "manages a busy downtown restaurant."},
        "Retired": {"occupation": "Retired Teacher", "bio": "spent 35 years teaching high school history."},
    }
    occ_info = occ_descriptions.get(target_occ, {"occupation": "Small Business Owner", "bio": "owns a local business."})

    return {
        "juror_number": juror_number,
        "name": name,
        "age": 30 + (juror_number * 3),
        "gender": "male" if juror_number % 2 == 0 else "female",
        "education": "Bachelor's Degree",
        "occupation": occ_info["occupation"],
        "biography": f"{name} {occ_info['bio']} {('He' if juror_number % 2 == 0 else 'She')} lives in the area with family.",
        "behavioral_profile": {
            "risk_tolerance": random.randint(3, 8),
            "empathy": random.randint(3, 8),
            "trust_in_experts": random.randint(3, 8),
            "trust_in_corporations": random.randint(2, 7),
            "political_leaning": random.choice(["liberal", "moderate", "conservative"]),
            "analytical_vs_emotional": random.randint(3, 8),
            "leadership_tendency": random.randint(3, 8),
        },
    }