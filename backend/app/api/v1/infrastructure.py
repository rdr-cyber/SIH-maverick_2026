"""Infrastructure intelligence API endpoints.

Metadata-oriented: domains, DNS, TLS certificates, hosting, ASN.
Every observation has source and provenance.
No exploitation or unauthorized access.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.services.infrastructure import InfrastructureService

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


@router.get(
    "",
    summary="List infrastructure observations",
)
def list_infrastructure(
    session: DbSession,
    kind: Annotated[Optional[str], Query(description="Filter by kind: domain, onion_service")] = None,
    actor: Annotated[Optional[str], Query(description="Filter by actor code")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """List infrastructure observations with provenance.

    Returns domain and onion_service identifiers with their source
    and actor context.  Every observation traces to exactly one source.
    """
    svc = InfrastructureService(session)
    return svc.list_infrastructure(kind=kind, actor_code=actor, limit=limit, offset=offset)


@router.get(
    "/clusters",
    summary="Find shared infrastructure across actors",
)
def get_clusters(
    session: DbSession,
) -> list[dict]:
    """Find infrastructure shared by multiple actors.

    Shared infrastructure is a key intelligence signal indicating
    potential actor overlap.
    """
    svc = InfrastructureService(session)
    return svc.get_clusters()


@router.get(
    "/actor/{actor_code}",
    summary="Get infrastructure for a specific actor",
)
def get_actor_infrastructure(
    session: DbSession,
    actor_code: str,
) -> dict:
    """Get all infrastructure observations for an actor with provenance."""
    svc = InfrastructureService(session)
    return svc.get_actor_infrastructure(actor_code)
