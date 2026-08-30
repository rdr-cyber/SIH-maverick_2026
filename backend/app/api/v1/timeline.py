"""Timeline API endpoints.

Chronological view of all intelligence events — appearances, migrations,
PGP sightings, wallet associations, relationship milestones, and analyst actions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.intel import TIMELINE_EVENT_KINDS
from app.services.timeline import TimelineService

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get(
    "",
    summary="List timeline events with filters",
)
def list_timeline(
    session: DbSession,
    actor: Annotated[Optional[str], Query(description="Actor code to filter by")] = None,
    kind: Annotated[Optional[str], Query(description=f"One of {TIMELINE_EVENT_KINDS}")] = None,
    since: Annotated[Optional[datetime], Query(description="Start date (ISO format)")] = None,
    until: Annotated[Optional[datetime], Query(description="End date (ISO format)")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """List timeline events sorted chronologically.

    Supports filtering by actor, event kind, and date range.
    """
    svc = TimelineService(session)
    return svc.list_events(
        actor_code=actor, kind=kind, since=since, until=until,
        limit=limit, offset=offset,
    )


@router.get(
    "/migration/{actor_code}",
    summary="Get migration story for an actor",
)
def get_migration(
    session: DbSession,
    actor_code: str,
) -> list[dict]:
    """Get the migration narrative for an actor.

    Returns appearance, disappearance, and activity events that show
    the persona migration story (e.g. darkmerchant → shadow_vendor).
    """
    svc = TimelineService(session)
    return svc.get_migration_events(actor_code)
