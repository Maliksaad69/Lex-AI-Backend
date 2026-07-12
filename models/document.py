from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: Optional[str] = None
    case_id: str
    filename: str
    original_path: str
    case: str
    content_type: str
    file_size: int
    pages: int = 0
    extracted_text: str = ""
    uploaded_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DocumentCreate(BaseModel):

    user_id: str
    case_id: str
    document_id: str
    filename: str
    file_size: int
    file_type: str
    pages: int
    status: str
    tags: List[str]
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


class DocumentResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    case_id: str
    document_id: str
    filename: str
    file_size: int
    file_type: str
    pages: int
    status: str
    tags: List[str]
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
