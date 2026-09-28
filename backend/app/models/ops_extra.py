"""Operations additions — DATABASE.md §7, §9, §10, §11.

Scan jobs, alerts, reports, investigation notes and the graph-sync bookkeeping
table. Phase 2 ships the models +Alembic migration; the engines that populate
them arrive in later phases (P11 autonomy, P12 reports, P5 graph sync).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, IDMixin, JSONBVariant, StampMixin
SCAN_KINDS = ("autonomous", "demo_run", "manual")
SCAN_STATUSES = ("queued", "running", "completed", "failed")
SCAN_TRIGGERS = ("beat", "api", "demo")
ALERT_KINDS = ("new_high_confidence", "new_handle_seen", "persona_migration",
               "new_evidence", "system")
ALERT_SEVERITIES = ("info", "low", "medium", "high")
REPORT_KINDS = ("pdf", "csv", "json")
REPORT_STATUSES = ("queued", "generating", "ready", "failed")
SYNC_STATUSES = ("pending", "synced", "failed")


class ScanJob(Base, IDMixin):
    """One ingestion/scan cycle — DATABASE.md §11."""

    __tablename__ = "scan_jobs"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="autonomous")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sources_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_artifacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_identifiers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_relationships: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_confidence_relationships: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[Any]] = mapped_column(JSONBVariant, nullable=False, default=list)
    batch_id: Mapped[Optional[str]] = mapped_column(GUID())
    trigger: Mapped[str] = mapped_column(String(10), nullable=False, default="beat")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("kind IN ('autonomous', 'demo_run', 'manual')", name="ck_scan_jobs_kind"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')", name="ck_scan_jobs_status"
        ),
        CheckConstraint("trigger IN ('beat', 'api', 'demo')", name="ck_scan_jobs_trigger"),
        Index("idx_scan_jobs_status", "status", "created_at"),
    )


class Alert(Base, IDMixin):
    """Analyst-facing alert feed — DATABASE.md §11."""

    __tablename__ = "alerts"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("actors.id"))
    relationship_id: Mapped[Optional[str]] = mapped_column(ForeignKey("relationships.id"))
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"))
    acknowledged_by: Mapped[Optional[str]] = mapped_column(GUID())
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('new_high_confidence', 'new_handle_seen', 'persona_migration',"
            " 'new_evidence', 'system')",
            name="ck_alerts_kind",
        ),
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high')", name="ck_alerts_severity"
        ),
        Index("idx_alerts_created", "created_at"),
    )


class Report(Base, IDMixin):
    """Generated report metadata — DATABASE.md §11."""

    __tablename__ = "reports"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    storage_key: Mapped[Optional[str]] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONBVariant, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(ForeignKey("analysts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    investigation = relationship("Investigation", lazy="joined")

    __table_args__ = (
        CheckConstraint("kind IN ('pdf', 'csv', 'json')", name="ck_reports_kind"),
        CheckConstraint(
            "status IN ('queued', 'generating', 'ready', 'failed')", name="ck_reports_status"
        ),
    )


class InvestigationNote(Base, IDMixin, StampMixin):
    """Analyst notes on an investigation — DATABASE.md §9."""

    __tablename__ = "investigation_notes"

    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    analyst_id: Mapped[str] = mapped_column(ForeignKey("analysts.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="team")

    analyst = relationship("Analyst", lazy="joined")

    __table_args__ = (
        CheckConstraint("visibility IN ('team', 'private')", name="ck_investigation_notes_visibility"),
        Index("idx_notes_investigation", "investigation_id"),
    )


class GraphSyncState(Base):
    """Postgres→Neo4j sync bookkeeping — DATABASE.md §10.

    Composite PK (entity_type, entity_id) per the canonical DDL; no UUID PK.
    """

    __tablename__ = "graph_sync_state"

    entity_type: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sync_status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('pending', 'synced', 'failed')", name="ck_graph_sync_state_status"
        ),
    )
