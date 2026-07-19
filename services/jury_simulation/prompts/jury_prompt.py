"""Prompt templates for the Jury Simulation pipeline.

Each function returns a dict with ``system`` and ``user`` keys suitable
for the LLM service's ``generate_json`` method.
"""

# ──────────────────────────────────────────────────────────────────────────
# 1. Pool Specification
# ──────────────────────────────────────────────────────────────────────────

POOL_SPEC_SYSTEM = """You are a jury consultant. Generate a representative jury pool
specification for a civil trial. The specification defines the target demographic
composition for a 12-person jury."""


def build_pool_spec_prompt(case_data: dict) -> dict:
    """Generate a demographic target spec from the case context."""
    parties = case_data.get("parties", [])
    claims = case_data.get("claims", [])
    assessments = case_data.get("assessments", [])

    claim_types = ", ".join(c.get("claim_type", "") for c in claims) if claims else "unknown"
    plaintiff = next(
        (p.get("name", "Plaintiff") for p in parties if p.get("role", "").lower() == "plaintiff"),
        "Plaintiff",
    )
    defendant = next(
        (p.get("name", "Defendant") for p in parties if p.get("role", "").lower() == "defendant"),
        "Defendant",
    )

    return {
        "system": POOL_SPEC_SYSTEM,
        "user": f"""Given the following case context, generate a jury pool specification.

Plaintiff: {plaintiff}
Defendant: {defendant}
Claim Types: {claim_types}

Return valid JSON with this exact schema:
{{
  "total_jurors": 12,
  "gender_split": {{ "male": int, "female": int }},
  "age_distribution": [{{ "range": str, "count": int }}],
  "education_distribution": [{{ "level": str, "count": int }}],
  "occupation_distribution": [{{ "category": str, "count": int }}],
  "political_leaning": {{ "liberal": float, "moderate": float, "conservative": float }},
  "rationale": "str — why this composition fits the case"
}}

Distribute exactly 12 jurors. Gender must sum to 12. Political leanings must sum to 1.0.""",
    }


# ──────────────────────────────────────────────────────────────────────────
# 2. Case Stimulus
# ──────────────────────────────────────────────────────────────────────────

STIMULUS_SYSTEM = """You are a legal writer. Convert structured case analysis data into a
neutral, juror-friendly case summary — similar to what mock-jury research participants
receive. Write in plain English. Do NOT editorialise. Present both sides fairly."""


def build_stimulus_prompt(case_data: dict) -> dict:
    """Build a juror-friendly case stimulus from structured analysis."""
    facts = case_data.get("facts", [])
    parties = case_data.get("parties", [])
    claims = case_data.get("claims", [])
    timeline = case_data.get("timeline", [])
    evidence_links = case_data.get("evidence_links", [])
    contradictions = case_data.get("contradictions", [])
    assessments = case_data.get("assessments", [])

    def fmt_facts():
        lines = []
        for f in facts[:20]:
            lines.append(f"• {f.get('statement','')}")
        return "\n".join(lines)

    def fmt_parties():
        lines = []
        for p in parties:
            lines.append(f"• {p.get('name','')} — {p.get('role','')} ({p.get('type','')})")
        return "\n".join(lines)

    def fmt_claims():
        lines = []
        for c in claims[:10]:
            els = c.get("elements", [])
            el_str = ""
            if isinstance(els, list) and els:
                el_str = " [Elements: " + "; ".join(els[:5]) + "]"
            lines.append(f"• {c.get('claim_type','')}{el_str}")
        return "\n".join(lines)

    def fmt_timeline():
        lines = []
        for ev in timeline[:15]:
            lines.append(f"• {ev.get('event_date','(date unknown)')} — {ev.get('description','')}")
        return "\n".join(lines)

    def fmt_evidence():
        lines = []
        for e in evidence_links[:15]:
            rel = e.get("relationship", "supports")
            lines.append(f"• {rel.upper()}: Claim ref {e.get('claim_id','?')[:8]} ↔ Fact ref {e.get('fact_id','?')[:8]}  (weight={e.get('weight_score','?')})")
        return "\n".join(lines)

    plaintiff_name = "Plaintiff"
    defendant_name = "Defendant"
    for p in parties:
        role = p.get("role", "").lower()
        name = p.get("name", "")
        if role == "plaintiff":
            plaintiff_name = name
        elif role == "defendant":
            defendant_name = name

    return {
        "system": STIMULUS_SYSTEM,
        "user": f"""Transform the following structured case data into a clear, neutral case summary
suitable for a mock-juror research study.

--- CASE BACKGROUND ---
Plaintiff: {plaintiff_name}
Defendant: {defendant_name}

--- PARTIES INVOLVED ---
{fmt_parties()}

--- KEY FACTS ---
{fmt_facts()}

--- CLAIMS ---
{fmt_claims()}

--- TIMELINE ---
{fmt_timeline()}

--- EVIDENCE SUMMARY ---
{fmt_evidence()}

Return a single string `stimulus` with:

1. A short case background paragraph.
2. A plaintiff's perspective paragraph.
3. A defendant's perspective paragraph.
4. A summary of key evidence and witnesses.
5. Questions the jury must decide (liability, damages, comparative fault).

Output format:
{{"stimulus": "the full text...", "plaintiff_narrative": "...", "defense_narrative": "...", "key_evidence": ["..."], "damages_overview": "..."}}
""",
    }


