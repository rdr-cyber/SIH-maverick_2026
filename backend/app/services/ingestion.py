"""Data Ingestion Pipeline.

Pipeline: SOURCE → OBSERVATION → NORMALIZATION → EXTRACTION → RESOLUTION → RELATIONSHIP → CORRELATION → CONFIDENCE

Every extracted intelligence item carries full provenance:
  Source → Raw observation → Normalized observation → Extracted entity → Resolved entity → Relationship → Confidence signal

Running the same fixture twice does NOT create duplicate intelligence (idempotency via deterministic IDs).

All extraction is RULE_BASED — deterministic, interpretable, no AI claims.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tasks import get_task_backend
from app.models.identity import Actor, Identifier, Persona, Source
from app.models.intel import Evidence, Relationship, TimelineEvent
from app.models.ops import AuditEvent
from app.services.normalization import normalize_identifier
from app.services.confidence import ConfidenceEngine

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ingestion observation model
# ---------------------------------------------------------------------------

@dataclass
class RawObservation:
    """A single raw intelligence observation from a source.

    This is the normalized ingestion object — all source-specific formats
    are converted to this shape before entering the pipeline.
    """
    source_name: str
    source_type: str  # marketplace, forum, paste_site, etc.
    content_type: str  # listing, post, profile, paste
    external_id: str  # unique within the source
    retrieved_at: str  # ISO datetime when retrieved
    published_at: str | None  # when the content was published
    content: str  # raw text content
    metadata: dict[str, Any] = field(default_factory=dict)

    # Extracted identifiers from content
    identifiers: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"kind": "handle|pgp_key|wallet|jabber|onion_service|domain",
    #         "value": "...", "label": "optional description"}


@dataclass
class ExtractedEntity:
    """A normalized entity extracted from an observation."""
    kind: str  # handle, pgp_key, wallet, jabber, onion_service, domain
    original_value: str
    normalized_value: str
    label: str | None
    extraction_method: str  # "rule_based", "field_extract", "content_scan"
    confidence: float  # 0.0-1.0


@dataclass
class ResolvedEntity:
    """An extracted entity that has been resolved to an existing actor."""
    entity: ExtractedEntity
    actor_code: str | None
    actor_id: str | None
    resolution_method: str  # "exact_normalized_match", "strong_match", "unresolved"
    resolution_confidence: float
    persona_id: str | None = None
    source_id: str | None = None


@dataclass
class IngestionResult:
    """Result of ingesting a batch of observations."""
    task_id: str
    source: str
    status: str  # "queued", "running", "completed", "failed"
    started_at: str | None = None
    completed_at: str | None = None
    observations_processed: int = 0
    entities_extracted: int = 0
    entities_resolved: int = 0
    relationships_created: int = 0
    timeline_events_created: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entity extraction (rule-based, deterministic)
# ---------------------------------------------------------------------------

# Regex patterns for entity extraction from content
_PGP_PATTERN = re.compile(
    r'(?:PGP|GPG|fingerprint)[:\s]*(?:0x)?([0-9A-Fa-f]{40})',
    re.IGNORECASE,
)
_WALLET_BTC_PATTERN = re.compile(
    r'\b([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-HJ-NP-Z0-9]{25,90})\b'
)
_WALLET_ETH_PATTERN = re.compile(r'\b(0x[0-9a-fA-F]{40})\b')
_JABBER_PATTERN = re.compile(
    r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:xmpp|jabber|invalid))\b',
    re.IGNORECASE,
)
_ONION_PATTERN = re.compile(r'\b([a-z2-7]{16,56}\.onion)\b')
_DOMAIN_PATTERN = re.compile(
    r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:invalid|test|onion))\b'
)


def extract_entities_from_content(content: str) -> list[ExtractedEntity]:
    """Extract entities from raw text content using rule-based methods.

    Returns ExtractedEntity objects with full provenance metadata.
    All extraction is deterministic and explainable.
    """
    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, value: str, method: str, confidence: float, label: str | None = None) -> None:
        normalized = normalize_identifier(kind, value)
        key = (kind, normalized)
        if key in seen:
            return
        seen.add(key)
        entities.append(ExtractedEntity(
            kind=kind,
            original_value=value,
            normalized_value=normalized,
            label=label,
            extraction_method=method,
            confidence=confidence,
        ))

    # PGP fingerprints
    for m in _PGP_PATTERN.finditer(content):
        _add("pgp_key", m.group(1).upper(), "content_scan", 0.9, "PGP fingerprint from content")

    # Bitcoin wallets
    for m in _WALLET_BTC_PATTERN.finditer(content):
        _add("wallet", m.group(1), "content_scan", 0.85, "BTC address from content")

    # Ethereum wallets
    for m in _WALLET_ETH_PATTERN.finditer(content):
        _add("wallet", m.group(1), "content_scan", 0.85, "ETH address from content")

    # Jabber/XMPP
    for m in _JABBER_PATTERN.finditer(content):
        _add("jabber", m.group(1), "content_scan", 0.8, "XMPP contact from content")

    # Onion services
    for m in _ONION_PATTERN.finditer(content):
        _add("onion_service", m.group(1), "content_scan", 0.8, "Onion service from content")

    # Domains (only .invalid/.test to avoid false positives on real domains)
    for m in _DOMAIN_PATTERN.finditer(content):
        _add("domain", m.group(1), "content_scan", 0.7, "Domain from content")

    return entities


def extract_entities_from_fields(observation: RawObservation) -> list[ExtractedEntity]:
    """Extract entities from observation fields (identifiers list).

    These are structured identifiers provided by the source adapter.
    Higher confidence than content scanning.
    """
    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    for ident in observation.identifiers:
        kind = ident.get("kind", "")
        value = ident.get("value", "")
        if not kind or not value:
            continue

        normalized = normalize_identifier(kind, value)
        key = (kind, normalized)
        if key in seen:
            continue
        seen.add(key)

        entities.append(ExtractedEntity(
            kind=kind,
            original_value=value,
            normalized_value=normalized,
            label=ident.get("label"),
            extraction_method="field_extract",
            confidence=0.95,  # Structured field extraction is high confidence
        ))

    return entities


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------

def resolve_entities(
    session: Session,
    entities: list[ExtractedEntity],
    source_name: str,
) -> list[ResolvedEntity]:
    """Resolve extracted entities against existing actors.

    Resolution strategy:
    1. Exact normalized identifier match (to ALL matching actors)
    2. Unresolved (new entity — not yet linked to an actor)

    When the same normalized identifier exists for multiple actors,
    we create a ResolvedEntity for EACH actor — this is critical
    for detecting cross-actor sharing in the relationship creation step.

    Every resolution carries provenance metadata.
    """
    resolved: list[ResolvedEntity] = []

    # Build lookup: (kind, normalized_value) → list of (actor_id, persona_id, source_id)
    existing_ids = list(session.execute(
        select(Identifier.kind, Identifier.normalized_value, Identifier.actor_id, Identifier.persona_id, Identifier.source_id)
    ).all())

    id_lookup: dict[tuple[str, str], list[dict[str, str | None]]] = {}
    for kind, norm_val, actor_id, persona_id, source_id in existing_ids:
        key = (kind, norm_val)
        id_lookup.setdefault(key, []).append({
            "actor_id": actor_id,
            "persona_id": persona_id,
            "source_id": source_id,
        })

    # Resolve actor codes
    all_actor_ids = set()
    for matches in id_lookup.values():
        for m in matches:
            if m["actor_id"]:
                all_actor_ids.add(m["actor_id"])

    actor_code_map: dict[str, str] = {}
    if all_actor_ids:
        actors = session.execute(
            select(Actor.id, Actor.code).where(Actor.id.in_(list(all_actor_ids)))
        ).all()
        actor_code_map = {a.id: a.code for a in actors}

    # Resolve each entity — may produce multiple resolutions if shared
    for entity in entities:
        key = (entity.kind, entity.normalized_value)
        matches = id_lookup.get(key, [])

        if matches:
            for m in matches:
                resolved.append(ResolvedEntity(
                    entity=entity,
                    actor_code=actor_code_map.get(m["actor_id"]),
                    actor_id=m["actor_id"],
                    resolution_method="exact_normalized_match",
                    resolution_confidence=0.95,
                    persona_id=m["persona_id"],
                    source_id=m["source_id"],
                ))
        else:
            resolved.append(ResolvedEntity(
                entity=entity,
                actor_code=None,
                actor_id=None,
                resolution_method="unresolved",
                resolution_confidence=0.0,
            ))

    return resolved


# ---------------------------------------------------------------------------
# Relationship creation
# ---------------------------------------------------------------------------

def _make_deterministic_id(parts: list[str]) -> str:
    """Create a deterministic ID from ordered parts."""
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def create_relationships_from_resolved(
    session: Session,
    actor_resolved: dict[str, list[ResolvedEntity]],
    observations: list[RawObservation],
    source: Source,
) -> int:
    """Create relationships from pre-resolved entities grouped by actor.

    This is called once per ingestion run (not per observation), avoiding
    session-level dedup issues.
    """
    actor_codes = sorted(actor_resolved.keys())
    new_rels = 0
    seen_pairs: set[tuple[str, str]] = set()

    for i, code_a in enumerate(actor_codes):
        for code_b in actor_codes[i + 1:]:
            pair = (code_a, code_b)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            # Find shared identifier kinds between these two actors
            shared_kinds: set[str] = set()
            for ra in actor_resolved.get(code_a, []):
                for rb in actor_resolved.get(code_b, []):
                    if (ra.entity.kind == rb.entity.kind and
                        ra.entity.normalized_value == rb.entity.normalized_value):
                        shared_kinds.add(ra.entity.kind)

            if not shared_kinds:
                continue

            # Check idempotency — does this relationship already exist?
            sorted_pair = sorted([code_a, code_b])
            rel_code = _make_deterministic_id(["INGESTED", sorted_pair[0], sorted_pair[1]])
            existing = session.execute(
                select(Relationship).where(Relationship.code == rel_code)
            ).scalar_one_or_none()

            if existing:
                # Update the existing relationship's last_seen
                obs = observations[0]
                if obs.retrieved_at:
                    existing.last_seen = datetime.fromisoformat(obs.retrieved_at)
                continue

            # Create new relationship
            actor_a = session.execute(
                select(Actor).where(Actor.code == code_a)
            ).scalar_one_or_none()
            actor_b = session.execute(
                select(Actor).where(Actor.code == code_b)
            ).scalar_one_or_none()

            if not actor_a or not actor_b:
                continue

            kind_list = ", ".join(sorted(shared_kinds))
            rel = Relationship(
                code=rel_code,
                kind="POSSIBLY_SAME_AS",
                from_type="actors",
                from_id=actor_a.id,
                to_type="actors",
                to_id=actor_b.id,
                confidence=0.0,  # computed by ConfidenceEngine
                band="low",
                status="pending",
                engine_ref="ingestion_pipeline",
                hypothesis_label=f"Shared identifiers ({kind_list}) discovered via ingestion",
                explanation=f"Entity ingestion found shared {kind_list} between {code_a} and {code_b}.",
                scoring_factors=[],
                source_id=source.id,
                first_seen=datetime.fromisoformat(observations[0].retrieved_at) if observations[0].retrieved_at else None,
                last_seen=datetime.fromisoformat(observations[0].retrieved_at) if observations[0].retrieved_at else None,
            )
            session.add(rel)
            new_rels += 1

            # Create evidence for each shared identifier
            for kind in sorted(shared_kinds):
                ev_code = _make_deterministic_id(["EVID-INGEST", rel_code, kind])
                ev_existing = session.execute(
                    select(Evidence).where(Evidence.code == ev_code)
                ).scalar_one_or_none()
                if not ev_existing:
                    evidence = Evidence(
                        code=ev_code,
                        kind=f"{kind}_match" if kind in ("pgp_key", "wallet", "jabber") else "identifier_match",
                        title=f"Shared {kind} discovered via ingestion",
                        description=f"Entity ingestion found matching {kind} identifier between {code_a} and {code_b}.",
                        strength="strong" if kind in ("pgp_key", "wallet") else "moderate",
                        evidence_class="OBSERVED_FACT",
                        score_contribution=0.0,  # computed by engine
                        relationship_id=rel.id,
                        source_id=source.id,
                        details={
                            "kind": kind,
                            "source": source.name,
                            "method": "entity_ingestion",
                        },
                    )
                    session.add(evidence)

            # Create timeline event
            evt = TimelineEvent(
                kind="relationship_added",
                actor_id=actor_a.id,
                entity_type="relationship",
                entity_id=rel.id,
                title=f"Ingested relationship: {code_a} {code_b}",
                detail=f"Shared {kind_list} found via ingestion from {source.name}",
                occurred_at=datetime.fromisoformat(observations[0].retrieved_at) if observations[0].retrieved_at else datetime.utcnow(),
                source_id=source.id,
                metadata_json={
                    "pipeline": "ingestion",
                    "source": source.name,
                    "shared_kinds": list(shared_kinds),
                },
            )
            session.add(evt)

    return new_rels


def create_relationships(
    session: Session,
    resolved_entities: list[ResolvedEntity],
    observation: RawObservation,
    source: Source,
) -> int:
    """Create relationship and evidence records from resolved entities.

    Returns the number of new relationships created (idempotent).
    """
    # Group resolved entities by actor
    actor_entities: dict[str, list[ResolvedEntity]] = {}
    for r in resolved_entities:
        if r.actor_code and r.actor_id:
            actor_entities.setdefault(r.actor_code, []).append(r)

    # Find pairs of actors that share identifiers from this observation
    actor_codes = sorted(actor_entities.keys())
    new_rels = 0

    for i, code_a in enumerate(actor_codes):
        for code_b in actor_codes[i + 1:]:
            # Find shared identifier kinds
            shared_kinds: set[str] = set()
            for ra in actor_entities[code_a]:
                for rb in actor_entities[code_b]:
                    if ra.entity.kind == rb.entity.kind and ra.entity.normalized_value == rb.entity.normalized_value:
                        shared_kinds.add(ra.entity.kind)

            if not shared_kinds:
                continue

            # Check idempotency — does this relationship already exist for this actor pair?
            # Use actor pair + engine_ref to detect duplicates across observations
            sorted_pair = sorted([code_a, code_b])
            rel_code = _make_deterministic_id(["INGESTED", sorted_pair[0], sorted_pair[1]])
            existing = session.execute(
                select(Relationship).where(Relationship.code == rel_code)
            ).scalar_one_or_none()

            if existing:
                # Update the existing relationship's last_seen and add evidence
                if observation.retrieved_at:
                    existing.last_seen = datetime.fromisoformat(observation.retrieved_at)
                continue

            # Create new relationship
            actor_a = session.execute(
                select(Actor).where(Actor.code == code_a)
            ).scalar_one_or_none()
            actor_b = session.execute(
                select(Actor).where(Actor.code == code_b)
            ).scalar_one_or_none()

            if not actor_a or not actor_b:
                continue

            kind_list = ", ".join(sorted(shared_kinds))
            rel = Relationship(
                code=rel_code,
                kind="POSSIBLY_SAME_AS",
                from_type="actors",
                from_id=actor_a.id,
                to_type="actors",
                to_id=actor_b.id,
                confidence=0.0,  # computed by ConfidenceEngine
                band="low",
                status="pending",
                engine_ref="ingestion_pipeline",
                hypothesis_label=f"Shared identifiers ({kind_list}) discovered via ingestion from {observation.source_name}",
                explanation=f"Entity ingestion from {observation.source_name} found shared {kind_list} between {code_a} and {code_b}.",
                scoring_factors=[],
                source_id=source.id,
                first_seen=datetime.fromisoformat(observation.retrieved_at) if observation.retrieved_at else None,
                last_seen=datetime.fromisoformat(observation.retrieved_at) if observation.retrieved_at else None,
            )
            session.add(rel)
            new_rels += 1

            # Create evidence for each shared identifier
            for kind in sorted(shared_kinds):
                ev_code = _make_deterministic_id(["EVID-INGEST", rel_code, kind])
                ev_existing = session.execute(
                    select(Evidence).where(Evidence.code == ev_code)
                ).scalar_one_or_none()
                if not ev_existing:
                    evidence = Evidence(
                        code=ev_code,
                        kind=f"{kind}_match" if kind in ("pgp_key", "wallet", "jabber") else "identifier_match",
                        title=f"Shared {kind} discovered via ingestion",
                        description=f"Entity ingestion from {observation.source_name} found matching {kind} identifier between {code_a} and {code_b}.",
                        strength="strong" if kind in ("pgp_key", "wallet") else "moderate",
                        evidence_class="OBSERVED_FACT",
                        score_contribution=0.0,  # computed by engine
                        relationship_id=rel.id,
                        source_id=source.id,
                        details={
                            "kind": kind,
                            "source": observation.source_name,
                            "method": "entity_ingestion",
                            "external_id": observation.external_id,
                        },
                    )
                    session.add(evidence)

            # Create timeline event
            existing_evt = session.execute(
                select(TimelineEvent).where(
                    TimelineEvent.title == f"Ingested relationship: {code_a} {code_b}"
                )
            ).scalars().first()
            if not existing_evt:
                evt = TimelineEvent(
                    kind="relationship_added",
                    actor_id=actor_a.id,
                    entity_type="relationship",
                    entity_id=rel.id,
                    title=f"Ingested relationship: {code_a} ↔ {code_b}",
                    detail=f"Shared {kind_list} found via ingestion from {observation.source_name}",
                    occurred_at=datetime.fromisoformat(observation.retrieved_at) if observation.retrieved_at else datetime.utcnow(),
                    source_id=source.id,
                    metadata_json={
                        "pipeline": "ingestion",
                        "source": observation.source_name,
                        "shared_kinds": list(shared_kinds),
                    },
                )
                session.add(evt)

    return new_rels


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

def run_ingestion_pipeline(
    observations: list[RawObservation],
    session: Session,
) -> IngestionResult:
    """Run the complete ingestion pipeline on a list of observations.

    Pipeline: OBSERVATION → EXTRACTION → RESOLUTION → RELATIONSHIP → CORRELATION

    Returns IngestionResult with full statistics.
    """
    result = IngestionResult(
        task_id="",
        source=observations[0].source_name if observations else "unknown",
        status="running",
        started_at=datetime.utcnow().isoformat(),
    )

    # Track entities extracted/resolved
    all_resolved: list[ResolvedEntity] = []

    for obs in observations:
        try:
            # 1. Resolve the source and enforce the DATABASE.md §2 boundary
            #    BEFORE any write. Sources must be registered (and enabled,
            #    with access_method synthetic|authorized|public) ahead of
            #    ingestion — the pipeline never self-registers a source it
            #    was merely told about. Unknown names are recorded as errors.
            source = session.execute(
                select(Source).where(Source.name == obs.source_name)
            ).scalar_one_or_none()

            from app.ingestion.boundary import (
                ForbiddenSourceError,
                assert_source_allowed,
            )

            try:
                assert_source_allowed(source, source_name=obs.source_name)
            except ForbiddenSourceError as exc:
                result.errors.append(
                    {
                        "record": obs.external_id,
                        "reason": "source_not_ingestable",
                        "detail": str(exc),
                    }
                )
                log.warning("boundary refused source %r: %s", obs.source_name, exc)
                continue

            # 2. Extract entities from fields (structured data)
            field_entities = extract_entities_from_fields(obs)

            # 3. Extract entities from content (text scanning)
            content_entities = extract_entities_from_content(obs.content)

            # Merge, deduplicating
            all_entities = field_entities + content_entities
            result.entities_extracted += len(all_entities)

            # 4. Resolve entities against existing actors
            resolved = resolve_entities(session, all_entities, obs.source_name)
            all_resolved.extend(resolved)

            resolved_count = sum(1 for r in resolved if r.resolution_method != "unresolved")
            result.entities_resolved += resolved_count

            result.observations_processed += 1

        except Exception as exc:
            result.errors.append(f"Error processing observation {obs.external_id}: {exc}")
            log.warning("ingestion error for %s: %s", obs.external_id, exc)

    # 5. Create relationships from resolved entities
    # Collect all resolved entities grouped by actor, then create relationships once
    # This avoids session-level dedup issues when the same actor pair appears in multiple observations
    actor_resolved: dict[str, list[ResolvedEntity]] = {}  # actor_code → [ResolvedEntity]
    actor_source: dict[str, str] = {}  # actor_code → first observation's source_name
    for resolved in all_resolved:
        if resolved.actor_code:
            actor_resolved.setdefault(resolved.actor_code, []).append(resolved)
            if resolved.actor_code not in actor_source:
                actor_source[resolved.actor_code] = resolved.entity.extraction_method  # just for tracking

    # Create relationship source object
    obs_source = session.execute(
        select(Source).where(Source.name == observations[0].source_name)
    ).scalar_one_or_none()
    if obs_source:
        new_rels = create_relationships_from_resolved(session, actor_resolved, observations, obs_source)
        result.relationships_created = new_rels
        result.timeline_events_created = new_rels

    # Flush new relationships so the confidence engine can see them
    session.flush()

    # 6. Recompute confidence for new relationships
    try:
        ce = ConfidenceEngine(session)
        new_rels_stmt = select(Relationship).where(Relationship.engine_ref == "ingestion_pipeline")
        for rel in session.execute(new_rels_stmt).scalars().all():
            if rel.from_id and rel.to_id:
                from_actor = session.execute(select(Actor.code).where(Actor.id == rel.from_id)).scalar_one_or_none()
                to_actor = session.execute(select(Actor.code).where(Actor.id == rel.to_id)).scalar_one_or_none()
                if from_actor and to_actor:
                    cr = ce.compute_confidence(from_actor, to_actor)
                    if cr.score > 0:
                        rel.confidence = cr.score
                        rel.band = cr.band.lower()
                        rel.scoring_factors = [
                            {"signal": c.signal_type, "weight": c.weight, "score": round(c.weighted_score, 1), "note": c.explanation}
                            for c in cr.signals
                        ]
                    else:
                        # No signals found — use the correlation engine's raw score
                        from app.services.correlation import CorrelationEngine
                        corr_engine = CorrelationEngine(session)
                        corr_result = corr_engine.correlate(from_actor, to_actor)
                        rel.confidence = corr_result.total_score
                        rel.band = corr_result.band
                        rel.scoring_factors = [
                            {"signal": s.signal_type, "weight": s.weight, "score": s.score, "note": s.explanation}
                            for s in corr_result.signals
                        ]
    except Exception as exc:
        result.errors.append(f"Confidence recomputation error: {exc}")
        log.warning("confidence recomputation failed: %s", exc)

    session.flush()

    result.status = "completed"
    result.completed_at = datetime.utcnow().isoformat()
    log.info(
        "ingestion complete: %d observations, %d entities, %d resolved, %d relationships",
        result.observations_processed,
        result.entities_extracted,
        result.entities_resolved,
        result.relationships_created,
    )
    return result


# ---------------------------------------------------------------------------
# Task integration (uses existing TaskBackend abstraction)
# ---------------------------------------------------------------------------

def submit_ingestion_task(
    observations: list[RawObservation],
) -> IngestionResult:
    """Submit ingestion to the task backend (local or Celery).

    In local mode, this runs synchronously.
    In production mode, this would be submitted to Celery.
    """
    from app.core.database import SessionLocal

    def _run() -> IngestionResult:
        session = SessionLocal()
        try:
            result = run_ingestion_pipeline(observations, session)
            session.commit()
            return result
        except Exception as exc:
            session.rollback()
            raise
        finally:
            session.close()

    task_backend = get_task_backend()
    handle = task_backend.submit(_run)
    # For local mode, wait for result
    result = handle.get_result(timeout=30)
    result.task_id = handle.task_id
    return result
