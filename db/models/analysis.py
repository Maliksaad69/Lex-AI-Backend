from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class ExtractedFact(SQLModel, table=True):
    __tablename__ = "extracted_facts"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    statement: str
    source_document: Optional[str] = None
    page_number: Optional[str] = None
    importance_score: int = Field(default=5)
    is_disputed: bool = False
    ai_confidence: float = Field(default=0.0)
    human_reviewed: bool = False


class Party(SQLModel, table=True):
    __tablename__ = "parties"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    name: str
    role: str  # "Plaintiff", "Defendant", "Witness"
    type: str  # "party" or "witness"


class Claim(SQLModel, table=True):
    __tablename__ = "claims"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    claim_type: str  # "Negligence", "Breach of Contract"
    legal_basis: Optional[str] = None
    elements: Optional[str] = None  # JSONB array stored as string


class EvidenceLink(SQLModel, table=True):
    __tablename__ = "evidence_links"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    claim_id: UUID = Field(foreign_key="claims.id")
    fact_id: UUID = Field(foreign_key="extracted_facts.id")
    relationship: str  # "supports" or "undermines"
    weight_score: int
    rationale: Optional[str] = None


class TimelineEvent(SQLModel, table=True):
    __tablename__ = "timeline_events"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    event_date: Optional[str] = None
    description: str
    significance: Optional[str] = None


class Contradiction(SQLModel, table=True):
    __tablename__ = "contradictions"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    fact_a_id: UUID = Field(foreign_key="extracted_facts.id")
    fact_b_id: UUID = Field(foreign_key="extracted_facts.id")
    nature: Optional[str] = None
    impact: Optional[str] = None


class Assessment(SQLModel, table=True):
    __tablename__ = "assessments"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    claim_id: UUID = Field(foreign_key="claims.id")
    overall_strength: int = Field(default=5)
    strengths: Optional[str] = None  # JSON list as string
    weaknesses: Optional[str] = None  # JSON list as string
    risk_level: str = Field(default="medium")
    recommendations: Optional[str] = None  # JSON list as string
