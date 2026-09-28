"""Async relational-store adapter — SQLAlchemy 2 async foundation.

The application currently serves through the sync engine
(``app.core.database``) under a threadpool, which is correct and sufficient
for the local demo and for uvicorn's worker model. This module provides the
**async twin** of that engine so later phases (SSE streaming, Phase-3
ingestion pipelines, Phase-11 workers) can adopt async I/O without another
schema or model change: the same ``Base.metadata`` and the same models power
both engines.

Usage (future phases):

    from app.core.database_async import async_engine, AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Analyst).where(...))

URL rules mirror ``create_db_engine``: PostgreSQL via ``postgresql+psycopg``
(PSYCOPG 3 has native async support), SQLite via ``sqlite+aiosqlite``.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

log = logging.getLogger(__name__)


def _async_url() -> str:
    """Translate the configured URL to its async driver form."""
    url = settings.database_url or ""
    if url.startswith("postgresql+psycopg://"):
        return url  # psycopg3 already supports async
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    raise ValueError(f"no async driver mapping for database URL: {url!r}")


def create_async_db_engine() -> AsyncEngine:
    target = _async_url()
    kwargs: dict = {"echo": settings.db_echo}
    if target.startswith("sqlite+aiosqlite"):
        # StaticPool not needed: aiosqlite serializes onto one connection thread.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
    return create_async_engine(target, **kwargs)


async_engine: AsyncEngine = create_async_db_engine()
AsyncSessionLocal = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
