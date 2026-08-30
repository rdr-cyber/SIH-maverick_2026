"""Timeline repository: chronological event queries.

The timeline denormalizes every timestamped artifact into a single flat
table for fast chronological queries.  This repository provides the
query layer for the Timeline UI.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.identity import Actor
from app.models.intel import TimelineEvent


class TimelineRepository:
    """Read access for timeline events."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_events(
        self,
        *,
        actor_code: Optional[str] = None,
        kind: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List timeline events with optional filters.

        Returns events sorted chronologically with actor name resolved.
        """
        stmt = select(TimelineEvent)

        if actor_code:
            actor = self.session.execute(
                select(Actor).where(Actor.code == actor_code)
            ).scalar_one_or_none()
            if actor:
                stmt = stmt.where(TimelineEvent.actor_id == actor.id)
            else:
                return [], 0

        if kind:
            stmt = stmt.where(TimelineEvent.kind == kind)
        if since:
            stmt = stmt.where(TimelineEvent.occurred_at >= since)
        if until:
            stmt = stmt.where(TimelineEvent.occurred_at <= until)

        # Count
        count_stmt = select(func.count(TimelineEvent.id))
        if actor_code:
            actor = self.session.execute(
                select(Actor).where(Actor.code == actor_code)
            ).scalar_one_or_none()
            if actor:
                count_stmt = count_stmt.where(TimelineEvent.actor_id == actor.id)
        if kind:
            count_stmt = count_stmt.where(TimelineEvent.kind == kind)
        if since:
            count_stmt = count_stmt.where(TimelineEvent.occurred_at >= since)
        if until:
            count_stmt = count_stmt.where(TimelineEvent.occurred_at <= until)
        total = self.session.execute(count_stmt).scalar_one()

        # Fetch
        stmt = stmt.order_by(TimelineEvent.occurred_at.asc())
        stmt = stmt.limit(limit).offset(offset)
        events = self.session.execute(stmt).scalars().all()

        # Resolve actor names
        actor_cache: dict[str, str] = {}
        results = []
        for e in events:
            actor_name = None
            if e.actor_id:
                if e.actor_id not in actor_cache:
                    name = self.session.execute(
                        select(Actor.code).where(Actor.id == e.actor_id)
                    ).scalar_one_or_none()
                    actor_cache[e.actor_id] = name or e.actor_id
                actor_name = actor_cache[e.actor_id]
            results.append({
                "id": e.id,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "kind": e.kind,
                "actor_id": e.actor_id,
                "actor_code": actor_name,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "title": e.title,
                "detail": e.detail,
                "confidence_delta": e.confidence_delta,
                "source_id": e.source_id,
                "metadata": e.metadata_json or {},
            })

        return results, int(total)

    def get_migration_events(self, actor_code: str) -> list[dict[str, Any]]:
        """Get events showing a persona migration story.

        Returns appearance, disappearance, and activity events for an actor,
        useful for showing the migration narrative (e.g. darkmerchant → shadow_vendor).
        """
        actor = self.session.execute(
            select(Actor).where(Actor.code == actor_code)
        ).scalar_one_or_none()
        if not actor:
            return []

        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.actor_id == actor.id)
            .where(TimelineEvent.kind.in_(["appearance", "disappearance", "activity", "pgp_seen", "wallet_associated"]))
            .order_by(TimelineEvent.occurred_at.asc())
        )
        events = self.session.execute(stmt).scalars().all()
        return [
            {
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "kind": e.kind,
                "title": e.title,
                "detail": e.detail,
            }
            for e in events
        ]
