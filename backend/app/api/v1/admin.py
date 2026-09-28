"""Admin API endpoints — API.md §14 subset + SECURITY.md §2 RBAC.

Admin-only operations for the three-role matrix:
- GET/POST /admin/analysts, PATCH /admin/analysts/{id}
- GET /admin/audit (audit-log browse with filters)

Graph resync and correlation-weight endpoints arrive with their phases
(P5 graph sync, P6 correlation); they are admin-gated there the same way.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit import write_audit
from app.api.auth import ADMIN_ONLY, CurrentUser, get_current_user, require_role
from app.core.database import get_session
from app.core.security import hash_password
from app.models.ops import ANALYST_ROLES, Analyst, AuditEvent

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(*ADMIN_ONLY))],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateAnalystRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role: str = "analyst"


class UpdateAnalystRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None


class AnalystOut(BaseModel):
    id: str
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Analyst management
# ---------------------------------------------------------------------------

def _serialize(a: Analyst) -> AnalystOut:
    return AnalystOut(
        id=a.id,
        username=a.username,
        full_name=a.full_name,
        email=a.email,
        role=a.role,
        is_active=a.is_active,
        must_change_password=a.must_change_password,
        created_at=a.created_at,
    )


@router.get("/analysts", response_model=list[AnalystOut], summary="List analysts")
def list_analysts(session: Annotated[Session, Depends(get_session)]) -> list[AnalystOut]:
    rows = session.execute(select(Analyst).order_by(Analyst.username)).scalars().all()
    return [_serialize(a) for a in rows]


@router.post("/analysts", response_model=AnalystOut, status_code=201, summary="Create analyst")
def create_analyst(
    body: CreateAnalystRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
) -> AnalystOut:
    if body.role not in ANALYST_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"role must be one of {', '.join(ANALYST_ROLES)}",
        )
    existing = session.execute(
        select(Analyst).where(Analyst.username == body.username)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        )

    analyst = Analyst(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
        must_change_password=True,
    )
    session.add(analyst)
    session.flush()

    write_audit(
        session,
        action="admin.analyst_create",
        analyst_id=user.user_id,
        resource_type="analyst",
        resource_id=analyst.id,
        after={"username": analyst.username, "role": analyst.role},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )
    session.commit()
    return _serialize(analyst)


@router.patch("/analysts/{analyst_id}", response_model=AnalystOut, summary="Update analyst")
def update_analyst(
    analyst_id: str,
    body: UpdateAnalystRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
) -> AnalystOut:
    analyst = session.get(Analyst, analyst_id)
    if analyst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyst not found")

    changes: dict[str, Any] = {}
    if body.role is not None:
        if body.role not in ANALYST_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"role must be one of {', '.join(ANALYST_ROLES)}",
            )
        changes["role"] = {"before": analyst.role, "after": body.role}
        analyst.role = body.role
    if body.is_active is not None:
        if analyst.id == user.user_id and body.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account",
            )
        changes["is_active"] = {"before": analyst.is_active, "after": body.is_active}
        analyst.is_active = body.is_active
    if body.full_name is not None:
        changes["full_name"] = {"before": analyst.full_name, "after": body.full_name}
        analyst.full_name = body.full_name
    if body.must_change_password is not None:
        changes["must_change_password"] = {
            "before": analyst.must_change_password,
            "after": body.must_change_password,
        }
        analyst.must_change_password = body.must_change_password

    write_audit(
        session,
        action="admin.analyst_update",
        analyst_id=user.user_id,
        resource_type="analyst",
        resource_id=analyst.id,
        before={k: v["before"] for k, v in changes.items()} or None,
        after={k: v["after"] for k, v in changes.items()} or None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )
    session.commit()
    return _serialize(analyst)


# ---------------------------------------------------------------------------
# Audit browse
# ---------------------------------------------------------------------------

@router.get("/audit", summary="Browse the append-only audit log")
def browse_audit(
    session: Annotated[Session, Depends(get_session)],
    action: str | None = Query(None, description="Exact action, e.g. auth.login"),
    action_prefix: str | None = Query(None, description="Action prefix, e.g. auth."),
    analyst_id: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    from sqlalchemy import func

    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    count_stmt = select(func.count()).select_from(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
        count_stmt = count_stmt.where(AuditEvent.action == action)
    if action_prefix:
        stmt = stmt.where(AuditEvent.action.startswith(action_prefix))
        count_stmt = count_stmt.where(AuditEvent.action.startswith(action_prefix))
    if analyst_id:
        stmt = stmt.where(AuditEvent.analyst_id == analyst_id)
        count_stmt = count_stmt.where(AuditEvent.analyst_id == analyst_id)
    if from_ts:
        stmt = stmt.where(AuditEvent.occurred_at >= from_ts)
        count_stmt = count_stmt.where(AuditEvent.occurred_at >= from_ts)
    if to_ts:
        stmt = stmt.where(AuditEvent.occurred_at <= to_ts)
        count_stmt = count_stmt.where(AuditEvent.occurred_at <= to_ts)

    total = session.execute(count_stmt).scalar() or 0
    rows = session.execute(stmt.offset(offset).limit(limit)).scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "analyst_id": e.analyst_id,
                "is_system": e.is_system,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "before": e.before_json,
                "after": e.after_json,
                "ip": e.ip,
                "user_agent": e.user_agent,
                "note": e.note,
                "occurred_at": e.occurred_at,
            }
            for e in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
