"""Module 3 — Case Analysis Pipeline

Orchestrates 7 specialised LLM agents in a DAG to turn raw case documents into
a structured legal analysis: facts → parties → claims → evidence links →
timeline → contradictions → scoring.

Each agent is independently promptable (see ``prompts/``) and its output is
persisted via the corresponding repository (see ``repositories/``).
"""

import logging
import time
from typing import Any
from uuid import UUID

from sqlmodel import Session

from services.case_analysis.graph.state import CaseAnalysisState
from services.case_analysis.services.qdrant import qdrant_service

from services.case_analysis.agents.fact_agent import run_fact_agent
from services.case_analysis.agents.party_agent import run_party_agent
from services.case_analysis.agents.claim_agent import run_claim_agent
from services.case_analysis.agents.evidence_agent import run_evidence_agent
from services.case_analysis.agents.timeline_agent import run_timeline_agent
from services.case_analysis.agents.contradiction_agent import run_contradiction_agent
from services.case_analysis.agents.scoring_agent import run_scoring_agent

from services.case_analysis.repositories.facts import (
    save_facts,
    delete_case_facts,
)
from services.case_analysis.repositories.parties import (
    save_parties,
    delete_case_parties,
)
from services.case_analysis.repositories.claims import (
    save_claims,
    delete_case_claims,
)
from services.case_analysis.repositories.evidence import (
    save_evidence_links,
    delete_case_evidence_links,
)
from services.case_analysis.repositories.timeline import (
    save_timeline,
    delete_case_timeline,
)
from services.case_analysis.repositories.contradictions import (
    save_contradictions,
    delete_case_contradictions,
)
from services.case_analysis.repositories.scoring import (
    save_assessments,
    delete_case_assessments,
)

logger = logging.getLogger(__name__)


# ── Context budget ────────────────────────────────────────────────────
# Qwen 3-32B has *6 K TPM* (input + output).  Each agent needs ~1.5 K for
# prompts+output, leaving ≈4.5 K for context.  Use a conservative 4 000‑token
# budget so 7 sequential calls don't exhaust the minute window.
_CONTEXT_MAX_CHARS = 16_000  # ≈ 4 000 tokens @ 4 chars/token

# ── Rate-limit pacing ─────────────────────────────────────────────────
# Qwen 3-32B: 6 K TPM.  The LLM service retries 429s with exponential
# backoff (10s/20s/40s).  This small sleep reduces how often we hit the
# limit in the first place.
_AGENT_SLEEP_S = 5


