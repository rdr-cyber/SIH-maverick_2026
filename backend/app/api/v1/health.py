"""Health and readiness endpoint.

Reports which infrastructure adapters this process resolved, so it is obvious
from the API whether the local or production stack is in use.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.config import settings
from app.core.database import engine
from app.models.base import utcnow
from app.models.identity import Actor
from app.schemas.common import AdapterInfo, HealthResponse

log = logging.getLogger(__name__)
router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness and adapter report")
def health(session: DbSession) -> HealthResponse:
    checks: dict[str, str] = {}

    try:
        count = session.execute(select(Actor.id).limit(1)).first()
        checks["database"] = "ok" if count is not None else "ok (empty)"
    except Exception as exc:  # pragma: no cover - surfaced, not swallowed
        log.exception("database health probe failed")
        checks["database"] = f"error: {type(exc).__name__}"

    # Graph adapter
    try:
        from app.core.graph import get_graph_backend
        gb = get_graph_backend()
        checks["graph"] = f"ok ({type(gb).__name__}, nodes={gb.node_count()}, edges={gb.edge_count()})"
    except Exception as exc:
        checks["graph"] = f"error: {type(exc).__name__}: {exc}"

    # Task adapter
    try:
        from app.core.tasks import get_task_backend
        tb = get_task_backend()
        checks["tasks"] = f"ok ({type(tb).__name__}, available={tb.is_available()})"
    except Exception as exc:
        checks["tasks"] = f"error: {type(exc).__name__}: {exc}"

    degraded = any(v.startswith("error") for v in checks.values())
    return HealthResponse(
        status="degraded" if degraded else "ok",
        app=settings.app_name,
        version=settings.app_version,
        time=utcnow(),
        adapters=AdapterInfo(
            app_mode=settings.app_mode,
            database=engine.dialect.name,
            graph_backend=settings.graph_backend or "inprocess",
            task_backend=settings.task_backend or "local",
        ),
        checks=checks,
    )
