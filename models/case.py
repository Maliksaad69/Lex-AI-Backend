from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    jurisdiction: Optional[str] = ""
    parties: Optional[dict] = {}
    tags: Optional[List[str]] = []

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    jurisdiction: Optional[str] = None
    parties: Optional[dict] = None
    tags: Optional[List[str]] = None

class CaseResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    case_number: str
    title: str
    description: str
    status: str
    jurisdiction: str
    parties: dict
    tags: List[str]
    document_count: int = 0    # computed field
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True

