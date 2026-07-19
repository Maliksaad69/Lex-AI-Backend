"""Vote aggregator — combines juror votes into a comprehensive simulation report."""

import logging
from typing import Any, Dict, List, Optional
from collections import Counter
from statistics import median as stat_median

logger = logging.getLogger(__name__)


def aggregate_votes(votes: List[dict], personas: List[dict]) -> dict:
    """Aggregate individual juror votes into a structured report.

    Returns
    -------
    dict with fields for the full suite of jury insights.
    """
    if not votes:
        return {
            "plaintiff_votes": 0,
            "defense_votes": 0,
            "confidence": 0.0,
            "average_damages": None,
            "summary": "No votes were recorded.",
            "consensus_level": "No Data",
            "jury_deliberation_summary": "",
            "decision_drivers": [],
            "damages_distribution": None,
            "confidence_distribution": [],
            "evidence_influence": [],
            "witness_credibility_ranking": [],
            "common_themes": [],
        }

    plaintiff_votes = [v for v in votes if v.get("verdict") == "plaintiff"]
    defense_votes = [v for v in votes if v.get("verdict") == "defense"]

    plaintiff_count = len(plaintiff_votes)
    defense_count = len(defense_votes)
    total = len(votes)
    plaintiff_pct = round(plaintiff_count / total * 100) if total else 0

    # ── Confidence ────────────────────────────────────────────────────
    all_confidences = [v.get("confidence", 0.5) for v in votes]
    avg_confidence = sum(all_confidences) / len(all_confidences)
    confidence_distribution = sorted([round(c * 100) for c in all_confidences], reverse=True)

    # ── Damages ───────────────────────────────────────────────────────
    damages_values = sorted([
        v.get("damages") for v in plaintiff_votes if v.get("damages") is not None
    ])
    avg_damages = sum(damages_values) / len(damages_values) if damages_values else None
    damages_distribution = None
    if damages_values:
        damages_distribution = {
            "minimum": damages_values[0],
            "maximum": damages_values[-1],
            "average": round(sum(damages_values) / len(damages_values)),
            "median": round(stat_median(damages_values)),
            "count": len(damages_values),
        }

    # ── Consensus level ───────────────────────────────────────────────
    ratio = plaintiff_count / total if total else 0
    if ratio >= 0.83:
        consensus_level = "Strong Consensus"
    elif ratio >= 0.67:
        consensus_level = "Moderate Consensus"
    elif ratio >= 0.42:
        consensus_level = "Split Jury"
    else:
        consensus_level = "Highly Divided"

    # ── Evidence influence ────────────────────────────────────────────
    evidence_counter: Counter = Counter()
    for v in votes:
        for ref in v.get("evidence_referenced", []):
            if ref:
                evidence_counter[ref.lower().strip()] += 1
    evidence_influence = [
        {
            "evidence": item,
            "mentions": count,
            "influence_score": round(count / total * 10, 1),
            "explanation": _explain_evidence_influence(item, count),
        }
        for item, count in evidence_counter.most_common(10)
    ]

    # ── Decision drivers (extracted from reasoning) ───────────────────
    all_reasoning = " ".join(v.get("reasoning", "") for v in votes).lower()
    driver_keywords = [
        ("Expert Credibility", ["expert credibility", "expert testimony", "expert witness"]),
        ("Failure to Preserve Evidence", ["failure to preserve", "spoliation", "destroyed evidence", "missing evidence"]),
        ("Contract Terms", ["contract", "agreement", "breach of contract", "terms"]),
        ("Technical Evidence", ["technical", "engineering", "scientific", "data", "analysis"]),
        ("Timeline Consistency", ["timeline", "chronology", "sequence", "date", "when"]),
        ("Credibility of Witnesses", ["credibility", "believable", "trustworthy", "unreliable"]),
        ("Causation", ["causation", "proximate cause", "directly caused", "led to"]),
        ("Damages Calculation", ["damages", "compensation", "award", "monetary", "financial loss"]),
        ("Comparative Fault", ["comparative fault", "contributory", "shared blame", "both parties"]),
        ("Documentary Evidence", ["document", "record", "email", "report", "memorandum"]),
    ]
    decision_drivers = []
    for driver_name, keywords in driver_keywords:
        count = sum(all_reasoning.count(kw) for kw in keywords)
        if count > 0:
            decision_drivers.append({"driver": driver_name, "juror_references": count})
    decision_drivers.sort(key=lambda d: d["juror_references"], reverse=True)

    # ── Witness credibility ranking with explanations ─────────────────
    witness_scores: Dict[str, List[int]] = {}
    witness_explanations: Dict[str, List[str]] = {}
    for v in votes:
        for witness, score in v.get("witness_credibility", {}).items():
            normalized = witness.strip().lower()
            if normalized not in witness_scores:
                witness_scores[normalized] = []
                witness_explanations[normalized] = []
            if isinstance(score, (int, float)):
                witness_scores[normalized].append(score)
        for w in v.get("witness_credibility", {}):
            # Extract a simple explanation from reasoning context
            lower_reasoning = v.get("reasoning", "").lower()
            w_lower = w.lower()
            context_start = max(0, lower_reasoning.find(w_lower) - 40)
            context_end = min(len(lower_reasoning), lower_reasoning.find(w_lower) + len(w_lower) + 60)
            if context_start < context_end:
                snippet = v.get("reasoning", "")[context_start:context_end].strip()
                if snippet and w_lower in snippet.lower():
                    witness_explanations[w.strip().lower()].append(snippet)

    witness_ranking = []
    for witness_name, scores in sorted(
        witness_scores.items(),
        key=lambda x: sum(x[1]) / len(x[1]),
        reverse=True,
    ):
        expls = witness_explanations.get(witness_name, [])
        # Pick the shortest useful explanation
        best_expl = min((e for e in expls if len(e) > 20), key=len) if expls else ""
        witness_ranking.append({
            "witness": witness_name.title(),
            "avg_score": round(sum(scores) / len(scores), 1),
            "count": len(scores),
            "explanation": best_expl if len(best_expl) < 200 else best_expl[:197] + "...",
        })

    # ── Common themes (removed — not useful) ─────────────────────────
    common_themes = []

    # ── AI Jury Deliberation Summary ───────────────────────────────────
    jury_deliberation_summary = _build_deliberation_summary(
        plaintiff_count, defense_count, total, avg_confidence,
        decision_drivers, avg_damages,
    )

    # ── Short summary ─────────────────────────────────────────────────
    summary = (
        f"Verdict split: {plaintiff_count} plaintiff ({plaintiff_pct}%) — "
        f"{defense_count} defense ({100 - plaintiff_pct}%). "
        f"Average confidence: {avg_confidence:.0%}. "
    )
    if avg_damages:
        summary += f"Average damages: ${avg_damages:,.0f}. "
    if decision_drivers:
        summary += f"Top driver: {decision_drivers[0]['driver']}."
    summary += f" Consensus: {consensus_level}."

    return {
        "plaintiff_votes": plaintiff_count,
        "defense_votes": defense_count,
        "confidence": round(avg_confidence, 2),
        "average_damages": avg_damages,
        "summary": summary,
        "consensus_level": consensus_level,
        "jury_deliberation_summary": jury_deliberation_summary,
        "decision_drivers": decision_drivers,
        "damages_distribution": damages_distribution,
        "confidence_distribution": confidence_distribution,
        "evidence_influence": evidence_influence,
        "witness_credibility_ranking": witness_ranking,
        "common_themes": common_themes,
    }


