"""Declarative base, UUID primary keys and timestamp mixins.

Mirrors the conventions of docs/schemas/postgres_schema.sql. For the
embedded SQLite demo, UUIDs are stored as 36-char strings and Postgres
JSONB/arrays are modeled as JSON — the Docker/Postgres deployment keeps
the same column semantics via SQLAlchemy's engine-agnostic layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    """UUID4 as a 36-char string (portable across SQLite and Postgres)."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC timestamp.

    SQLite has no timezone-aware DateTime, so every timestamp in the system is
    stored naive-UTC. Keeping one helper avoids mixed-awareness comparisons.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Single declarative base for every model in the app."""


class IDMixin:
    """String(36) primary key, defaulting to a v4 UUID."""

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id)


class StampMixin:
    """created_at / updated_at housekeeping columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