def _truncate_context(raw: str, max_chars: int = _CONTEXT_MAX_CHARS) -> str:
    """Truncate *raw* to *max_chars*, preserving the first and last portions."""
    if len(raw) <= max_chars:
        return raw
    head = raw[: max_chars * 3 // 4]
    tail = raw[-(max_chars // 4) :]
    return (
        head
        + f"\n\n[… {len(raw) - max_chars} chars truncated …]\n\n"
        + tail
    )


def run_analysis_pipeline(case_id: UUID, session: Session) -> dict[str, Any]:
    """Execute the full 7-agent analysis pipeline for *case_id*.

    Steps
    -----
    1. Fetch raw document chunks from Qdrant.
    2. Clear stale analysis data for this case.
    3. Agent 1 — Fact Extraction
    4. Agent 2 — Party Identification
    5. Agent 3 — Claim Identification
    6. Agent 4 — Evidence Linkage
    7. Agent 5 — Timeline Building
    8. Agent 6 — Contradiction Detection
    9. Agent 7 — Scoring & Assessment
    10. Persist every result to the database.

    Returns the full ``CaseAnalysisState`` dict with all fields populated.
    """
    # ── 1. Build raw context from Qdrant ─────────────────────────────
    raw_context = qdrant_service.build_context(str(case_id))
    if not raw_context:
        return {"case_id": case_id, "raw_context": "", "errors": ["No documents found"]}

    raw_context = _truncate_context(raw_context)
    logger.info(
        "[pipeline] case=%s — raw_context=%d chars (after truncation)",
        case_id,
        len(raw_context),
    )

    # ── 2. Initialise state and clear stale data ─────────────────────
    state: CaseAnalysisState = {
        "case_id": case_id,
        "raw_context": raw_context,
        "facts": [],
        "parties": [],
        "claims": [],
        "evidence_links": [],
        "timeline": [],
        "contradictions": [],
        "assessments": [],
        "errors": [],
    }

    # ── 2. Clear stale data (all domains) ──────────────────────────────
    # Delete in FK-safe order: children before parents.
    # assessments.claim_id     → claims.id
    # evidence_links.claim_id  → claims.id
    # evidence_links.fact_id   → extracted_facts.id
    # contradictions.fact_a/b_id → extracted_facts.id
    delete_case_assessments(session, case_id)
    delete_case_evidence_links(session, case_id)
    delete_case_contradictions(session, case_id)
    delete_case_timeline(session, case_id)
    delete_case_claims(session, case_id)
    delete_case_parties(session, case_id)
    delete_case_facts(session, case_id)

    # ── 3. Fact Agent ────────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 1/7: Fact Extraction", case_id)
    facts = run_fact_agent(state)
    db_facts: list = []
    print("facts are ,",facts)
    if facts:
        db_facts = save_facts(session, case_id, facts)
        state["facts"] = [
            {**f, "id": str(db_facts[i].id)} for i, f in enumerate(facts)
        ]
        logger.info("[pipeline] case=%s — extracted %d facts", case_id, len(facts))
    else:
        logger.warning("[pipeline] case=%s — Fact agent returned empty", case_id)

    time.sleep(_AGENT_SLEEP_S)

    # ── 4. Party Agent ───────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 2/7: Party Identification", case_id)
    parties = run_party_agent(state)
    print(parties)
    if parties:
        db_parties = save_parties(session, case_id, parties)
        state["parties"] = [
            {**p, "id": str(db_parties[i].id)} for i, p in enumerate(parties)
        ]
        logger.info("[pipeline] case=%s — identified %d parties", case_id, len(parties))

    time.sleep(_AGENT_SLEEP_S)

    # ── 5. Claim Agent ───────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 3/7: Claim Identification", case_id)
    claims = run_claim_agent(state)
    db_claims: list = []
    if claims:
        db_claims = save_claims(session, case_id, claims)
        state["claims"] = [
            {**c, "id": str(db_claims[i].id)} for i, c in enumerate(claims)
        ]
        logger.info("[pipeline] case=%s — identified %d claims", case_id, len(claims))

    # Build index maps for downstream agents (safe defaults when empty)
    claim_ids = [db_claims[i].id for i in range(len(claims))] if claims else []
    fact_ids = [db_facts[i].id for i in range(len(facts))] if facts else []

    time.sleep(_AGENT_SLEEP_S)

    # ── 6. Evidence Agent ────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 4/7: Evidence Linkage", case_id)
    evidence_links = run_evidence_agent(state)
    if evidence_links and claim_ids and fact_ids:
        save_evidence_links(session, claim_ids, fact_ids, evidence_links)
        state["evidence_links"] = evidence_links
        logger.info("[pipeline] case=%s — created %d evidence links", case_id, len(evidence_links))

    time.sleep(_AGENT_SLEEP_S)

    # ── 7. Timeline Agent ────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 5/7: Timeline Building", case_id)
    timeline = run_timeline_agent(state)
    if timeline:
        save_timeline(session, case_id, timeline)
        state["timeline"] = timeline
        logger.info("[pipeline] case=%s — built %d timeline events", case_id, len(timeline))

    time.sleep(_AGENT_SLEEP_S)

    # ── 8. Contradiction Agent ───────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 6/7: Contradiction Detection", case_id)
    contradictions = run_contradiction_agent(state)
    if contradictions and fact_ids:
        save_contradictions(session, case_id, fact_ids, contradictions)
        state["contradictions"] = contradictions
        logger.info("[pipeline] case=%s — found %d contradictions", case_id, len(contradictions))

    time.sleep(_AGENT_SLEEP_S)

    # ── 9. Scoring Agent ─────────────────────────────────────────────
    logger.info("[pipeline] case=%s — Agent 7/7: Case Scoring", case_id)
    assessments = run_scoring_agent(state)
    if assessments and claim_ids:
        save_assessments(session, case_id, claim_ids, assessments)
        state["assessments"] = assessments
        logger.info("[pipeline] case=%s — produced %d assessments", case_id, len(assessments))

    # ── 10. Done ─────────────────────────────────────────────────────
    logger.info("[pipeline] case=%s — analysis complete (%d errors)", case_id, len(state.get("errors", [])))
    return state