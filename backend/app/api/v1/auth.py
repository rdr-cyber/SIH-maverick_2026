"""Authentication API endpoints.

POST /auth/login  - Authenticate and receive JWT
GET  /auth/me     - Get current user info
POST /auth/logout  - Logout (client-side token discard + audit)
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth import CurrentUser, get_current_user
from app.core.database import get_session
from app.core.security import create_access_token, hash_password, utcnow, verify_password
from app.models.ops import Analyst

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    full_name: str


class UserInfo(BaseModel):
    username: str
    role: str
    full_name: str
    email: str
    is_active: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_audit(
    session,
    *,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    note: str | None = None,
    request: Request | None = None,
) -> None:
    """Write an audit event (best-effort, never raises)."""
    from app.models.ops import AuditEvent
    try:
        ip = None
        ua = None
        if request:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent", "")[:200]
        evt = AuditEvent(
            analyst_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            note=note,
            ip=ip,
            user_agent=ua,
            occurred_at=utcnow(),
        )
        session.add(evt)
        session.flush()
    except Exception:
        pass  # audit should never break the request


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse, summary="Authenticate and receive JWT")
def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[object, Depends(get_session)],
) -> LoginResponse:
    """Authenticate with username/password and return a JWT access token."""
    # Find user
    analyst = session.execute(
        select(Analyst).where(Analyst.username == body.username)
    ).scalar_one_or_none()

    if analyst is None:
        _write_audit(session, action="LOGIN_FAILURE", note=f"Unknown user: {body.username}", request=request)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not analyst.is_active:
        _write_audit(
            session, action="LOGIN_FAILURE", user_id=analyst.id,
            note="Account disabled", request=request,
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    if not verify_password(body.password, analyst.password_hash):
        _write_audit(
            session, action="LOGIN_FAILURE", user_id=analyst.id,
            note="Wrong password", request=request,
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Generate token
    token = create_access_token(analyst.username, analyst.role, analyst.id)

    # Update last login
    analyst.last_login_at = utcnow()
    session.flush()

    # Audit
    _write_audit(
        session, action="LOGIN_SUCCESS", user_id=analyst.id,
        resource_type="analyst", resource_id=analyst.id, request=request,
    )
    session.commit()

    return LoginResponse(
        access_token=token,
        username=analyst.username,
        role=analyst.role,
        full_name=analyst.full_name,
    )


@router.get("/me", response_model=UserInfo, summary="Get current user info")
def get_me(
    session: Annotated[object, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
) -> UserInfo:
    """Return the current authenticated user's full profile."""
    analyst = session.execute(
        select(Analyst).where(Analyst.username == user.username)
    ).scalar_one_or_none()
    if analyst is None:
        return UserInfo(
            username=user.username,
            role=user.role,
            full_name=user.username,
            email="",
            is_active=True,
        )
    return UserInfo(
        username=analyst.username,
        role=analyst.role,
        full_name=analyst.full_name,
        email=analyst.email,
        is_active=analyst.is_active,
    )


@router.post("/logout", summary="Logout (audit + client-side token discard)")
def logout(
    request: Request,
    session: Annotated[object, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Logout. The client should discard the token.

    This endpoint creates an audit record of the logout.
    """
    _write_audit(
        session, action="LOGOUT", user_id=user.user_id,
        resource_type="analyst", resource_id=user.user_id, request=request,
    )
    session.commit()
    return {"ok": True, "message": "Logged out successfully"}
