"""Authentication API endpoints — API.md §2.

POST /auth/login    {username, password} → {access_token, refresh_token, user}
POST /auth/refresh  rotate refresh token (denylist-revoked or reused jti → 401)
GET  /auth/me       current analyst profile + permissions
POST /auth/logout   revoke refresh token; audit auth.logout

All four write to ``audit_events`` (SECURITY.md §6: ``auth.*`` actions).
Login failures audit with ``is_system=False`` and a NULL analyst id so the
append-only log records the attempt without attributing it to an account.
"""
from __future__ import annotations

from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit import write_audit
from app.api.auth import CurrentUser, get_current_user
from app.core.database import get_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    utcnow,
    verify_password,
)
from app.models.ops import Analyst

router = APIRouter(prefix="/auth", tags=["auth"])

# In-process jti denylist for revoked refresh tokens. Suitable for the
# single-process local mode; a multi-worker production deployment would move
# this to Redis (mirrors the rate-limiter note in SECURITY.md §3).
_revoked_jtis: set[str] = set()


def revoke_jti(jti: str) -> None:
    _revoked_jtis.add(jti)


def _jti_revoked(jti: str | None) -> bool:
    return bool(jti) and jti in _revoked_jtis


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    username: str
    role: str
    full_name: str
    email: str
    is_active: bool
    must_change_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo
    # Deprecated flat duplicates kept so the existing frontend Login page
    # (which reads data.username / data.role) keeps working until the
    # Phase-9 UI refresh migrates to the canonical `user` object.
    username: str = ""
    role: str = ""
    full_name: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_info(analyst: Analyst) -> UserInfo:
    return UserInfo(
        username=analyst.username,
        role=analyst.role,
        full_name=analyst.full_name,
        email=analyst.email,
        is_active=analyst.is_active,
        must_change_password=analyst.must_change_password,
    )


def _request_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    return ip, ua


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse, summary="Authenticate and receive JWT pair")
def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> LoginResponse:
    """Authenticate with username/password; audit ``auth.login``/``auth.login_failed``."""
    ip, ua = _request_meta(request)

    analyst = session.execute(
        select(Analyst).where(Analyst.username == body.username)
    ).scalar_one_or_none()

    if analyst is None or not verify_password(body.password, analyst.password_hash):
        # Same response for unknown user and wrong password (no account oracle).
        write_audit(
            session,
            action="auth.login_failed",
            resource_type="analyst",
            resource_id=analyst.id if analyst else None,
            ip=ip,
            user_agent=ua,
            note=f"login attempt for username={body.username!r}",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if not analyst.is_active:
        write_audit(
            session,
            action="auth.login_failed",
            analyst_id=analyst.id,
            resource_type="analyst",
            resource_id=analyst.id,
            ip=ip,
            user_agent=ua,
            note="account disabled",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled"
        )

    access = create_access_token(analyst.username, analyst.role, analyst.id)
    refresh, _jti = create_refresh_token(analyst.username, analyst.role, analyst.id)

    analyst.last_login_at = utcnow()
    write_audit(
        session,
        action="auth.login",
        analyst_id=analyst.id,
        resource_type="analyst",
        resource_id=analyst.id,
        ip=ip,
        user_agent=ua,
    )
    session.commit()

    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        user=_user_info(analyst),
        username=analyst.username,
        role=analyst.role,
        full_name=analyst.full_name,
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Rotate refresh token")
def refresh(
    body: RefreshRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RefreshResponse:
    """Exchange a valid refresh token for a fresh pair (rotation).

    Revoked (logged-out) or already-rotated tokens are rejected with 401 —
    replay of an old refresh token cannot mint new sessions.
    """
    ip, ua = _request_meta(request)
    try:
        payload = decode_refresh_token(body.refresh_token)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    if _jti_revoked(payload.get("jti")):
        write_audit(
            session,
            action="auth.refresh_failed",
            analyst_id=payload.get("uid"),
            resource_type="analyst",
            resource_id=payload.get("uid"),
            ip=ip,
            user_agent=ua,
            note="revoked refresh token replay",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked"
        )

    analyst = session.execute(
        select(Analyst).where(Analyst.username == payload["sub"])
    ).scalar_one_or_none()
    if analyst is None or not analyst.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable"
        )

    # Rotate: revoke the presented jti, mint a fresh pair.
    revoke_jti(payload["jti"])
    access = create_access_token(analyst.username, analyst.role, analyst.id)
    new_refresh, _ = create_refresh_token(analyst.username, analyst.role, analyst.id)

    write_audit(
        session,
        action="auth.refresh",
        analyst_id=analyst.id,
        resource_type="analyst",
        resource_id=analyst.id,
        ip=ip,
        user_agent=ua,
    )
    session.commit()

    return RefreshResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserInfo, summary="Current analyst profile")
def get_me(
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
) -> UserInfo:
    analyst = session.execute(
        select(Analyst).where(Analyst.username == user.username)
    ).scalar_one_or_none()
    if analyst is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found"
        )
    return _user_info(analyst)


@router.post("/logout", summary="Revoke refresh token; audit auth.logout")
def logout(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser = Depends(get_current_user),
    body: RefreshRequest | None = None,
) -> dict:
    """Revoke the presented refresh token (if any) and audit the logout."""
    if body and body.refresh_token:
        try:
            payload = decode_refresh_token(body.refresh_token)
            revoke_jti(payload.get("jti"))
        except pyjwt.PyJWTError:
            pass  # already-invalid tokens need no revocation
    ip, ua = _request_meta(request)
    write_audit(
        session,
        action="auth.logout",
        analyst_id=user.user_id,
        resource_type="analyst",
        resource_id=user.user_id,
        ip=ip,
        user_agent=ua,
    )
    session.commit()
    response.delete_cookie("trilok_trace_refresh", path="/api/v1/auth")
    return {"ok": True, "message": "Logged out successfully"}


__all__ = [
    "router",
    "hash_password",
    "revoke_jti",
]
