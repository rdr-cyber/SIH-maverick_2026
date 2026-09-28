"""Monitoring API endpoints.

Reports system status derived from the database — NOT live autonomous
collection.  Do not claim live scanning unless actually implemented.

Provides:
- System overview (entity counts, task backend status)  - Source scan status (last_scanned_at, trust_level)
- Relationship breakdown (by status, by band)
- Timeline event summary
- Recent errors from audit log
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.core.config import settings
from app.core.tasks import get_task_backend
from app.models.identity import Actor, Identifier, Persona, Source
from app.models.intel import Evidence, Relationship, TimelineEvent
from app.models.ops import AuditEvent

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/monitoring", tags=["monitoring"])


@router.get("/overview", summary="System monitoring overview")
def overview(session: DbSession) -> dict:
    """Aggregate counts and system status."""

    # Entity counts
    source_count = session.execute(select(func.count(Source.id))).scalar() or 0
    actor_count = session.execute(select(func.count(Actor.id))).scalar() or 0
    persona_count = session.execute(select(func.count(Persona.id))).scalar() or 0
    identifier_count = session.execute(select(func.count(Identifier.id))).scalar() or 0
    relationship_count = session.execute(select(func.count(Relationship.id))).scalar() or 0
    evidence_count = session.execute(select(func.count(Evidence.id))).scalar() or 0
    timeline_count = session.execute(select(func.count(TimelineEvent.id))).scalar() or 0

    # Task backend status
    try:
        tb = get_task_backend()
        task_status = {
            "backend": type(tb).__name__,
            "available": tb.is_available(),
        }
    except Exception as e:
        task_status = {"backend": "error", "available": False, "error": str(e)}

    # Last scan across all sources
    last_scan = session.execute(
        select(func.max(Source.last_scanned_at))
    ).scalar()

    return {
        "app_mode": settings.app_mode,
        "entities": {
            "sources": source_count,
            "actors": actor_count,
            "personas": persona_count,
            "identifiers": identifier_count,
            "relationships": relationship_count,
            "evidence": evidence_count,
            "timeline_events": timeline_count,
        },
        "last_scan_at": last_scan.isoformat() if last_scan else None,
        "task_backend": task_status,
        "disclaimer": (
            "This system reports database-derived metrics. "
            "It does not perform live autonomous collection."
        ),
    }


@router.get("/sources", summary="Source scan status")
def source_status(session: DbSession) -> list[dict]:
    """Each source's last scan time, trust level, and artifact count."""
    sources = list(session.execute(select(Source).order_by(Source.name)).scalars().all())
    results = []
    for src in sources:
        actor_count = session.execute(
            select(func.count(Actor.id)).where(Actor.primary_source_id == src.id)
        ).scalar() or 0
        persona_count = session.execute(
            select(func.count(Persona.id)).where(Persona.source_id == src.id)
        ).scalar() or 0
        identifier_count = session.execute(
            select(func.count(Identifier.id)).where(Identifier.source_id == src.id)
        ).scalar() or 0
        results.append({
            "id": src.id,
            "name": src.name,
            "kind": src.kind,
            "trust_level": src.trust_level,
            "enabled": src.enabled,
            "last_scanned_at": src.last_scanned_at.isoformat() if src.last_scanned_at else None,
            "actors": actor_count,
            "personas": persona_count,
            "identifiers": identifier_count,
        })
    return results


@router.get("/relationships", summary="Relationship breakdown")
def relationship_breakdown(session: DbSession) -> dict:
    """Relationships grouped by status and band."""
    # By status
    status_rows = session.execute(
        select(Relationship.status, func.count(Relationship.id))
        .group_by(Relationship.status)
    ).all()
    by_status = {row[0]: row[1] for row in status_rows}

    # By band
    band_rows = session.execute(
        select(Relationship.band, func.count(Relationship.id))
        .group_by(Relationship.band)
    ).all()
    by_band = {row[0]: row[1] for row in band_rows}

    # High-confidence pending (need analyst review)
    high_pending = session.execute(
        select(func.count(Relationship.id))
        .where(Relationship.status == "pending")
        .where(Relationship.confidence >= 70)
    ).scalar() or 0

    return {
        "by_status": by_status,
        "by_band": by_band,
        "high_confidence_pending": high_pending,
    }


@router.get("/timeline", summary="Timeline event summary")
def timeline_summary(session: DbSession) -> dict:
    """Event counts by kind."""
    rows = session.execute(
        select(TimelineEvent.kind, func.count(TimelineEvent.id))
        .group_by(TimelineEvent.kind)
    ).all()
    by_kind = {row[0]: row[1] for row in rows}

    total = sum(by_kind.values())
    last_event = session.execute(
        select(TimelineEvent.occurred_at).order_by(TimelineEvent.occurred_at.desc()).limit(1)
    ).scalar()

    return {
        "total": total,
        "by_kind": by_kind,
        "last_event_at": last_event.isoformat() if last_event else None,
    }


@router.get("/errors", summary="Recent errors from audit log")
def recent_errors(
    session: DbSession,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Recent audit events that may indicate errors or anomalies."""
    events = list(
        session.execute(
            select(AuditEvent)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(limit)
        ).scalars().all()
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "analyst_id": e.analyst_id,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "note": e.note,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]
