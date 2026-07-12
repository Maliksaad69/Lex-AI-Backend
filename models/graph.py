from typing import TypedDict, List, Dict
from uuid import UUID


class CaseAnalysisState(TypedDict):
    case_id: UUID

    raw_context: str

    facts: List[Dict]
    parties: List[Dict]
    witnesses: List[Dict]
    claims: List[Dict]
    evidence_links: List[Dict]
    assessments: List[Dict]
    timeline: List[Dict]
    contradictions: List[Dict]

    errors: List[str]
