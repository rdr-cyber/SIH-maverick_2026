"""Infrastructure repository: metadata-oriented intelligence.

Aggregates domain, onion_service, and other infrastructure identifiers
with their provenance (source, timestamp).  Every observation traces
back to exactly one source — this is the provenance guarantee.

This module is metadata-only.  It does not perform exploitation,
unauthorized access, or any active interaction with observed systems.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.identity import Actor, Identifier, Persona, Source


# Infrastructure-relevant identifier kinds
INFRA_KINDS = ("domain", "onion_service")


class InfrastructureRepository:
    """Read access for infrastructure observations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_infrastructure(
        self,
        *,
        kind: Optional[str] = None,
        actor_code: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List infrastructure observations with provenance.

        Returns domain and onion_service identifiers with their source
        and actor context.
        """
        stmt = select(Identifier).options(
            selectinload(Identifier.source),
        )

        # Filter to infrastructure kinds
        if kind:
            stmt = stmt.where(Identifier.kind == kind)
        else:
            stmt = stmt.where(Identifier.kind.in_(INFRA_KINDS))

        # Filter by actor
        if actor_code:
            actor = self.session.execute(
                select(Actor).where(Actor.code == actor_code)
            ).scalar_one_or_none()
            if actor:
                stmt = stmt.where(Identifier.actor_id == actor.id)
            else:
                return [], 0

        # Count
        count_stmt = select(func.count(Identifier.id))
        if kind:
            count_stmt = count_stmt.where(Identifier.kind == kind)
        else:
            count_stmt = count_stmt.where(Identifier.kind.in_(INFRA_KINDS))
        if actor_code:
            actor = self.session.execute(
                select(Actor).where(Actor.code == actor_code)
            ).scalar_one_or_none()
            if actor:
                count_stmt = count_stmt.where(Identifier.actor_id == actor.id)
        total = self.session.execute(count_stmt).scalar_one()

        # Fetch
        stmt = stmt.order_by(Identifier.kind, Identifier.value)
        stmt = stmt.limit(limit).offset(offset)
        items = self.session.execute(stmt).scalars().all()

        # Resolve actor names
        actor_cache: dict[str, str] = {}
        results = []
        for i in items:
            if i.actor_id not in actor_cache:
                name = self.session.execute(
                    select(Actor.code).where(Actor.id == i.actor_id)
                ).scalar_one_or_none()
                actor_cache[i.actor_id] = name or i.actor_id
            results.append({
                "id": i.id,
                "kind": i.kind,
                "value": i.value,
                "normalized_value": i.normalized_value,
                "label": i.label,
                "attributes": i.attributes or {},
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_seen": i.last_seen.isoformat() if i.last_seen else None,
                "actor_code": actor_cache[i.actor_id],
                "source_name": i.source.name if i.source else None,
                "source_kind": i.source.kind if i.source else None,
                "source_reliability": i.source.trust_level if i.source else None,
            })

        return results, int(total)

    def get_infrastructure_clusters(self) -> list[dict[str, Any]]:
        """Find shared infrastructure — actors using the same domain or onion.

        This is the key intelligence signal: shared infrastructure indicates
        potential actor overlap.
        """
        # Find identifiers that appear for multiple actors
        stmt = (
            select(
                Identifier.normalized_value,
                Identifier.kind,
                func.count(func.distinct(Identifier.actor_id)).label("actor_count"),
                func.group_concat(func.distinct(Actor.code)).label("actors"),
            )
            .join(Actor, Identifier.actor_id == Actor.id)
            .where(Identifier.kind.in_(INFRA_KINDS))
            .group_by(Identifier.normalized_value, Identifier.kind)
            .having(func.count(func.distinct(Identifier.actor_id)) > 1)
        )
        rows = self.session.execute(stmt).all()

        clusters = []
        for row in rows:
            clusters.append({
                "value": row.normalized_value,
                "kind": row.kind,
                "actor_count": row.actor_count,
                "actors": [a.strip() for a in (row.actors or "").split(",") if a.strip()],
            })

        return clusters

    def get_actor_infrastructure(self, actor_code: str) -> dict[str, Any]:
        """Get all infrastructure for a specific actor with provenance."""
        actor = self.session.execute(
            select(Actor).where(Actor.code == actor_code)
        ).scalar_one_or_none()
        if not actor:
            return {"actor": None, "identifiers": []}

        stmt = (
            select(Identifier)
            .where(Identifier.actor_id == actor.id)
            .where(Identifier.kind.in_(INFRA_KINDS))
            .options(selectinload(Identifier.source))
            .order_by(Identifier.kind, Identifier.value)
        )
        items = self.session.execute(stmt).scalars().all()

        return {
            "actor": {
                "code": actor.code,
                "display_name": actor.display_name,
            },
            "identifiers": [
                {
                    "kind": i.kind,
                    "value": i.value,
                    "label": i.label,
                    "attributes": i.attributes or {},
                    "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                    "last_seen": i.last_seen.isoformat() if i.last_seen else None,
                    "source_name": i.source.name if i.source else None,
                    "source_reliability": i.source.trust_level if i.source else None,
                }
                for i in items
            ],
        }
