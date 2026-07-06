"""Cases CRUD router — create, read, update, delete litigation cases."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from db.session import get_session
from db.models.case import Case
from routes.auth import get_current_user

router = APIRouter(prefix="/cases", tags=["cases"])


def _case_to_dict(case: Case) -> dict:
    """Convert a Case ORM object to the JSON shape the frontend expects."""
    return {
        "id": str(case.id),
        "user_id": case.user_id,
        "caseName": case.case_name,
        "claimType": case.claim_type,
        "currentStage": case.current_stage,
        "plaintiffName": case.plaintiff_name,
        "plaintiffCounsel": case.plaintiff_counsel,
        "defenseName": case.defense_name,
        "defenseCounsel": case.defense_counsel,
        "state": case.state,
        "court": case.court,
        "county": case.county,
        "trialDate": case.trial_date,
        "summary": case.summary,
        "analysis": case.analysis,
        "documentCount": case.document_count,
        "createdAt": case.created_at.isoformat() if case.created_at else None,
        "updatedAt": case.updated_at.isoformat() if case.updated_at else None,
    }


@router.get("/")
def list_cases(
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return all cases for the authenticated user."""
    stmt = (
        select(Case)
        .where(Case.user_id == user_id)
        .order_by(Case.updated_at.desc())
    )
    cases = session.exec(stmt).all()
    return [_case_to_dict(c) for c in cases]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_case(
    request: Request,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Create a new case for the authenticated user."""
    payload = await request.json()

    case = Case(
        user_id=user_id,
        case_name=payload.get("caseName", "Untitled Case"),
        claim_type=payload.get("claimType", ""),
        current_stage=payload.get("currentStage", "draft"),
        plaintiff_name=payload.get("plaintiffName", ""),
        plaintiff_counsel=payload.get("plaintiffCounsel", ""),
        defense_name=payload.get("defenseName", ""),
        defense_counsel=payload.get("defenseCounsel", ""),
        state=payload.get("state", ""),
        court=payload.get("court", ""),
        county=payload.get("county", ""),
        trial_date=payload.get("trialDate", ""),
        summary=payload.get("summary", ""),
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return _case_to_dict(case)


@router.get("/{case_id}")
def get_case(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return a single case by ID (must belong to the authenticated user)."""
    case = session.get(Case, case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_to_dict(case)


@router.patch("/{case_id}")
async def update_case(
    case_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Update fields on an existing case."""
    case = session.get(Case, case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Case not found")

    payload = await request.json()

    field_map = {
        "caseName": "case_name",
        "claimType": "claim_type",
        "currentStage": "current_stage",
        "plaintiffName": "plaintiff_name",
        "plaintiffCounsel": "plaintiff_counsel",
        "defenseName": "defense_name",
        "defenseCounsel": "defense_counsel",
        "state": "state",
        "court": "court",
        "county": "county",
        "trialDate": "trial_date",
        "summary": "summary",
        "analysis": "analysis",
    }

    for json_key, db_field in field_map.items():
        if json_key in payload:
            setattr(case, db_field, payload[json_key])

    case.updated_at = datetime.utcnow()
    session.add(case)
    session.commit()
    session.refresh(case)
    return _case_to_dict(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: UUID,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Delete a case (must belong to the authenticated user)."""
    case = session.get(Case, case_id)
    if not case or case.user_id != user_id:
        raise HTTPException(status_code=404, detail="Case not found")
    session.delete(case)
    session.commit()