"""Case database model — SQLModel table for the cases table. Uses UUID PK."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Case(SQLModel, table=True):
    __tablename__ = "cases"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    case_name: str = Field(index=True)
    claim_type: Optional[str] = Field(default="")
    current_stage: Optional[str] = Field(default="draft")
    plaintiff_name: Optional[str] = Field(default="")
    plaintiff_counsel: Optional[str] = Field(default="")
    defense_name: Optional[str] = Field(default="")
    defense_counsel: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    court: Optional[str] = Field(default="")
    county: Optional[str] = Field(default="")
    trial_date: Optional[str] = Field(default="")
    summary: Optional[str] = Field(default="")
    analysis: Optional[str] = Field(default="Not started")
    document_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)