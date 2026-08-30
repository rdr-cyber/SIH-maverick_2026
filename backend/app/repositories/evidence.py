"""Data access for relationships and evidence.

The repository answers the core product question:
    WHY ARE THESE TWO PERSONAS CONNECTED?

Every query returns data that traces back to observed facts and derived signals,
never presenting correlation as confirmed identity.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.identity import Actor
from app.models.intel import Evidence, Relationship


class EvidenceRepository:
    """Read access for relationships and their supporting evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_relationships(
        self,
        *,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List relationships with resolved actor names.

        Returns list of dicts with relationship + from_name/to_name resolved.
        """
        stmt = select(Relationship)
        if kind:
            stmt = stmt.where(Relationship.kind == kind)
        if status:
            stmt = stmt.where(Relationship.status == status)
        if min_confidence is not None:
            stmt = stmt.where(Relationship.confidence >= min_confidence)
        stmt = stmt.order_by(Relationship.confidence.desc())
        total = self.session.execute(
            select(func.count(Relationship.id)).where(*(
                [Relationship.kind == kind] if kind else []
            ))
        ).scalar_one()

        stmt = stmt.limit(limit).offset(offset)
        rels = self.session.execute(stmt).scalars().all()

        # Resolve actor names
        results = []
        for r in rels:
            from_name = self._resolve_actor_name(r.from_id)
            to_name = self._resolve_actor_name(r.to_id)
            results.append({
                "relationship": r,
                "from_name": from_name or r.from_id,
                "to_name": to_name or r.to_id,
            })
        return results, int(total)

    def get_relationship(self, code: str) -> Optional[Relationship]:
        """Get one relationship by code."""
        stmt = select(Relationship).where(Relationship.code == code)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_evidence_for_relationship(self, rel_id: str) -> list[Evidence]:
        """Get all evidence items supporting a relationship."""
        stmt = (
            select(Evidence)
            .where(Evidence.relationship_id == rel_id)
            .order_by(Evidence.score_contribution.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_relationship_with_evidence(self, code: str) -> Optional[dict[str, Any]]:
        """Get a relationship plus its evidence chain and resolved actor names.

        This is the core query that powers the WHY panel.
        """
        rel = self.get_relationship(code)
        if rel is None:
            return None

        evidence = self.get_evidence_for_relationship(rel.id)
        from_name = self._resolve_actor_name(rel.from_id)
        to_name = self._resolve_actor_name(rel.to_id)

        return {
            "relationship": rel,
            "from_name": from_name or rel.from_id,
            "to_name": to_name or rel.to_id,
            "evidence": evidence,
        }

    def list_all_evidence(
        self,
        *,
        relationship_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Evidence]:
        """List evidence items with optional filters."""
        stmt = select(Evidence)
        if relationship_id:
            stmt = stmt.where(Evidence.relationship_id == relationship_id)
        if kind:
            stmt = stmt.where(Evidence.kind == kind)
        stmt = stmt.order_by(Evidence.score_contribution.desc())
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def _resolve_actor_name(self, actor_id: str) -> Optional[str]:
        """Look up an actor's display_name by ID."""
        row = self.session.execute(
            select(Actor.display_name).where(Actor.id == actor_id)
        ).scalar_one_or_none()
        return row
