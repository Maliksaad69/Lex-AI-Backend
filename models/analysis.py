from typing import List, Optional
from pydantic import BaseModel


class Party(BaseModel):
    name: str
    role: str  # plaintiff, defendant, witness, expert
    description: str


class Evidence(BaseModel):
    document_ref: str
    page: int
    excerpt: str
    weight_score: int  # 1–10 based on the rubric
    credibility_assessment: str


class Claim(BaseModel):
    cause_of_action: str
    supporting_evidence: List[Evidence]
    weaknesses: List[str]
    strength_score: int


class CaseAnalysisState(BaseModel):
    case_id: str
    case_summary: Optional[str] = None
    parties: List[Party] = []
    claims: List[Claim] = []
    # Add other fields: witnesses, timeline, contradictions, missing_evidence
    review_status: str = "pending"
