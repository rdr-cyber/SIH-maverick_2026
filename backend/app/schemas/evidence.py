"""Evidence and relationship response contracts.

These wire-format models answer the product's core question:
    WHY ARE THESE TWO PERSONAS CONNECTED?

Every response carries evidence items with their class
(OBSERVED_FACT, DERIVED_SIGNAL, CORRELATION, ANALYST_HYPOTHESIS)
and score contributions showing exactly how the RCS was computed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


class ScoringFactor(BaseModel):
    """One signal's contribution to the Relationship Confidence Score."""

    signal: str
    weight: int
    score: float
    note: str


class RelationshipOut(BaseModel):
    """Summary view of a relationship."""

    model_config = ORM

    id: str
    code: str
    kind: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    from_name: str = ""
    to_name: str = ""
    confidence: float = Field(ge=0, le=100)
    band: str
    status: str
    explanation: Optional[str] = None
    hypothesis_label: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    engine_ref: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    scoring_factors: list[ScoringFactor] = Field(default_factory=list)


class EvidenceOut(BaseModel):
    """One piece of supporting evidence."""

    model_config = ORM

    id: str
    code: str
    kind: str
    title: str
    description: str
    strength: str
    evidence_class: str
    score_contribution: float
    details: dict[str, Any] = Field(default_factory=dict)
    status: str


class RelationshipDetail(RelationshipOut):
    """Full relationship view with evidence chain — the WHY panel."""

    evidence: list[EvidenceOut] = Field(default_factory=list)
    total_evidence_score: float = 0.0
