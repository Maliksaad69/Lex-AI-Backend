"""Document database model — SQLModel table for uploaded documents."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    filename: str = Field(index=True)
    file_type: str = Field(default="")
    file_size: int = Field(default=0)
    file_path: str = Field(default="")
    page_count: int = Field(default=0)
    chunks_count: int = Field(default=0)
    qdrant_document_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)