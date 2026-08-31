"""Authentication and authorization dependencies.

Provides:
- get_current_user: extracts and validates JWT from Authorization header
- require_role: enforces role-based access control
- CurrentUser: typed dependency for the current authenticated user
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """Authenticated user context extracted from JWT."""
    username: str
    role: str
    user_id: str


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Extract and validate JWT from Authorization header.

    Returns CurrentUser if valid, raises 401 if missing/invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        username=payload.get("sub", ""),
        role=payload.get("role", ""),
        user_id=payload.get("uid", ""),
    )


def require_role(*allowed_roles: str):
    """Dependency factory that enforces role-based access control.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        def admin_endpoint(user: CurrentUser = Depends(get_current_user)): ...
    """
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized for this endpoint. Required: {', '.join(allowed_roles)}",
            )
        return user
    return _check
