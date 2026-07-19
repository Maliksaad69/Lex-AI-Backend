from uuid import UUID, uuid4
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class Simulation(SQLModel, table=True):
    __tablename__ = "simulations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)

    status: str = Field(default="pending", max_length=30)
    model: Optional[str] = None
    temperature: Optional[float] = None
    juror_count: int = Field(default=12)

    plaintiff_votes: int = Field(default=0)
    defense_votes: int = Field(default=0)
    confidence: Optional[float] = None
    average_damages: Optional[float] = None
    summary: Optional[str] = None

    # Jury composition spec
    pool_spec: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )

    # Case stimulus presented to each juror
    stimulus: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Full aggregation results (persisted JSON for GET endpoint)
    aggregation_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class Persona(SQLModel, table=True):
    __tablename__ = "personas"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    simulation_id: UUID = Field(foreign_key="simulations.id", index=True)
    juror_number: int

    # Optional display name
    name: Optional[str] = None

    # Demographic information
    demographics: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )

    # Personality / behavioral attributes
    behavioral_profile: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )

    # Short AI-generated background
    biography: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Vote(SQLModel, table=True):
    __tablename__ = "votes"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    simulation_id: UUID = Field(foreign_key="simulations.id", index=True)
    persona_id: UUID = Field(foreign_key="personas.id", index=True)

    verdict: str
    confidence: float
    damages: Optional[float] = None
    reasoning: str

    evidence_used: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )
    witness_scores: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
    )

    prompt_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)