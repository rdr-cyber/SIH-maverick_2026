"""Declarative base, UUID primary keys and timestamp mixins.

Mirrors the conventions of docs/schemas/postgres_schema.sql.

Two deployment targets, one model layer:

* **PostgreSQL (APP_MODE=production)** — the canonical deployment. ``GUID`` maps
  to ``UUID``, ``JSONB`` to ``JSONB``, ``CITEXT`` to ``citext`` (per
  DATABASE.md §1: emails use CITEXT), and Alembic owns the schema
  (``alembic upgrade head`` runs on container boot).
* **SQLite (APP_MODE=local demo)** — the embedded demo. ``GUID`` maps to
  ``CHAR(36)``, ``JSONB`` to JSON, ``CITEXT`` to VARCHAR. Business code cannot
  tell the difference.

The demo keeps naive-UTC datetimes so SQLite round-trips them losslessly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CHAR, DateTime, TypeDecorator, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON, String, Text, TypeEngine
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


class GUID(TypeDecorator):
    """Portable UUID/GUID primary-key type.

    UUID on PostgreSQL (the canonical system of record per DATABASE.md §1),
    CHAR(36) everywhere else. Values are normalised to str so both dialects
    accept the app-generated ids.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect) -> TypeEngine:  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PGUUID

            return dialect.type_descriptor(PGUUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return str(value)


class JSONBVariant(TypeDecorator):
    """JSONB on PostgreSQL, JSON elsewhere (TEXT on SQLite)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect) -> TypeEngine:  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class CITEXT(TypeDecorator):
    """Case-insensitive text (DATABASE.md §1: emails use CITEXT).

    citext on PostgreSQL with a citext extension; case-folded VARCHAR elsewhere.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect) -> TypeEngine:  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import CITEXT as PGCITEXT

            return dialect.type_descriptor(PGCITEXT())
        return dialect.type_descriptor(String(255))

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return value.casefold()


class IDMixin:
    """UUID primary key, defaulting to a v4 UUID (app-generated per DATABASE.md §1)."""

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_id)


class StampMixin:
    """created_at / updated_at housekeeping columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SeenMixin:
    """first_seen / last_seen — provenance window shared by intelligence artifacts."""

    first_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
