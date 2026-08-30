"""Data-access layer for investigations and audit events."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Actor
from app.models.intel import Evidence, Relationship
from app.models.ops import Analyst, AuditEvent, Investigation


def list_investigations(session: Session, status: Optional[str] = None) -> list[Investigation]:
    stmt = select(Investigation).order_by(Investigation.created_at.desc())
    if status:
        stmt = stmt.where(Investigation.status == status)
    return list(session.execute(stmt).scalars().all())


def get_investigation(session: Session, code: str) -> Optional[Investigation]:
    return session.execute(
        select(Investigation).where(Investigation.code == code)
    ).scalar_one_or_none()


def get_investigation_by_id(session: Session, inv_id: str) -> Optional[Investigation]:
    return session.get(Investigation, inv_id)


def create_investigation(
    session: Session,
    *,
    code: str,
    title: str,
    description: str,
    lead_analyst_id: str,
    targets: list[str] | None = None,
    parameters: dict | None = None,
) -> Investigation:
    inv = Investigation(
        code=code,
        title=title,
        description=description,
        status="draft",
        lead_analyst_id=lead_analyst_id,
        targets=targets or [],
        parameters=parameters or {},
        participants=[],
    )
    session.add(inv)
    session.flush()
    return inv


def update_investigation_status(
    session: Session,
    inv: Investigation,
    *,
    new_status: str,
    analyst_id: str | None = None,
) -> AuditEvent:
    old_status = inv.status
    inv.status = new_status
    audit = AuditEvent(
        analyst_id=analyst_id,
        is_system=False,
        action="investigation_status_changed",
        resource_type="investigations",
        resource_id=inv.id,
        before_json={"status": old_status},
        after_json={"status": new_status},
        occurred_at=datetime.utcnow(),
    )
    session.add(audit)
    session.flush()
    return audit


def add_investigation_note(
    session: Session,
    inv: Investigation,
    *,
    note: str,
    analyst_id: str | None = None,
) -> AuditEvent:
    audit = AuditEvent(
        analyst_id=analyst_id,
        is_system=False,
        action="investigation_note_added",
        resource_type="investigations",
        resource_id=inv.id,
        after_json={"note": note},
        note=note,
        occurred_at=datetime.utcnow(),
    )
    session.add(audit)
    session.flush()
    return audit


def decide_relationship(
    session: Session,
    *,
    relationship_id: str,
    decision: str,  # accepted | rejected | uncertain
    analyst_id: str | None = None,
    review_note: str | None = None,
) -> tuple[Relationship, AuditEvent]:
    rel = session.get(Relationship, relationship_id)
    if rel is None:
        raise ValueError(f"Relationship {relationship_id} not found")

    old_status = rel.status
    rel.status = decision
    rel.reviewed_by = analyst_id
    rel.reviewed_at = datetime.utcnow()
    rel.review_note = review_note

    audit = AuditEvent(
        analyst_id=analyst_id,
        is_system=False,
        action="relationship_decided",
        resource_type="relationships",
        resource_id=rel.id,
        before_json={"status": old_status},
        after_json={"status": decision, "review_note": review_note},
        note=review_note,
        occurred_at=datetime.utcnow(),
    )
    session.add(audit)
    session.flush()
    return rel, audit


def get_analyst_by_username(session: Session, username: str) -> Optional[Analyst]:
    return session.execute(
        select(Analyst).where(Analyst.username == username)
    ).scalar_one_or_none()


def get_audit_events(
    session: Session,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    analyst_id: str | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc())
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditEvent.resource_id == resource_id)
    if analyst_id:
        stmt = stmt.where(AuditEvent.analyst_id == analyst_id)
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())
