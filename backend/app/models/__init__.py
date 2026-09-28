"""ORM models. Importing this package registers every table on Base.metadata.

Prototype domain (identity.py): Source, Actor, Persona, Identifier
Canonical additions (canonical.py): Handle, Alias, PGPKey, Wallet, Domain,
    Infrastructure, CertificateMetadata, Marketplace, Forum, Post, Observation,
    RelationshipObservation, BehaviorProfile, StylometricProfile
Intel domain (intel.py): Relationship, Evidence, TimelineEvent
Ops domain (ops.py): Analyst, Investigation, AuditEvent
Ops additions (ops_extra.py): ScanJob, Alert, Report, InvestigationNote,
    GraphSyncState
"""
from .base import (
    Base,
    CITEXT,
    GUID,
    IDMixin,
    JSONBVariant,
    StampMixin,
    new_id,
    utcnow,
)
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
from .canonical import (
    ACCESS_METHODS,
    DOMAIN_STATUSES,
    HANDLE_CATEGORIES,
    INFRA_KINDS,
    OBSERVATION_KINDS,
    PLATFORM_STATUSES,
    PLATFORM_TYPES,
    WALLET_CHAINS,
    Alias,
    BehaviorProfile,
    CertificateMetadata,
    Domain,
    Forum,
    Handle,
    Infrastructure,
    Marketplace,
    Observation,
    PGPKey,
    Post,
    RelationshipObservation,
    StylometricProfile,
    Wallet,
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
from .ops_extra import (
    ALERT_KINDS,
    ALERT_SEVERITIES,
    REPORT_KINDS,
    REPORT_STATUSES,
    SCAN_KINDS,
    SCAN_STATUSES,
    SCAN_TRIGGERS,
    SYNC_STATUSES,
    Alert,
    GraphSyncState,
    InvestigationNote,
    Report,
    ScanJob,
)

__all__ = [
    # base
    "Base", "GUID", "JSONBVariant", "CITEXT", "IDMixin", "StampMixin",
    "new_id", "utcnow",
    # identity (prototype)
    "Source", "Actor", "Persona", "Identifier",
    "SOURCE_KINDS", "ACTOR_STATUSES", "ACTOR_CATEGORIES",
    "RISK_LEVELS", "PERSONA_STATUSES", "IDENTIFIER_KINDS",
    # canonical additions
    "Handle", "Alias", "PGPKey", "Wallet",
    "Domain", "Infrastructure", "CertificateMetadata",
    "Marketplace", "Forum", "Post",
    "Observation", "RelationshipObservation",
    "BehaviorProfile", "StylometricProfile",
    "ACCESS_METHODS", "HANDLE_CATEGORIES", "WALLET_CHAINS", "INFRA_KINDS",
    "DOMAIN_STATUSES", "PLATFORM_STATUSES", "PLATFORM_TYPES",
    "OBSERVATION_KINDS",
    # intel
    "Relationship", "Evidence", "TimelineEvent",
    "RELATIONSHIP_KINDS", "RELATIONSHIP_STATUS", "CONFIDENCE_BANDS",
    "EVIDENCE_KINDS", "EVIDENCE_CLASSES", "EVIDENCE_STRENGTH",
    "TIMELINE_EVENT_KINDS",
    # ops
    "Analyst", "Investigation", "AuditEvent",
    "ANALYST_ROLES", "INVESTIGATION_STATUS",
    # ops additions
    "ScanJob", "Alert", "Report", "InvestigationNote", "GraphSyncState",
    "SCAN_KINDS", "SCAN_STATUSES", "SCAN_TRIGGERS",
    "ALERT_KINDS", "ALERT_SEVERITIES",
    "REPORT_KINDS", "REPORT_STATUSES", "SYNC_STATUSES",
]
