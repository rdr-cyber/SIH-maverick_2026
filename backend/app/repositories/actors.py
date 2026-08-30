"""PostgreSQL/SQLite data access for the identity domain.

The repository is the seam between business logic and the relational store.
Everything here is expressed in portable SQLAlchemy Core/ORM constructs, so
the same code runs against SQLite (local) and PostgreSQL (production).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.identity import Actor, Identifier, Persona, Source

# risk_level is stored as text; sorting needs an explicit severity order.
_RISK_ORDER = case(
    {"critical": 4, "high": 3, "moderate": 2, "low": 1},
    value=Actor.risk_level,
    else_=0,
)

SORTABLE = {
    "display_name": Actor.display_name,
    "risk": _RISK_ORDER,
    "confidence": Actor.attribution_confidence,
    "last_seen": Actor.last_seen,
    "last_scan_at": Actor.last_scan_at,
}


@dataclass(slots=True)
class ActorRow:
    """An actor plus its aggregate counts, as needed by list views."""

    actor: Actor
    persona_count: int
    identifier_count: int


class ActorRepository:
    """Read/write access to actors, personas and identifiers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- counts -----------------------------------------------------------
    @staticmethod
    def _count_subqueries() -> tuple[Any, Any]:
        personas = (
            select(func.count(Persona.id))
            .where(Persona.actor_id == Actor.id)
            .correlate(Actor)
            .scalar_subquery()
            .label("persona_count")
        )
        identifiers = (
            select(func.count(Identifier.id))
            .where(Identifier.actor_id == Actor.id)
            .correlate(Actor)
            .scalar_subquery()
            .label("identifier_count")
        )
        return personas, identifiers

    # ---- filtering --------------------------------------------------------
    def _apply_filters(
        self,
        stmt: Select[Any],
        *,
        query: Optional[str],
        risk_level: Optional[str],
        category: Optional[str],
        status: Optional[str],
    ) -> Select[Any]:
        if query:
            needle = f"%{query.strip()}%"
            # Search reaches into personas and identifiers so an analyst can
            # paste a handle, PGP fingerprint or wallet address and land on
            # the owning actor.
            persona_hit = (
                select(Persona.id)
                .where(Persona.actor_id == Actor.id, Persona.name.ilike(needle))
                .correlate(Actor)
                .exists()
            )
            identifier_hit = (
                select(Identifier.id)
                .where(
                    Identifier.actor_id == Actor.id,
                    or_(
                        Identifier.value.ilike(needle),
                        Identifier.normalized_value.ilike(needle),
                    ),
                )
                .correlate(Actor)
                .exists()
            )
            stmt = stmt.where(
                or_(
                    Actor.display_name.ilike(needle),
                    Actor.code.ilike(needle),
                    persona_hit,
                    identifier_hit,
                )
            )
        if risk_level:
            stmt = stmt.where(Actor.risk_level == risk_level)
        if category:
            stmt = stmt.where(Actor.category == category)
        if status:
            stmt = stmt.where(Actor.status == status)
        return stmt

    # ---- queries ----------------------------------------------------------
    def list_actors(
        self,
        *,
        query: Optional[str] = None,
        risk_level: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort: str = "risk",
        descending: bool = True,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[ActorRow], int]:
        personas, identifiers = self._count_subqueries()
        order_col = SORTABLE.get(sort, _RISK_ORDER)

        stmt = select(Actor, personas, identifiers).options(
            selectinload(Actor.primary_source)
        )
        stmt = self._apply_filters(
            stmt, query=query, risk_level=risk_level, category=category, status=status
        )
        stmt = stmt.order_by(
            order_col.desc() if descending else order_col.asc(), Actor.display_name.asc()
        ).limit(limit).offset(offset)

        rows = [
            ActorRow(actor=a, persona_count=p or 0, identifier_count=i or 0)
            for a, p, i in self.session.execute(stmt).all()
        ]

        count_stmt = self._apply_filters(
            select(func.count(Actor.id)),
            query=query,
            risk_level=risk_level,
            category=category,
            status=status,
        )
        total = self.session.execute(count_stmt).scalar_one()
        return rows, int(total)

    def get_actor(self, actor_id: str) -> Optional[Actor]:
        """Load one actor with personas and identifiers eagerly attached."""
        stmt = (
            select(Actor)
            .where(or_(Actor.id == actor_id, Actor.code == actor_id))
            .options(
                selectinload(Actor.personas).selectinload(Persona.identifiers),
                selectinload(Actor.identifiers),
            )
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def counts_for(self, actor_id: str) -> tuple[int, int]:
        personas = self.session.execute(
            select(func.count(Persona.id)).where(Persona.actor_id == actor_id)
        ).scalar_one()
        identifiers = self.session.execute(
            select(func.count(Identifier.id)).where(Identifier.actor_id == actor_id)
        ).scalar_one()
        return int(personas), int(identifiers)

    # ---- aggregates -------------------------------------------------------
    def _group_count(self, column: Any) -> dict[str, int]:
        rows = self.session.execute(select(column, func.count()).group_by(column)).all()
        return {str(k): int(v) for k, v in rows}

    def stats(self) -> dict[str, Any]:
        scalar = self.session.execute
        return {
            "total_actors": int(scalar(select(func.count(Actor.id))).scalar_one()),
            "total_personas": int(scalar(select(func.count(Persona.id))).scalar_one()),
            "total_identifiers": int(scalar(select(func.count(Identifier.id))).scalar_one()),
            "total_sources": int(scalar(select(func.count(Source.id))).scalar_one()),
            "by_risk_level": self._group_count(Actor.risk_level),
            "by_category": self._group_count(Actor.category),
            "by_status": self._group_count(Actor.status),
            "identifiers_by_kind": self._group_count(Identifier.kind),
            "last_scan_at": scalar(select(func.max(Actor.last_scan_at))).scalar_one_or_none(),
        }

    def distinct_values(self, column: Any) -> Sequence[str]:
        rows = self.session.execute(select(column).distinct().order_by(column)).scalars().all()
        return [r for r in rows if r]
