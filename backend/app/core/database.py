"""Relational-store adapter: one SQLAlchemy layer, two engines.

The engine is built from ``settings.database_url``, so SQLite (local) and
PostgreSQL (production) are the *same* code path. Only connection arguments
differ, and they are isolated in :func:`_engine_kwargs`.

Nothing above this module knows which database is in use.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

log = logging.getLogger(__name__)


def _engine_kwargs() -> dict[str, Any]:
    """Connection arguments that differ between SQLite and PostgreSQL."""
    target = settings.database_url or ""
    if target.startswith("sqlite"):
        # check_same_thread=False: FastAPI serves requests from a threadpool.
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        # 'sqlite://', 'sqlite:///' and 'sqlite:///:memory:' are all in-memory
        # variants ('sqlite:///' resolves to a private per-connection temp DB,
        # which silently breaks threading). Share one connection so the API's
        # threadpool and the seeding path see the same schema and data.
        if target in ("sqlite://", "sqlite:///:memory:") or target.rstrip("/") == "sqlite:":
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        return kwargs
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
    }


def create_db_engine(url: str | None = None) -> Engine:
    """Build an engine for ``url`` (defaults to the configured database)."""
    target = url or settings.database_url
    assert target is not None  # guaranteed by Settings validation
    eng = create_engine(target, echo=settings.db_echo, future=True, **_engine_kwargs())

    if target.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return eng


engine: Engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any missing tables. Safe to call repeatedly."""
    from app import models  # noqa: F401  -- registers mappers on Base.metadata

    models.Base.metadata.create_all(engine)
    log.info(
        "database ready (dialect=%s, tables=%d)",
        engine.dialect.name,
        len(models.Base.metadata.tables),
    )


def reset_db() -> None:
    """Drop and recreate every table. Used by tests and ``--reset`` seeding."""
    from app import models  # noqa: F401

    models.Base.metadata.drop_all(engine)
    models.Base.metadata.create_all(engine)
    log.warning("database reset (dialect=%s)", engine.dialect.name)