def _build_deliberation_summary(
    plaintiff_count: int,
    defense_count: int,
    total: int,
    avg_confidence: float,
    decision_drivers: List[dict],
    avg_damages: Optional[float],
) -> str:
    """Generate a concise deliberation summary paragraph."""
    parts = []
    winner = "plaintiff" if plaintiff_count > defense_count else "defense"
    parts.append(
        f"After deliberating on the case evidence, {plaintiff_count} of {total} jurors "
        f"found in favor of the {winner}."
    )
    if decision_drivers:
        top = decision_drivers[0]
        parts.append(
            f"The most influential factor was {top['driver'].lower()}, "
            f"referenced by {top['juror_references']} juror(s)."
        )
    if avg_damages:
        parts.append(f"Among plaintiff verdicts, estimated damages averaged ${avg_damages:,.0f}.")
    parts.append(
        f"Overall juror confidence averaged {avg_confidence:.0%}, "
        f"indicating {'strong' if avg_confidence > 0.8 else 'moderate' if avg_confidence > 0.6 else 'mixed'} conviction."
    )
    return " ".join(parts)


def _explain_evidence_influence(evidence: str, mentions: int) -> str:
    """Generate a short explanation for why evidence was influential."""
    evidence_lower = evidence.lower()
    if any(kw in evidence_lower for kw in ["expert", "testimony", "report", "analysis"]):
        return "Provided authoritative technical analysis that shaped juror understanding."
    if any(kw in evidence_lower for kw in ["contract", "agreement", "email", "document"]):
        return "Documented the legal obligations and factual timeline of the case."
    if any(kw in evidence_lower for kw in ["witness", "deposition", "statement"]):
        return "Offered firsthand account that jurors weighed against other testimony."
    if any(kw in evidence_lower for kw in ["photo", "video", "diagram", "exhibit"]):
        return "Visual evidence that made the technical details accessible to jurors."
    if any(kw in evidence_lower for kw in ["damages", "financial", "economic", "loss"]):
        return "Quantified the financial impact and influenced damages assessment."
    return "Referenced by multiple jurors as significant to their decision-making process."