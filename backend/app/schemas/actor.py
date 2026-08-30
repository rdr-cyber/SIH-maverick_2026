"""Actor / Persona / Identifier response contracts.

These are the wire format. The frontend's ``src/api/types.ts`` mirrors them,
so any change here must be reflected there.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


class SourceOut(BaseModel):
    model_config = ORM

    id: str
    name: str
    kind: str
    access_method: str
    reliability: int = Field(ge=0, le=100)
    last_scanned_at: Optional[datetime] = None


class IdentifierOut(BaseModel):
    model_config = ORM

    id: str
    kind: str
    value: str
    label: Optional[str] = None
    persona_id: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source: Optional[SourceOut] = None


class PersonaOut(BaseModel):
    model_config = ORM

    id: str
    name: str
    platform: str
    platform_type: str
    status: str
    is_primary: bool
    reputation: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source: Optional[SourceOut] = None
    identifiers: list[IdentifierOut] = Field(default_factory=list)


class ActorSummary(BaseModel):
    """Row shape for the actor list / search table."""

    model_config = ORM

    id: str
    code: str
    display_name: str
    status: str
    risk_level: str
    category: str
    attribution_confidence: float = Field(ge=0, le=100)
    persona_count: int = 0
    identifier_count: int = 0
    primary_source: Optional[SourceOut] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_scan_at: Optional[datetime] = None


class ActorDetail(ActorSummary):
    """Full profile: everything the Actor Profile screen renders."""

    summary: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    personas: list[PersonaOut] = Field(default_factory=list)
    identifiers: list[IdentifierOut] = Field(default_factory=list)


class ActorStats(BaseModel):
    """Command Center aggregates."""

    total_actors: int
    total_personas: int
    total_identifiers: int
    total_sources: int
    by_risk_level: dict[str, int]
    by_category: dict[str, int]
    by_status: dict[str, int]
    identifiers_by_kind: dict[str, int]
    last_scan_at: Optional[datetime] = None
