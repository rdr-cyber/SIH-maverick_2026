"""SHADOWGRAPH application entry point.

Run locally (no Docker, no external services):

    python -m uvicorn app.main:app --reload --port 8000

The app never branches on deployment mode. ``app.core.config`` resolves which
infrastructure adapters to build, and everything above that layer is identical
in local and production deployments.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.logging import configure_logging
from app.services.actors import ActorNotFound

log = logging.getLogger(__name__)

DESCRIPTION = """
MAVERICKS PROJECT - Investigative Intelligence Platform (SIH PS 26151, NTRO).

All data served by this API is **synthetic**. Relationship scores are decision
heuristics for analysts, never claims about a real person's identity.
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info(
        "starting %s %s (mode=%s, db=%s, graph=%s, tasks=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_mode,
        engine.dialect.name,
        settings.graph_backend,
        settings.task_backend,
    )
    init_db()

    if settings.seed_on_startup:
        from app.data_generation import seed_database

        try:
            seed_database()
        except Exception:  # pragma: no cover - never block startup on demo data
            log.exception("synthetic seed failed; continuing with an empty database")

    yield
    log.info("shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    # ---- rate limiting + security headers ---------------------------------
    _rate_limit_store: dict[str, list[float]] = defaultdict(list)
    _RATE_LIMIT = 120  # requests per minute per IP

    @app.middleware("http")
    async def rate_limit_and_headers(request: Request, call_next):
        # Rate limiting (skip health checks and docs)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        if request.url.path not in ("/api/v1/health", "/docs", "/openapi.json", "/"):
            timestamps = _rate_limit_store[client_ip]
            # Remove entries older than 60s
            timestamps[:] = [t for t in timestamps if now - t < 60]
            if len(timestamps) >= _RATE_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                )
            timestamps.append(now)

        # Security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.app_mode == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ---- global error mapping -----------------------------------------------
    @app.exception_handler(ActorNotFound)
    def _actor_not_found_handler(request: Any, exc: ActorNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "code": "actor_not_found"},
        )

    @app.exception_handler(ValueError)
    def _validation_error_handler(request: Any, exc: ValueError) -> JSONResponse:
        # In production, don't leak internal error details
        msg = str(exc) if settings.app_mode == "local" else "Invalid input"
        return JSONResponse(
            status_code=422,
            content={"detail": msg, "code": "validation_error"},
        )

    @app.get("/", include_in_schema=False)
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "name": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
                "api": settings.api_prefix,
                "notice": "Synthetic data only. Scores are analyst heuristics, not identity proof.",
            }
        )

    return app


app = create_app()
