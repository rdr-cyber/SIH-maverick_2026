"""Infrastructure business logic.

Metadata-oriented intelligence: domains, DNS, TLS, hosting, ASN.
Every observation has source and provenance.  No exploitation.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.repositories.infrastructure import InfrastructureRepository


class InfrastructureService:
    """Business logic for infrastructure observations."""

    def __init__(self, session: Session) -> None:
        self.repo = InfrastructureRepository(session)

    def list_infrastructure(
        self,
        *,
        kind: Optional[str] = None,
        actor_code: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        items, total = self.repo.list_infrastructure(
            kind=kind, actor_code=actor_code, limit=limit, offset=offset,
        )
        return {"items": items, "total": total}

    def get_clusters(self) -> list[dict[str, Any]]:
        return self.repo.get_infrastructure_clusters()

    def get_actor_infrastructure(self, actor_code: str) -> dict[str, Any]:
        return self.repo.get_actor_infrastructure(actor_code)
