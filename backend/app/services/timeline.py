"""Timeline business logic."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.repositories.timeline import TimelineRepository


class TimelineService:
    """Business logic for timeline events."""

    def __init__(self, session: Session) -> None:
        self.repo = TimelineRepository(session)

    def list_events(
        self,
        *,
        actor_code: Optional[str] = None,
        kind: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        items, total = self.repo.list_events(
            actor_code=actor_code,
            kind=kind,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total}

    def get_migration_events(self, actor_code: str) -> list[dict[str, Any]]:
        return self.repo.get_migration_events(actor_code)
