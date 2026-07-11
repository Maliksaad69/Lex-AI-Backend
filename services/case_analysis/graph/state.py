from typing import TypedDict
from uuid import UUID


class Fact(TypedDict):
    statement: str
    source_document: str | None
    page: str | None
    importance: int
    disputed: bool
    confidence: float


class Party(TypedDict):
    name: str
    role: str
    type: str


class Claim(TypedDict):
    claim_type: str
    legal_basis: str | None
    elements: list[str]


class EvidenceLink(TypedDict):
    claim_index: int
    fact_index: int
    relationship: str
    weight_score: int
    rationale: str


class TimelineEvent(TypedDict):
    date: str
    event: str
    significance: str


class Contradiction(TypedDict):
    fact_a: int
    fact_b: int
    nature: str
    impact: str


class Assessment(TypedDict):
    claim_index: int
    overall_strength: int
    strengths: list[str]
    weaknesses: list[str]
    risk_level: str
    recommendations: list[str]


class CaseAnalysisState(TypedDict):
    case_id: UUID

    raw_context: str

    facts: list[Fact]

    parties: list[Party]

    claims: list[Claim]

    evidence_links: list[EvidenceLink]

    timeline: list[TimelineEvent]

    assessments: list[Assessment]

    contradictions: list[Contradiction]

    errors: list[str]