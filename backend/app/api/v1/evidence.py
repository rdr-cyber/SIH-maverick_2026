"""Evidence and relationship endpoints.

The evidence API answers the product's core question:
    WHY ARE THESE TWO PERSONAS CONNECTED?

Every relationship carries:
- Confidence score (RCS) and band
- Scoring factors showing exactly how the score was computed
- Evidence items classified as OBSERVED_FACT, DERIVED_SIGNAL, CORRELATION, or ANALYST_HYPOTHESIS
- Human-readable explanation
- Review status (pending/accepted/rejected/uncertain)
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.models.intel import CONFIDENCE_BANDS, EVIDENCE_KINDS, RELATIONSHIP_KINDS, RELATIONSHIP_STATUS
from app.schemas.common import ErrorResponse
from app.schemas.evidence import RelationshipDetail, RelationshipOut
from app.services.evidence import EvidenceService, RelationshipNotFound

router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/relationships",
    response_model=list[RelationshipOut],
    summary="List relationships between actors",
)
def list_relationships(
    session: DbSession,
    kind: Annotated[Optional[str], Query(description=f"One of {RELATIONSHIP_KINDS}")] = None,
    status: Annotated[Optional[str], Query(description=f"One of {RELATIONSHIP_STATUS}")] = None,
    min_confidence: Annotated[Optional[float], Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RelationshipOut]:
    svc = EvidenceService(session)
    return svc.list_relationships(
        kind=kind, status=status, min_confidence=min_confidence,
        limit=limit, offset=offset,
    )


@router.get(
    "/relationships/{code}",
    response_model=RelationshipDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Full relationship with evidence chain — the WHY panel",
)
def get_relationship(
    session: DbSession,
    code: Annotated[str, Path(description="Relationship code, e.g. REL-DM-SV-001")],
) -> RelationshipDetail:
    """Get a relationship with its complete evidence chain.

    This is the endpoint that powers the 'WHY are these connected?' UI.
    It returns:
    - The relationship with confidence, band, and review status
    - All evidence items with their class and score contribution
    - The scoring factors showing exactly how the RCS was computed
    - A human-readable explanation
    """
    svc = EvidenceService(session)
    try:
        return svc.get_relationship_detail(code)
    except RelationshipNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/items",
    response_model=list,
    summary="List all evidence items",
)
def list_evidence_items(
    session: DbSession,
    relationship_id: Annotated[Optional[str], Query()] = None,
    kind: Annotated[Optional[str], Query(description=f"One of {EVIDENCE_KINDS}")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list:
    svc = EvidenceService(session)
    return svc.list_evidence(
        relationship_id=relationship_id, kind=kind,
        limit=limit, offset=offset,
    )
