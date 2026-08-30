"""ORM models. Importing this package registers every table on Base.metadata.

Identity domain: Source, Actor, Persona, Identifier
Intel domain: Relationship, Evidence, TimelineEvent
Ops domain: Analyst, Investigation, AuditEvent
"""
from .base import Base, IDMixin, StampMixin, new_id, utcnow
from .identity import (
    ACTOR_CATEGORIES,
    ACTOR_STATUSES,
    IDENTIFIER_KINDS,
    PERSONA_STATUSES,
    RISK_LEVELS,
    SOURCE_KINDS,
    Actor,
    Identifier,
    Persona,
    Source,
)
from .intel import (
    CONFIDENCE_BANDS,
    EVIDENCE_CLASSES,
    EVIDENCE_KINDS,
    EVIDENCE_STRENGTH,
    RELATIONSHIP_KINDS,
    RELATIONSHIP_STATUS,
    TIMELINE_EVENT_KINDS,
    Evidence,
    Relationship,
    TimelineEvent,
)
from .ops import (
    ANALYST_ROLES,
    INVESTIGATION_STATUS,
    Analyst,
    AuditEvent,
    Investigation,
)

__all__ = [
    # base
    "Base", "IDMixin", "StampMixin", "new_id", "utcnow",
    # identity
    "Source", "Actor", "Persona", "Identifier",
    "SOURCE_KINDS", "ACTOR_STATUSES", "ACTOR_CATEGORIES",
    "RISK_LEVELS", "PERSONA_STATUSES", "IDENTIFIER_KINDS",
    # intel
    "Relationship", "Evidence", "TimelineEvent",
    "RELATIONSHIP_KINDS", "RELATIONSHIP_STATUS", "CONFIDENCE_BANDS",
    "EVIDENCE_KINDS", "EVIDENCE_CLASSES", "EVIDENCE_STRENGTH",
    "TIMELINE_EVENT_KINDS",
    # ops
    "Analyst", "Investigation", "AuditEvent",
    "ANALYST_ROLES", "INVESTIGATION_STATUS",
]
