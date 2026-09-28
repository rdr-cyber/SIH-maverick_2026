"""TRILOK TRACE application entry point.

Run locally (no Docker, no external services):

    python -m uvicorn app.main:app --reload --port 8000

The app never branches on deployment mode. ``app.core.config`` resolves which
infrastructure adapters to build, and everything above that layer is identical
in local and production deployments.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.logging import configure_logging
from app.services.actors import ActorNotFound

log = logging.getLogger(__name__)

# CSP for the SPA (SECURITY.md §4). style-src allows Tailwind's inline styles;
# connect-src covers the vite dev server origin used by the demo UI.
# img-src also allows the Esri tile host used by the map view's basemap.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data: https://server.arcgisonline.com; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)

DESCRIPTION = """
TRILOK TRACE - Investigative Intelligence Platform (SIH PS 26151, NTRO).

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

    # PostgreSQL deployments own their schema through Alembic (DATABASE.md §14);
    # SQLite demo mode keeps create_all for zero-config startup.
    if engine.dialect.name == "postgresql":
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
        command.upgrade(alembic_cfg, "head")
        log.info("alembic migrations applied (head)")
    else:
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
    _RATE_LIMIT = settings.rate_limit_per_minute  # requests per minute per IP
    _AUTH_RATE_LIMIT = 30  # separate budget for /auth/* — login abuse can't starve data pages
    _auth_rate_limit_store: dict[str, list[float]] = defaultdict(list)
    _STALE_CLEANUP_INTERVAL = 60.0  # seconds between full-store purges
    _last_cleanup: float = time.time()

    @app.middleware("http")
    async def rate_limit_and_headers(request: Request, call_next):
        nonlocal _last_cleanup
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # Periodic full-store purge to prevent unbounded memory growth
        if now - _last_cleanup > _STALE_CLEANUP_INTERVAL:
            _last_cleanup = now
            stale_ips = [
                ip for ip, ts in _rate_limit_store.items()
                if not ts or (now - ts[-1]) > _STALE_CLEANUP_INTERVAL
            ]
            for ip in stale_ips:
                del _rate_limit_store[ip]

        # Rate limiting (skip health checks and docs).  Auth endpoints get a
        # separate, smaller bucket so data-page traffic can never exhaust the
        # login budget (and vice versa) — SECURITY.md §3.
        if request.url.path not in ("/api/v1/health", "/docs", "/openapi.json", "/"):
            is_auth = request.url.path.startswith(f"{settings.api_prefix}/auth/")
            bucket = _auth_rate_limit_store if is_auth else _rate_limit_store
            limit = _AUTH_RATE_LIMIT if is_auth else _RATE_LIMIT
            timestamps = bucket[client_ip]
            # Remove entries older than 60s
            timestamps[:] = [t for t in timestamps if now - t < 60]
            if len(timestamps) >= limit:
                retry_after = int(60 - (now - timestamps[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Rate limit exceeded. Try again later.",
                            "details": {"retry_after": max(retry_after, 1)},
                            "request_id": request_id,
                        }
                    },
                    headers={"Retry-After": str(max(retry_after, 1)), "X-Request-ID": request_id},
                )
            timestamps.append(now)

        # Security headers (SECURITY.md §4)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        if settings.app_mode == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ---- global error mapping (API.md §1.1 envelope) -------------------------
    def _envelope(
        request: Request,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        body: dict[str, Any] = {
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        }
        if details is not None:
            body["error"]["details"] = details
        headers = {"X-Request-ID": request_id}
        if extra_headers:
            headers.update(extra_headers)
        return JSONResponse(status_code=status_code, content=body, headers=headers)

    @app.exception_handler(ActorNotFound)
    def _actor_not_found_handler(request: Request, exc: ActorNotFound) -> JSONResponse:
        # Legacy contract kept for the current frontend/tests: a top-level
        # `code: actor_not_found` alongside the API.md §1.1 envelope.
        request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "code": "actor_not_found",
                "error": {
                    "code": "ACTOR_NOT_FOUND",
                    "message": str(exc),
                    "request_id": request_id,
                },
            },
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(ValueError)
    def _validation_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        # Safe errors: internals stay in the server log (SECURITY.md §7).
        log.info("value error on %s: %s", request.url.path, exc)
        msg = str(exc) if settings.app_mode == "local" else "Invalid input"
        return _envelope(request, status_code=422, code="VALIDATION_ERROR", message=msg)

    @app.exception_handler(StarletteHTTPException)
    def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }
        return _envelope(
            request,
            status_code=exc.status_code,
            code=code_map.get(exc.status_code, "HTTP_ERROR"),
            message=str(exc.detail),
            extra_headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    def _request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(
            request,
            status_code=400,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Safe-error contract: no stack traces leave the process. The trace goes
        # to the server log; the client gets the request_id for correlation.
        request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        log.exception("unhandled error (request_id=%s)", request_id)
        return _envelope(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            details={"request_id": request_id} if settings.app_mode == "local" else None,
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
