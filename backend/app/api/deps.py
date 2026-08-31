"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.config import settings
from app.services.actors import ActorService
from app.api.auth import CurrentUser, get_current_user, require_role  # re-export

DbSession = Annotated[Session, Depends(get_session)]


def get_actor_service(session: DbSession) -> ActorService:
    return ActorService(session)


ActorServiceDep = Annotated[ActorService, Depends(get_actor_service)]

LimitQuery = Annotated[
    int,
    Query(ge=1, le=settings.max_page_size, description="Maximum rows to return"),
]
OffsetQuery = Annotated[int, Query(ge=0, description="Rows to skip")]