# ──────────────────────────────────────────────────────────────────────────
# 3. Juror Persona Generation
# ──────────────────────────────────────────────────────────────────────────

PERSONA_SYSTEM = """You are a jury consultant creating realistic juror personas for a mock trial.
Each persona must be internally consistent — demographics, life experience, and
behavioural traits should all align. Invent a plausible background story.

CRITICAL: Every persona you generate must be UNIQUE. Do NOT repeat names, occupations,
or life stories from the list of already-used personas below. Spread across diverse
age groups, backgrounds, and personality types."""


def build_persona_prompt(
    pool_spec: dict,
    juror_number: int,
    case_data: dict,
    used_names: list[str] | None = None,
    used_occupations: list[str] | None = None,
    target_occupation: str | None = None,
) -> dict:
    """Generate one juror persona matching the pool specification.

    Parameters
    ----------
    used_names : list[str]
        Names already assigned to earlier personas — avoid repeating.
    used_occupations : list[str]
        Occupations already used — aim for distinct fields.
    target_occupation : str, optional
        Broad occupation category this persona should fall into
        (e.g. "Professional", "Skilled Trades", "Service", "Retired").
    """
    claims = case_data.get("claims", [])
    claim_types = ", ".join(c.get("claim_type", "") for c in claims) if claims else "general civil litigation"

    genders = pool_spec.get("gender_split", {"male": 6, "female": 6})
    ages = pool_spec.get("age_distribution", [{"range": "35-44", "count": 4}])
    eds = pool_spec.get("education_distribution", [{"level": "Bachelor's", "count": 4}])
    occs = pool_spec.get("occupation_distribution", [{"category": "Professional", "count": 4}])

    used_names_str = ", ".join(used_names[-8:]) if used_names else "None yet"
    used_occs_str = ", ".join(used_occupations[-8:]) if used_occupations else "None yet"

    return {
        "system": PERSONA_SYSTEM,
        "user": f"""Create a realistic juror persona (juror #{juror_number}) for a {claim_types} trial.

The jury pool has this target composition:
  Gender split: {genders}
  Age distribution: {ages}
  Education: {eds}
  Occupations: {occs}

ALREADY-USED names: [{used_names_str}]
ALREADY-USED occupations: [{used_occs_str}]

{"Target occupation category for this juror: " + target_occupation if target_occupation else ""}

DIVERSITY RULES:
1. Name MUST be different from all already-used names above. Choose a distinct first + last name.
2. Occupation MUST be different from already-used occupations. Be specific (e.g. "High School Biology Teacher" not just "Teacher").
3. Age must be realistic for the occupation.
4. behavioral_profile scores should vary meaningfully — not all 7-9 across the board.
5. biography must feel like a real person with specific details (where they grew up, family, hobbies, career path).

Return valid JSON with this exact schema:
{{
  "name": "str",
  "age": int,
  "gender": "male" | "female" | "non-binary",
  "education": "str",
  "occupation": "str",
  "biography": "str — 2-3 sentence life story with specific personal details",
  "behavioral_profile": {{
    "risk_tolerance": int (1-10),
    "empathy": int (1-10),
    "trust_in_experts": int (1-10),
    "trust_in_corporations": int (1-10),
    "political_leaning": "liberal" | "moderate" | "conservative",
    "analytical_vs_emotional": int (1-10, 10 = highly analytical),
    "leadership_tendency": int (1-10)
  }}
}}

Make this persona feel like a real, distinct person — not a stereotype. Spread trait scores across the full 1-10 range, not clustered in the middle.""",
    }


