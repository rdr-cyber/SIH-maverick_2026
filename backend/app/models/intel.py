"""Intelligence domain: Relationships, Evidence, Timeline Events.

These are the core entities that power the correlation pipeline and the
evidence graph.  Every relationship carries confidence, scoring factors,
and human-readable explanations — never presented as proven identity.

Column semantics are engine-agnostic: UUIDs are String(36) and JSON payloads
use SQLAlchemy's JSON type (TEXT on SQLite, JSONB on PostgreSQL).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDMixin, StampMixin

# Controlled vocabularies
RELATIONSHIP_KINDS = (
    "POSSIBLY_SAME_AS",
    "USES",
    "ASSOCIATED_WITH",
    "APPEARS_ON",
    "AUTHORED",
    "RESOLVES_TO",
    "HAS_CERTIFICATE",
    "HAS_EVIDENCE",
    "ACTIVE_DURING",
)

RELATIONSHIP_STATUS = ("pending", "accepted", "rejected", "uncertain")

CONFIDENCE_BANDS = ("weak", "low", "moderate", "high", "very_high")

EVIDENCE_KINDS = (
    "pgp_match",
    "wallet_match",
    "handle_match",
    "stylometric_similarity",
    "behavior_similarity",
    "infrastructure_reuse",
    "temporal_proximity",
    "analyst_observation",
)

EVIDENCE_CLASSES = ("OBSERVED_FACT", "DERIVED_SIGNAL", "CORRELATION", "ANALYST_HYPOTHESIS")

EVIDENCE_STRENGTH = ("weak", "moderate", "strong")

TIMELINE_EVENT_KINDS = (
    "appearance",
    "pgp_seen",
    "wallet_associated",
    "activity",
    "migration",
    "disappearance",
    "relationship_added",
    "confidence_changed",
    "alert",
    "analyst_note",
)


class Relationship(Base, IDMixin, StampMixin):
    """An inferred or analyst-created link between two entities.

    The correlation engine writes these with status='pending'; only a
    senior_analyst can accept/reject/uncertain.  Every review writes
    an audit event.
    """

    __tablename__ = "relationships"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

    # Polymorphic references — from_type/to_type name the entity table,
    # from_id/to_id are the UUIDs.  This avoids FK circular references
    # while keeping the graph traversable.
    from_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_type: Mapped[str] = mapped_column(String(40), nullable=False)
    to_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Scoring
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    band: Mapped[str] = mapped_column(String(20), nullable=False, default="weak")
    scoring_factors: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    hypothesis_label: Mapped[Optional[str]] = mapped_column(String(200))

    # Review workflow
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_note: Mapped[Optional[str]] = mapped_column(Text)

    # Source tracking
    source_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    engine_ref: Mapped[Optional[str]] = mapped_column(String(60))

    # Temporal
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_rel_status_confidence", "status", "confidence"),
        Index("ix_rel_from", "from_type", "from_id"),
        Index("ix_rel_to", "to_type", "to_id"),
        Index("ix_rel_kind", "kind"),
    )


class Evidence(Base, IDMixin, StampMixin):
    """A piece of derived, explainable support for an inference.

    Each evidence item traces back to one or more observations and
    contributes a score to a relationship's RCS.
    """

    __tablename__ = "evidence"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    strength: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    evidence_class: Mapped[str] = mapped_column(
        "class", String(30), nullable=False, default="DERIVED_SIGNAL"
    )
    score_contribution: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Links
    source_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    relationship_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("relationships.id", ondelete="SET NULL")
    )

    # Supporting details
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")

    __table_args__ = (
        Index("ix_evidence_relationship", "relationship_id"),
        Index("ix_evidence_kind", "kind"),
    )


class TimelineEvent(Base, IDMixin):
    """A unified chronological event for the Timeline UI.

    Events are denormalized from every timestamped artifact — observations,
    posts, PGP sightings, wallet associations, persona appearances,
    relationship milestones, and analyst actions.
    """

    __tablename__ = "timeline_events"

    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

    actor_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL")
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(40))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    confidence_delta: Mapped[Optional[float]] = mapped_column(Float)

    source_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_timeline_actor", "actor_id", "occurred_at"),
        Index("ix_timeline_occurred", "occurred_at"),
    )



