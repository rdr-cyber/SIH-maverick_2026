"""Actor endpoints: list/search, detail, and Command Center statistics."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.auth import get_current_user
from app.api.deps import ActorServiceDep, LimitQuery, OffsetQuery
from app.models.identity import ACTOR_CATEGORIES, ACTOR_STATUSES, RISK_LEVELS
from app.schemas.actor import ActorDetail, ActorStats, ActorSummary
from app.schemas.common import ErrorResponse, Page
from app.services.actors import ActorNotFound

router = APIRouter(
    prefix="/actors",
    tags=["actors"],
    dependencies=[Depends(get_current_user)],
)

SortField = Literal["risk", "confidence", "display_name", "last_seen", "last_scan_at"]


@router.get(
    "",
    response_model=Page[ActorSummary],
    summary="List and search actors",
)
def list_actors(
    service: ActorServiceDep,
    q: Annotated[
        Optional[str],
        Query(
            min_length=1,
            max_length=200,
            description="Free-text match on actor name/code, persona names and identifier values",
        ),
    ] = None,
    risk_level: Annotated[Optional[str], Query(description=f"One of {RISK_LEVELS}")] = None,
    category: Annotated[Optional[str], Query(description=f"One of {ACTOR_CATEGORIES}")] = None,
    actor_status: Annotated[
        Optional[str], Query(alias="status", description=f"One of {ACTOR_STATUSES}")
    ] = None,
    sort: SortField = "risk",
    order: Literal["asc", "desc"] = "desc",
    limit: LimitQuery = 25,
    offset: OffsetQuery = 0,
) -> Page[ActorSummary]:
    return service.search(
        query=q,
        risk_level=risk_level,
        category=category,
        status=actor_status,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stats",
    response_model=ActorStats,
    summary="Aggregate counts for the Command Center",
)
def actor_stats(service: ActorServiceDep) -> ActorStats:
    return service.stats()


@router.get(
    "/{actor_ref}",
    response_model=ActorDetail,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    summary="Full actor profile by id or code",
)
def get_actor(
    service: ActorServiceDep,
    actor_ref: Annotated[
        str, Path(description="Actor UUID or human-readable code, e.g. 'darkmerchant'")
    ],
) -> ActorDetail:
    # ActorNotFound is mapped to 404 by the global exception handler in main.py
    return service.get(actor_ref)