# ──────────────────────────────────────────────────────────────────────────
# 4. Juror Deliberation / Verdict
# ──────────────────────────────────────────────────────────────────────────

JUROR_SYSTEM = """You are serving as a juror in a civil trial. You have been given a specific
juror profile with demographic information, life experience, and behavioural traits.
You must evaluate the case evidence FROM THAT JUROR'S PERSPECTIVE — applying their
life experience, biases, and reasoning style to the facts presented.

Be honest about how this specific person would react, not how an ideal juror would.
Your reasoning must reflect the persona's traits."""


def build_juror_prompt(persona: dict, stimulus: dict) -> dict:
    """Build the prompt for one juror to evaluate the case."""
    bp = persona.get("behavioral_profile", {})

    profile_summary = (
        f"Name: {persona.get('name','Juror')}\n"
        f"Age: {persona.get('age','?')} · Gender: {persona.get('gender','?')}\n"
        f"Education: {persona.get('education','?')}\n"
        f"Occupation: {persona.get('occupation','?')}\n"
        f"Biography: {persona.get('biography','?')}\n"
        f"\nBehavioural Profile:\n"
        f"  Risk tolerance: {bp.get('risk_tolerance','?')}/10\n"
        f"  Empathy: {bp.get('empathy','?')}/10\n"
        f"  Trust in experts: {bp.get('trust_in_experts','?')}/10\n"
        f"  Trust in corporations: {bp.get('trust_in_corporations','?')}/10\n"
        f"  Political leaning: {bp.get('political_leaning','?')}\n"
        f"  Analytical vs emotional: {bp.get('analytical_vs_emotional','?')}/10\n"
        f"  Leadership tendency: {bp.get('leadership_tendency','?')}/10"
    )

    stimulus_text = stimulus.get("stimulus", "")

    return {
        "system": JUROR_SYSTEM,
        "user": f"""You are the following juror:

{profile_summary}

Now read the case evidence and instructions below. After careful consideration,
decide on a VERDICT from THIS JUROR'S perspective.

--- CASE STIMULUS ---
{stimulus_text}

Return your verdict and reasoning as valid JSON with this schema:
{{
  "verdict": "plaintiff" | "defense",
  "confidence": 0.0-1.0,
  "damages": float | null (only if plaintiff verdict, estimated $ amount),
  "reasoning": "str — detailed explanation of how this juror reached their decision, referencing specific evidence",
  "evidence_referenced": ["str — specific evidence that influenced this juror"],
  "witness_credibility": {{ "witness_name": 1-10, ... }},
  "key_doubts": "str — what this SPECIFIC juror is still uncertain about (must be unique per juror)"
}}

IMPORTANT: Your key_doubts must be SPECIFIC to this juror's unique perspective. Different jurors have different doubts. Be creative and specific.""",
    }