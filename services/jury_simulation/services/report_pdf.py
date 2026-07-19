"""PDF Report — comprehensive report with case analysis + jury simulation + verdict prediction."""

import io, os
from datetime import datetime
from uuid import UUID
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.colors import HexColor

from sqlmodel import Session
from db.models.case import Case
from services.case_analysis.repositories.facts import get_facts
from services.case_analysis.repositories.parties import get_parties
from services.case_analysis.repositories.claims import get_claims
from services.case_analysis.repositories.evidence import get_evidence_links
from services.case_analysis.repositories.timeline import get_timeline
from services.case_analysis.repositories.contradictions import get_contradictions
from services.case_analysis.repositories.scoring import get_assessments
from services.jury_simulation.services.database import (
    get_latest_simulation_for_case, get_personas_for_simulation, get_votes_for_simulation,
)

PRIMARY = HexColor("#2563eb")
DARK = HexColor("#1e293b")
LIGHT_GRAY = HexColor("#f8fafc")
MED_GRAY = HexColor("#94a3b8")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=28, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=14, textColor=DARK, alignment=TA_CENTER, spaceAfter=6))
styles.add(ParagraphStyle("SectionHead", fontName="Helvetica-Bold", fontSize=16, textColor=PRIMARY, spaceAfter=10, spaceBefore=24))
styles.add(ParagraphStyle("SubHead", fontName="Helvetica-Bold", fontSize=12, textColor=DARK, spaceAfter=6, spaceBefore=14))
styles.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=15, textColor=DARK, spaceAfter=6, alignment=TA_JUSTIFY))
styles.add(ParagraphStyle("BodyBold", fontName="Helvetica-Bold", fontSize=10, textColor=DARK, spaceAfter=4))
styles.add(ParagraphStyle("Small", fontName="Helvetica", fontSize=8, textColor=MED_GRAY, spaceAfter=3))
styles.add(ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle("TableCell", fontName="Helvetica", fontSize=9, textColor=DARK))


def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=HexColor("#e2e8f0"), spaceAfter=10, spaceBefore=10)


def _section(title: str):
    return [Spacer(1, 10), Paragraph(title, styles["SectionHead"]), _hr()]


def _kv_table(data, col_widths=None):
    rows = [[Paragraph(k, styles["BodyBold"]), Paragraph(str(v), styles["Body"])] for k, v in data]
    t = Table(rows, colWidths=col_widths or [1.8*inch, 4.2*inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HexColor("#e2e8f0")),
    ]))
    return t


def _styled_table(headers, rows, col_widths=None):
    all_rows = [[Paragraph(h, styles["TableHeader"]) for h in headers]]
    for row in rows:
        all_rows.append([Paragraph(str(c), styles["TableCell"]) for c in row])
    t = Table(all_rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
    ]))
    return t


def _format_dollars(val):
    if val is None:
        return "N/A"
    return f"${val:,.0f}"


