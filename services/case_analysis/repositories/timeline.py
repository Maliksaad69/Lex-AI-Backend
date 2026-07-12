"""Repository for TimelineEvent — persists, reads, and deletes timeline records."""

from typing import Any, List
from uuid import UUID

from sqlmodel import Session, select

from db.models.analysis import TimelineEvent


def save_timeline(
    session: Session, case_id: UUID, events: List[dict[str, Any]]
) -> List[TimelineEvent]:
    """Bulk-insert timeline events for a case."""
    instances = []
    for ev in events:
        obj = TimelineEvent(
            case_id=case_id,
            event_date=ev.get("date"),
            description=ev.get("event", ""),
            significance=ev.get("significance"),
        )
        session.add(obj)
        instances.append(obj)
    session.commit()
    for obj in instances:
        session.refresh(obj)
    return instances


def get_timeline(session: Session, case_id: UUID) -> List[dict[str, Any]]:
    """Return all timeline events for *case_id* as plain dicts."""
    stmt = select(TimelineEvent).where(TimelineEvent.case_id == case_id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": str(r.id),
            "date": r.event_date,
            "event": r.description,
            "significance": r.significance,
        }
        for r in rows
    ]


def delete_case_timeline(session: Session, case_id: UUID) -> None:
    """Remove all timeline events belonging to *case_id*."""
    stmt = select(TimelineEvent).where(TimelineEvent.case_id == case_id)
    for obj in session.exec(stmt).all():
        session.delete(obj)
    session.commit()
