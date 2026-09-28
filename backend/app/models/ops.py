"""Operations domain: Analysts, Investigations, Audit Events.

Analysts are the human users of the system.  Investigations are
analyst-curated workspaces targeting specific actors.  Audit Events
are an append-only log of every mutation that matters.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CITEXT, GUID, IDMixin, JSONBVariant, StampMixin

# Controlled vocabularies
ANALYST_ROLES = ("analyst", "senior_analyst", "admin")
INVESTIGATION_STATUS = ("draft", "active", "paused", "closed")


class Analyst(Base, IDMixin, StampMixin):
    """A system user (analyst, senior analyst, or admin)."""

    __tablename__ = "analysts"

    username: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # CITEXT per DATABASE.md §1 (case-insensitive unique emails).
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Investigation(Base, IDMixin, StampMixin):
    """An analyst-curated investigation targeting one or more actors.

    Investigations group relationships, evidence, and analyst notes
    into a coherent workspace with configurable correlation parameters.
    """

    __tablename__ = "investigations"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    lead_analyst_id: Mapped[str] = mapped_column(
        ForeignKey("analysts.id", ondelete="RESTRICT"), nullable=False
    )
    # UUID[] in the DDL; JSON array keeps SQLite parity (flagged drift).
    participants: Mapped[dict[str, Any]] = mapped_column(
        JSONBVariant, nullable=False, default=list
    )
    targets: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=list)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    lead_analyst: Mapped["Analyst"] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_investigations_status", "status"),
    )


class AuditEvent(Base):
    """Append-only audit log.  Every mutation that matters writes here.

    By convention, no application code UPDATEs or DELETEs rows in this
    table.  The BIGSERIAL PK mirrors PostgreSQL's convention; for
    SQLite we use Integer which auto-increments.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    analyst_id: Mapped[Optional[str]] = mapped_column(GUID())
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(40))
    resource_id: Mapped[Optional[str]] = mapped_column(GUID())

    before_json: Mapped[Optional[dict[str, Any]]] = mapped_column("before", JSON)
    after_json: Mapped[Optional[dict[str, Any]]] = mapped_column("after", JSON)

    ip: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(200))
    note: Mapped[Optional[str]] = mapped_column(Text)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_audit_occurred", "occurred_at"),
        Index("ix_audit_analyst", "analyst_id"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