def generate_jury_report(case_id: UUID, session: Session, output_path: str | None = None) -> bytes:
    case = session.get(Case, case_id)
    sim = get_latest_simulation_for_case(session, case_id)

    facts = get_facts(session, case_id)
    parties_list = get_parties(session, case_id)
    claims_list = get_claims(session, case_id)
    evidence_links = get_evidence_links(session, case_id)
    timeline = get_timeline(session, case_id)
    contradictions = get_contradictions(session, case_id)
    assessments = get_assessments(session, case_id)

    personas = get_personas_for_simulation(session, sim.id) if sim else []
    votes = get_votes_for_simulation(session, sim.id) if sim else []
    agg = sim.aggregation_data if sim and sim.aggregation_data else {}
    vp = agg.get("verdict_prediction", {}) if agg else {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    elements = []
    now_str = datetime.now().strftime("%B %d, %Y")
    winner = "Plaintiff" if sim and sim.plaintiff_votes > sim.defense_votes else "Defense"

    # ═══════════ COVER PAGE ═══════════
    elements.append(Spacer(1, 2.5*inch))
    elements.append(Paragraph("AI Litigation Intelligence Report", styles["CoverTitle"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(case.case_name if case else "Case Report", styles["CoverSub"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Generated: {now_str}", styles["Small"]))
    elements.append(Spacer(1, 0.5*inch))
    if sim:
        sd = [
            ["Predicted Outcome", winner],
            ["Vote Split", f"{sim.plaintiff_votes} - {sim.defense_votes}"],
            ["Confidence", f"{sim.confidence:.0%}" if sim.confidence else "N/A"],
            ["Damages", _format_dollars(sim.average_damages)],
            ["Consensus", agg.get("consensus_level", "N/A")],
        ]
        t = Table(sd, colWidths=[2*inch, 3*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), PRIMARY), ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
    elements.append(PageBreak())

    # ═══════════ EXECUTIVE SUMMARY ═══════════
    elements.extend(_section("Executive Summary"))
    es = agg.get("jury_deliberation_summary") or vp.get("executive_summary") or ""
    if es:
        elements.append(Paragraph(es, styles["Body"]))
    else:
        pn = next((p.get("name") for p in parties_list if p.get("role","").lower() == "plaintiff"), "Plaintiff")
        dn = next((p.get("name") for p in parties_list if p.get("role","").lower() == "defendant"), "Defendant")
        elements.append(Paragraph(f"AI analysis of {case.case_name} — {pn} v. {dn}. {len(facts)} facts, {len(claims_list)} claims.", styles["Body"]))
    elements.append(Spacer(1, 8))
    if sim:
        damages_str = f" Est. damages: {_format_dollars(sim.average_damages)}." if sim.average_damages else ""
        elements.append(Paragraph(
            f"The jury simulation predicts a <b>{winner}</b> verdict ({sim.plaintiff_votes}-{sim.defense_votes}) "
            f"with {sim.confidence:.0%} confidence.{damages_str} Consensus: {agg.get('consensus_level','N/A')}.",
            styles["Body"],
        ))

    # Verdict Prediction summary
    if vp:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Litigation Risk:</b> {vp.get('litigation_risk','N/A')}", styles["Body"]))
        elements.append(Paragraph(f"<b>Settlement Recommendation:</b> {vp.get('settlement_recommendation','N/A')}", styles["Body"]))
        elements.append(Paragraph(f"<b>Plaintiff Win Probability:</b> {vp.get('plaintiff_win_probability','N/A')}%", styles["Body"]))
        if vp.get("attorney_recommendations"):
            elements.append(Spacer(1, 4))
            elements.append(Paragraph("<b>Attorney Recommendations:</b>", styles["BodyBold"]))
            for rec in vp["attorney_recommendations"]:
                elements.append(Paragraph(f"• {rec}", styles["Body"]))

    # ═══════════ CASE OVERVIEW ═══════════
    elements.extend(_section("Case Overview"))
    if case:
        elements.append(_kv_table([
            ("Case Name", case.case_name),
            ("Claim Type", case.claim_type or "N/A"),
            ("Plaintiff", f"{case.plaintiff_name or 'N/A'} ({case.plaintiff_counsel or 'N/A'})"),
            ("Defendant", f"{case.defense_name or 'N/A'} ({case.defense_counsel or 'N/A'})"),
            ("Court / District", f"{case.court or 'N/A'}, {case.state or 'N/A'}"),
            ("County", case.county or "N/A"),
            ("Trial Date", case.trial_date or "N/A"),
            ("Filing Date", case.created_at.strftime("%B %d, %Y") if case.created_at else "N/A"),
            ("Current Stage", case.current_stage or "N/A"),
            ("Case Summary", case.summary or "N/A"),
        ]))

    # All Parties
    if parties_list:
        elements.append(Paragraph("All Parties", styles["SubHead"]))
        p_rows = [["Name", "Role", "Type"]]
        for p in parties_list:
            p_rows.append([p.get("name",""), p.get("role",""), p.get("type","")])
        elements.append(_styled_table(p_rows[0], p_rows[1:], col_widths=[2*inch, 1.5*inch, 1.5*inch]))

    # All Facts
    if facts:
        elements.append(Paragraph(f"All Extracted Facts ({len(facts)})", styles["SubHead"]))
        for f in facts:
            imp = f.get("importance", "N/A")
            conf = f.get("confidence", "N/A")
            conf_str = f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf)
            elements.append(Paragraph(
                f"• {f.get('statement','')} <i>(Importance: {imp}/10, Confidence: {conf_str})</i>",
                styles["Body"],
            ))

    # All Claims with Assessments
    if claims_list:
        elements.append(Paragraph(f"All Claims & Assessments ({len(claims_list)})", styles["SubHead"]))
        for c in claims_list:
            asm = next((a for a in assessments if str(a.get("claim_id","")) == str(c.get("id",""))), None)
            strength = asm.get("overall_strength", "N/A") if asm else "N/A"
            risk = asm.get("risk_level", "N/A") if asm else "N/A"
            strengths = asm.get("strengths", "N/A") if asm else "N/A"
            weaknesses = asm.get("weaknesses", "N/A") if asm else "N/A"
            el_str = ""
            if c.get("elements"):
                els = c["elements"]
                if isinstance(els, list):
                    el_str = " — Elements: " + "; ".join(els[:5])
            elements.append(Paragraph(
                f"• <b>{c.get('claim_type','')}</b>{el_str} — Strength: {strength}/10, Risk: {risk}",
                styles["Body"],
            ))
            if asm:
                if asm.get("strengths"):
                    s_val = asm["strengths"]
                    if isinstance(s_val, list) and s_val:
                        elements.append(Paragraph(f"  <i>Strengths:</i> {'; '.join(s_val[:3])}", styles["Small"]))
                if asm.get("weaknesses"):
                    w_val = asm["weaknesses"]
                    if isinstance(w_val, list) and w_val:
                        elements.append(Paragraph(f"  <i>Weaknesses:</i> {'; '.join(w_val[:3])}", styles["Small"]))

    # All Evidence Links
    if evidence_links:
        elements.append(Paragraph(f"Evidence Linkage Matrix ({len(evidence_links)})", styles["SubHead"]))
        el_rows = [["Claim", "Fact", "Relationship", "Weight"]]
        for e in evidence_links[:15]:
            el_rows.append([
                str(e.get("claim_id",""))[:8], str(e.get("fact_id",""))[:8],
                e.get("relationship",""), str(e.get("weight_score","")),
            ])
        elements.append(_styled_table(el_rows[0], el_rows[1:], col_widths=[1.5*inch, 1.5*inch, 1.2*inch, 0.8*inch]))

    # Full Timeline
    if timeline:
        elements.append(Paragraph(f"Case Timeline ({len(timeline)} events)", styles["SubHead"]))
        tl_rows = [["Date", "Event", "Significance"]]
        for ev in timeline:
            tl_rows.append([ev.get("event_date","N/A"), ev.get("description",""), ev.get("significance","") or ""])
        elements.append(_styled_table(tl_rows[0], tl_rows[1:], col_widths=[1.2*inch, 3.5*inch, 1.5*inch]))

    # All Contradictions
    if contradictions:
        elements.append(Paragraph(f"Contradictions Detected ({len(contradictions)})", styles["SubHead"]))
        for ct in contradictions:
            elements.append(Paragraph(
                f"• <b>{ct.get('nature','Contradiction')}</b> — "
                f"Fact A: {str(ct.get('fact_a_id',''))[:8]} vs Fact B: {str(ct.get('fact_b_id',''))[:8]}. "
                f"Impact: {ct.get('impact','N/A')}",
                styles["Body"],
            ))

    elements.append(PageBreak())

    # ═══════════ JURY SIMULATION ═══════════
    elements.extend(_section("Jury Simulation"))
    if sim:
        pct = round(sim.plaintiff_votes / (sim.plaintiff_votes + sim.defense_votes or 1) * 100)
        elements.append(_kv_table([
            ("Predicted Trial Outcome", winner),
            ("Plaintiff Votes", str(sim.plaintiff_votes)),
            ("Defense Votes", str(sim.defense_votes)),
            ("Win Percentage", f"{pct}%"),
            ("Average Confidence", f"{sim.confidence:.0%}" if sim.confidence else "N/A"),
            ("Average Damages", _format_dollars(sim.average_damages)),
            ("Jury Consensus", agg.get("consensus_level", "N/A")),
            ("Jurors Simulated", str(sim.juror_count)),
            ("AI Model", sim.model or "N/A"),
            ("Simulation Status", sim.status.upper()),
            ("Generated", sim.created_at.strftime("%B %d, %Y at %H:%M") if sim.created_at else "N/A"),
        ]))

    # Deliberation Summary
    elements.append(Paragraph("AI Jury Deliberation Summary", styles["SubHead"]))
    ds = agg.get("jury_deliberation_summary", "")
    if ds:
        elements.append(Paragraph(ds, styles["Body"]))
    else:
        elements.append(Paragraph("Deliberation summary not available.", styles["Body"]))

    # Confidence Distribution
    if agg.get("confidence_distribution"):
        elements.append(Paragraph("Confidence Distribution", styles["SubHead"]))
        vals = agg["confidence_distribution"]
        avg_conf = f"{sim.confidence:.0%}" if sim and sim.confidence else "N/A"
        conf_text = f"Average: {avg_conf}. Individual juror confidences: " + ", ".join(f"{v}%" for v in vals)
        elements.append(Paragraph(conf_text, styles["Body"]))

    # Decision Drivers
    if agg.get("decision_drivers"):
        elements.append(Paragraph("Decision Drivers", styles["SubHead"]))
        for d in agg["decision_drivers"][:5]:
            elements.append(Paragraph(f"• <b>{d['driver']}</b> — Referenced by {d['juror_references']} juror(s)", styles["Body"]))

    # Evidence Influence
    if agg.get("evidence_influence"):
        elements.append(Paragraph("Evidence Influence", styles["SubHead"]))
        for ev in agg["evidence_influence"][:5]:
            elements.append(Paragraph(
                f"• <b>{ev['evidence']}</b> — Score: {ev.get('influence_score','N/A')}/10 "
                f"(Mentioned by {ev['mentions']} juror(s))",
                styles["Body"],
            ))
            if ev.get("explanation"):
                elements.append(Paragraph(f"  {ev['explanation']}", styles["Small"]))

    # Witness Credibility (aggregated)
    if agg.get("witness_credibility_ranking"):
        elements.append(Paragraph("Witness Credibility (Aggregated)", styles["SubHead"]))
        w_rows = [["Witness", "Avg Score", "Assessment", "Explanation"]]
        for w in agg["witness_credibility_ranking"]:
            label = "High" if w["avg_score"] >= 7 else "Moderate" if w["avg_score"] >= 4 else "Low"
            expl = (w.get("explanation","") or "")[:80]
            w_rows.append([w["witness"], f"{w['avg_score']}/10", label, expl])
        elements.append(_styled_table(w_rows[0], w_rows[1:], col_widths=[1.3*inch, 0.8*inch, 1*inch, 3*inch]))

    # Damages Distribution
    if agg.get("damages_distribution"):
        elements.append(Paragraph("Damages Distribution", styles["SubHead"]))
        dd = agg["damages_distribution"]
        d_rows = [["", "Amount"], ["Minimum", _format_dollars(dd["minimum"])],
                  ["Median", _format_dollars(dd["median"])], ["Average", _format_dollars(dd["average"])],
                  ["Maximum", _format_dollars(dd["maximum"])]]
        t = Table(d_rows, colWidths=[2*inch, 2*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)

    # ═══════════ VERDICT PREDICTION ═══════════
    if vp:
        elements.append(PageBreak())
        elements.extend(_section("Verdict Prediction"))
        elements.append(_kv_table([
            ("Predicted Winner", vp.get("predicted_winner", "N/A")),
            ("Plaintiff Win Probability", f"{vp.get('plaintiff_win_probability','N/A')}%"),
            ("Defense Win Probability", f"{vp.get('defense_win_probability','N/A')}%"),
            ("Prediction Confidence", f"{vp.get('prediction_confidence','N/A')}%"),
            ("Litigation Risk", vp.get("litigation_risk", "N/A")),
            ("Settlement Recommendation", vp.get("settlement_recommendation", "N/A")),
            ("Expected Damages (Min)", _format_dollars(vp.get("expected_damages_min"))),
            ("Expected Damages (Most Likely)", _format_dollars(vp.get("expected_damages_most_likely"))),
            ("Expected Damages (Max)", _format_dollars(vp.get("expected_damages_max"))),
        ]))

        if vp.get("executive_summary"):
            elements.append(Paragraph("Executive Summary", styles["SubHead"]))
            elements.append(Paragraph(vp["executive_summary"], styles["Body"]))

        if vp.get("attorney_recommendations"):
            elements.append(Paragraph("Attorney Recommendations", styles["SubHead"]))
            for rec in vp["attorney_recommendations"]:
                elements.append(Paragraph(f"• {rec}", styles["Body"]))

        if vp.get("alternative_outcomes"):
            elements.append(Paragraph("Alternative Outcomes", styles["SubHead"]))
            ao = vp["alternative_outcomes"]
            ao_rows = [["Outcome", "Probability"]]
            for key, label in [("plaintiff_victory","Plaintiff Victory"), ("defense_victory","Defense Victory"), ("hung_jury","Hung Jury")]:
                if key in ao:
                    ao_rows.append([label, f"{ao[key]}%"])
            elements.append(_styled_table(ao_rows[0], ao_rows[1:], col_widths=[3*inch, 1.5*inch]))

    elements.append(PageBreak())

    # ═══════════ JUROR PROFILES ═══════════
    elements.extend(_section("Juror Profiles"))
    for i, p in enumerate(personas):
        v = next((v for v in votes if v.persona_id == p.id), None)
        bp = p.behavioral_profile or {}
        dem = p.demographics or {}

        elements.append(Paragraph(f"Juror {p.juror_number}: {p.name}", styles["SubHead"]))

        # Demographics
        dem_rows = [
            ["Age", str(dem.get("age","N/A")), "Gender", str(dem.get("gender","N/A"))],
            ["Education", str(dem.get("education","N/A")), "Occupation", str(dem.get("occupation","N/A"))],
        ]
        for row in dem_rows:
            t = Table([row], colWidths=[1*inch, 1.5*inch, 1*inch, 1.5*inch])
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(t)

        # Behavioral Profile
        bp_rows = [
            ["Political Leaning", str(bp.get("political_leaning","N/A")), "Risk Tolerance", f"{bp.get('risk_tolerance','N/A')}/10"],
            ["Empathy", f"{bp.get('empathy','N/A')}/10", "Leadership", f"{bp.get('leadership_tendency','N/A')}/10"],
            ["Trust in Experts", f"{bp.get('trust_in_experts','N/A')}/10", "Trust in Corps", f"{bp.get('trust_in_corporations','N/A')}/10"],
        ]
        for row in bp_rows:
            t = Table([row], colWidths=[1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(t)

        if p.biography:
            elements.append(Paragraph(f"<i>{p.biography}</i>", styles["Body"]))

        if v:
            vcolor = "#16a34a" if v.verdict == "plaintiff" else "#dc2626"
            elements.append(Paragraph(
                f"Verdict: <b><font color='{vcolor}'>{v.verdict.upper()}</font></b> | "
                f"Confidence: {v.confidence:.0%} | "
                f"{'Damages: ' + _format_dollars(v.damages) if v.damages else 'No damages'}",
                styles["Body"],
            ))
            if v.reasoning:
                elements.append(Paragraph(f"Reasoning: {v.reasoning}", styles["Body"]))
            # Evidence referenced per juror
            if v.evidence_used:
                eu = v.evidence_used
                if isinstance(eu, dict) and eu:
                    elements.append(Paragraph(f"<i>Evidence Referenced:</i> {', '.join(list(eu.keys())[:5])}", styles["Small"]))
            # Witness scores per juror
            if v.witness_scores:
                ws = v.witness_scores
                if isinstance(ws, dict) and ws:
                    wstr = "; ".join(f"{w}: {s}/10" for w, s in list(ws.items())[:5])
                    elements.append(Paragraph(f"<i>Witness Credibility:</i> {wstr}", styles["Small"]))

        if i < len(personas) - 1:
            elements.append(Spacer(1, 6))
            elements.append(_hr())

    # ═══════════ BUILD PDF ═══════════
    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes