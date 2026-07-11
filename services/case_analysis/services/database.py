from sqlmodel import Session

from db.models import (
    ExtractedFact,
    Party,
    Claim,
    EvidenceLink,
    TimelineEvent,
    Contradiction,
)


class DatabaseService:

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------
    # Facts
    # -----------------------------

    def save_facts(self, case_id, facts):

        ids = []

        for fact in facts:

            db_fact = ExtractedFact(
                case_id=case_id,
                statement=fact["statement"],
                source_document=fact.get("source_document"),
                page_number=fact.get("page"),
                importance_score=fact.get("importance", 5),
                is_disputed=fact.get("disputed", False),
                ai_confidence=fact.get("confidence", 0.0),
            )

            self.session.add(db_fact)
            self.session.flush()

            ids.append(db_fact.id)

        return ids

    # -----------------------------
    # Parties
    # -----------------------------

    def save_parties(self, case_id, parties):

        for party in parties:

            self.session.add(
                Party(
                    case_id=case_id,
                    name=party["name"],
                    role=party["role"],
                    type=party["type"],
                )
            )

    # -----------------------------
    # Claims
    # -----------------------------

    def save_claims(self, case_id, claims):

        ids = []

        for claim in claims:

            db_claim = Claim(
                case_id=case_id,
                claim_type=claim["claim_type"],
                legal_basis=claim.get("legal_basis"),
                elements=claim.get("elements"),
            )

            self.session.add(db_claim)
            self.session.flush()

            ids.append(db_claim.id)

        return ids

    # -----------------------------
    # Evidence
    # -----------------------------

    def save_evidence_links(self, links):

        for link in links:

            self.session.add(
                EvidenceLink(
                    claim_id=link["claim_id"],
                    fact_id=link["fact_id"],
                    relationship=link["relationship"],
                    weight_score=link["weight_score"],
                    rationale=link.get("rationale"),
                )
            )

    # -----------------------------
    # Timeline
    # -----------------------------

    def save_timeline(self, case_id, timeline):

        for event in timeline:

            self.session.add(
                TimelineEvent(
                    case_id=case_id,
                    event_date=event.get("date"),
                    description=event["event"],
                    significance=event.get("significance"),
                )
            )

    # -----------------------------
    # Contradictions
    # -----------------------------

    def save_contradictions(self, case_id, contradictions):

        for contradiction in contradictions:

            self.session.add(
                Contradiction(
                    case_id=case_id,
                    fact_a_id=contradiction["fact_a_id"],
                    fact_b_id=contradiction["fact_b_id"],
                    nature=contradiction.get("nature"),
                    impact=contradiction.get("impact"),
                )
            )

    # -----------------------------
    # Commit
    # -----------------------------

    def commit(self):

        self.session.commit()