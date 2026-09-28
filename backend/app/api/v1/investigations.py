"""Investigation workspace API endpoints.

The analyst workflow:
  Create → Activate → Explore → Review → Decide → Close

Decisions are NEVER automatic. The correlation engine proposes,
the analyst disposes.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Body, HTTPException, Query
from pydantic import BaseModel

from app.api.auth import get_current_user, require_role
from app.api.deps import DbSession, CurrentUser
from app.services.investigations import InvestigationService

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/investigations", tags=["investigations"])


# ------------------------------------------------------------------
# Request schemas
# ------------------------------------------------------------------

class CreateInvestigationRequest(BaseModel):
    title: str
    description: str
    lead_analyst: str
    targets: list[str] = []
    parameters: dict[str, Any] = {}


class AddNoteRequest(BaseModel):
    analyst: str
    note: str


class DecideRelationshipRequest(BaseModel):
    relationship_id: str
    decision: str  # accepted | rejected | uncertain
    analyst: str
    review_note: str | None = None


# ------------------------------------------------------------------
# CRUD endpoints
# ------------------------------------------------------------------

@router.get("", summary="List all investigations")
def list_investigations(
    session: DbSession,
    status: str | None = Query(None, description="Filter by status"),
) -> list[dict]:
    svc = InvestigationService(session)
    return svc.list_investigations(status=status)


@router.get("/{code}", summary="Get investigation detail with relationships")
def get_investigation(session: DbSession, code: str) -> dict:
    svc = InvestigationService(session)
    result = svc.get_investigation(code)
    if not result:
        return {"error": "not_found", "code": code}
    return result


@router.post("", status_code=201, summary="Create a new investigation",
             dependencies=[Depends(require_role("analyst", "senior_analyst", "admin"))])
def create_investigation(
    session: DbSession,
    body: CreateInvestigationRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    svc = InvestigationService(session)
    try:
        return svc.create_investigation(
            title=body.title,
            description=body.description,
            lead_analyst=body.lead_analyst,
            targets=body.targets,
            parameters=body.parameters,
        )
    except ValueError as e:
        return {"error": str(e)}


# ------------------------------------------------------------------
# Status transitions
# ------------------------------------------------------------------

@router.post("/{code}/activate", summary="Activate investigation",
             dependencies=[Depends(require_role("admin", "senior_analyst"))])
def activate(session: DbSession, code: str, analyst: str = Query(...),
             user: CurrentUser = Depends(get_current_user)) -> dict:
    svc = InvestigationService(session)
    try:
        return svc.activate(code, analyst)
    except ValueError as e:
        return {"error": str(e)}


@router.post("/{code}/pause", summary="Pause investigation",
             dependencies=[Depends(require_role("admin", "senior_analyst"))])
def pause(session: DbSession, code: str, analyst: str = Query(...),
          user: CurrentUser = Depends(get_current_user)) -> dict:
    svc = InvestigationService(session)
    try:
        return svc.pause(code, analyst)
    except ValueError as e:
        return {"error": str(e)}


@router.post("/{code}/close", summary="Close investigation",
             dependencies=[Depends(require_role("admin", "senior_analyst"))])
def close(session: DbSession, code: str, analyst: str = Query(...),
          user: CurrentUser = Depends(get_current_user)) -> dict:
    svc = InvestigationService(session)
    try:
        return svc.close_investigation(code, analyst)
    except ValueError as e:
        return {"error": str(e)}


# ------------------------------------------------------------------
# Notes
# ------------------------------------------------------------------

@router.post("/{code}/notes", summary="Add analyst note to investigation")
def add_note(session: DbSession, code: str, body: AddNoteRequest) -> dict:
    svc = InvestigationService(session)
    try:
        return svc.add_note(code, body.analyst, body.note)
    except ValueError as e:
        return {"error": str(e)}


# ------------------------------------------------------------------
# Relationship decisions
# ------------------------------------------------------------------

@router.post("/decide", summary="Senior analyst decides on a relationship",
             dependencies=[Depends(require_role("admin", "senior_analyst"))])
def decide(session: DbSession, body: DecideRelationshipRequest,
           user: CurrentUser = Depends(get_current_user)) -> dict:
    """Review a relationship (accept/reject/uncertain).

    RBAC (SECURITY.md §2): senior_analyst and admin only — analysts may not
    decide correlation hypotheses.
    """
    svc = InvestigationService(session)
    try:
        result = svc.decide_relationship(
            relationship_id=body.relationship_id,
            decision=body.decision,
            analyst=body.analyst,
            review_note=body.review_note,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Audit log
# ------------------------------------------------------------------

@router.get("/audit/log", summary="Audit trail")
def audit_log(
    session: DbSession,
    resource_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    svc = InvestigationService(session)
    return svc.get_audit(resource_type=resource_type, limit=limit)
