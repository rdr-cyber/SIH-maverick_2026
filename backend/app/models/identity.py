"""Identity domain: Source -> Actor -> Persona -> Identifier.

This is the Milestone 1 subset of ``docs/schemas/postgres_schema.sql``. It is
normalized so Phase 2 can add the remaining entities (marketplaces, forums,
posts, observations, relationships, evidence) without reshaping these tables.

Vocabulary
    Actor      the attributed entity an investigation targets
    Persona    one identity of that actor as seen on ONE platform
    Identifier a handle / alias / PGP fingerprint / wallet / onion address
               observed for a persona

Column semantics are engine-agnostic: UUIDs are String(36) and JSON payloads
use SQLAlchemy's JSON type, which maps to TEXT on SQLite and JSONB on
PostgreSQL. The same models therefore serve both deployment modes.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDMixin, StampMixin

# Controlled vocabularies. Kept as tuples so schemas and the seed agree.
SOURCE_KINDS = ("marketplace", "forum", "paste_site", "certificate_archive",
                "dns_archive", "blockchain_indexer", "test_harness")
ACTOR_STATUSES = ("tracked", "dormant", "archived", "merged")
RISK_LEVELS = ("low", "moderate", "high", "critical")
ACTOR_CATEGORIES = ("narcotics", "weapons", "stolen_data", "hacking_services",
                    "money_laundering", "terror_financing", "fraud", "other")
PERSONA_STATUSES = ("active", "inactive", "abandoned", "rebranded")
IDENTIFIER_KINDS = ("handle", "alias", "pgp_key", "wallet", "email",
                    "jabber", "onion_service", "domain")


class Source(Base, IDMixin, StampMixin):
    """Provenance root. Every artifact traces back to exactly one source."""

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    access_method: Mapped[str] = mapped_column(String(40), nullable=False, default="synthetic")
    reliability: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Actor(Base, IDMixin, StampMixin):
    """A threat actor: the attribution target that personas roll up into."""

    __tablename__ = "actors"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="tracked")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="other")

    # 0-100 heuristic. NOT a probability that two personas are one human.
    attribution_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    primary_source_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    primary_source: Mapped[Optional["Source"]] = relationship(lazy="joined")
    personas: Mapped[list["Persona"]] = relationship(
        back_populates="actor",
        cascade="all, delete-orphan",
        order_by="Persona.first_seen",
    )
    identifiers: Mapped[list["Identifier"]] = relationship(
        back_populates="actor",
        cascade="all, delete-orphan",
        order_by="Identifier.kind",
    )

    __table_args__ = (
        Index("ix_actors_risk_category", "risk_level", "category"),
        Index("ix_actors_last_scan", "last_scan_at"),
    )


class Persona(Base, IDMixin, StampMixin):
    """One platform-scoped identity belonging to an actor."""

    __tablename__ = "personas"

    actor_id: Mapped[str] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(120), nullable=False)
    platform_type: Mapped[str] = mapped_column(String(40), nullable=False, default="marketplace")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    reputation: Mapped[Optional[str]] = mapped_column(String(40))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)

    actor: Mapped["Actor"] = relationship(back_populates="personas")
    source: Mapped["Source"] = relationship(lazy="joined")
    identifiers: Mapped[list["Identifier"]] = relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("normalized_name", "platform", name="uq_persona_name_platform"),
        Index("ix_personas_actor", "actor_id"),
    )


class Identifier(Base, IDMixin, StampMixin):
    """A concrete identifying artifact observed for a persona.

    ``actor_id`` is denormalized from the persona so actor-scoped queries do
    not need a join; the pair is kept consistent by the repository layer.
    """

    __tablename__ = "identifiers"

    actor_id: Mapped[str] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False
    )
    persona_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE")
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(400), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(400), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(160))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)

    actor: Mapped["Actor"] = relationship(back_populates="identifiers")
    persona: Mapped[Optional["Persona"]] = relationship(back_populates="identifiers")
    source: Mapped["Source"] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("persona_id", "kind", "normalized_value", name="uq_identifier_scope"),
        # Shared values across personas are the correlation signal, so this is
        # an index rather than a unique constraint.
        Index("ix_identifiers_kind_value", "kind", "normalized_value"),
        Index("ix_identifiers_actor", "actor_id"),
    )
