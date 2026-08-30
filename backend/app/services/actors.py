"""Actor business logic.

Services own domain rules and DTO mapping. They depend on repository
abstractions, never on a concrete database, so the production stack swaps in
underneath without changes here.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.actors import ActorRepository, ActorRow
from app.schemas.actor import ActorDetail, ActorStats, ActorSummary
from app.schemas.common import Page


class ActorNotFound(LookupError):
    """Raised when an actor id or code does not resolve. Mapped to HTTP 404."""

    def __init__(self, ref: str) -> None:
        super().__init__(f"No actor matching '{ref}'")
        self.ref = ref


def _to_summary(row: ActorRow) -> ActorSummary:
    return ActorSummary.model_validate(row.actor).model_copy(
        update={
            "persona_count": row.persona_count,
            "identifier_count": row.identifier_count,
        }
    )


class ActorService:
    def __init__(self, session: Session) -> None:
        self.repo = ActorRepository(session)

    def search(
        self,
        *,
        query: Optional[str] = None,
        risk_level: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort: str = "risk",
        descending: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Page[ActorSummary]:
        effective_limit = min(limit or settings.default_page_size, settings.max_page_size)
        rows, total = self.repo.list_actors(
            query=query,
            risk_level=risk_level,
            category=category,
            status=status,
            sort=sort,
            descending=descending,
            limit=effective_limit,
            offset=max(offset, 0),
        )
        return Page[ActorSummary](
            items=[_to_summary(r) for r in rows],
            total=total,
            limit=effective_limit,
            offset=max(offset, 0),
        )

    def get(self, ref: str) -> ActorDetail:
        """Fetch a full actor profile by UUID or by human-readable code."""
        actor = self.repo.get_actor(ref)
        if actor is None:
            raise ActorNotFound(ref)
        persona_count, identifier_count = self.repo.counts_for(actor.id)
        return ActorDetail.model_validate(actor).model_copy(
            update={
                "persona_count": persona_count,
                "identifier_count": identifier_count,
            }
        )

    def stats(self) -> ActorStats:
        return ActorStats.model_validate(self.repo.stats())
