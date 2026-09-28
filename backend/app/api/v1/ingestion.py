"""Ingestion API endpoints.

Provides:
- POST /ingestion/scan — trigger a synthetic ingestion scan
- GET  /ingestion/status — view recent ingestion results
- GET  /ingestion/provenance — trace an entity back to its source

All endpoints require authentication. Sensitive operations require appropriate roles.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user, require_role
from app.api.deps import DbSession
from app.data_generation.fixtures import (
    ALL_FIXTURES,
    DARKMERCHANT_FIXTURES,
    LAUNDERPIPE_FIXTURES,
    PHARMAKON_FIXTURES,
)
from app.models.identity import Identifier, Source
from app.models.intel import Relationship
from app.services.ingestion import (
    IngestionResult,
    RawObservation,
    submit_ingestion_task,
)
from sqlalchemy import func, select

router = APIRouter(
    dependencies=[Depends(get_current_user)],
    prefix="/ingestion",
    tags=["ingestion"],
)

# In-memory store for recent ingestion results (production would use a table)
_recent_results: list[dict] = []


@router.post("/scan", summary="Run synthetic ingestion scan",
             dependencies=[Depends(require_role("admin", "senior_analyst"))])
def run_scan(
    session: DbSession,
    scenario: str = Query(
        "all",
        description="Which scenario to ingest: all, darkmerchant, launderpipe, pharmakon",
    ),
) -> dict:
    """Trigger a synthetic ingestion scan.

    This runs the real local ingestion pipeline — it does NOT fake results.
    The pipeline extracts entities, resolves them against existing actors,
    creates relationships, and runs the confidence engine.

    Scenarios:
    - all: all synthetic fixtures
    - darkmerchant: DarkMerchant identity correlation fixtures
    - launderpipe: LaunderPipe wallet overlap fixtures
    - pharmakon: Pharmakon ↔ Redsparrow false positive fixtures
    """
    fixture_map = {
        "all": ALL_FIXTURES,
        "darkmerchant": DARKMERCHANT_FIXTURES,
        "launderpipe": LAUNDERPIPE_FIXTURES,
        "pharmakon": PHARMAKON_FIXTURES,
    }

    fixtures = fixture_map.get(scenario)
    if fixtures is None:
        return {"error": f"Unknown scenario: {scenario}. Available: {list(fixture_map.keys())}"}

    # Run the ingestion pipeline
    result = submit_ingestion_task(fixtures)

    # Store result for status queries
    result_dict = {
        "task_id": result.task_id,
        "source": result.source,
        "status": result.status,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "observations_processed": result.observations_processed,
        "entities_extracted": result.entities_extracted,
        "entities_resolved": result.entities_resolved,
        "relationships_created": result.relationships_created,
        "timeline_events_created": result.timeline_events_created,
        "errors": result.errors,
        "scenario": scenario,
    }
    _recent_results.insert(0, result_dict)
    # Keep only the last 20 results
    if len(_recent_results) > 20:
        _recent_results.pop()

    return result_dict


@router.get("/status", summary="View recent ingestion results")
def ingestion_status(
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Return recent ingestion scan results."""
    return _recent_results[:limit]


@router.get("/provenance", summary="View ingestion provenance")
def provenance(
    session: DbSession,
    entity_kind: str | None = Query(None, description="Filter by entity kind"),
    entity_value: str | None = Query(None, description="Filter by normalized value"),
    actor_code: str | None = Query(None, description="Filter by actor code"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Trace entities back to their source observations.

    Shows the provenance chain:
    Source → Observation → Extracted Entity → Resolved Actor → Relationship
    """
    from app.models.identity import Actor

    # Find relationships created by ingestion
    stmt = (
        select(Relationship)
        .where(Relationship.engine_ref == "ingestion_pipeline")
        .order_by(Relationship.created_at.desc())
        .limit(limit)
    )
    rels = list(session.execute(stmt).scalars().all())

    results = []
    for rel in rels:
        from_actor = session.execute(
            select(Actor).where(Actor.id == rel.from_id)
        ).scalar_one_or_none()
        to_actor = session.execute(
            select(Actor).where(Actor.id == rel.to_id)
        ).scalar_one_or_none()

        # Get source
        source = session.execute(
            select(Source).where(Source.id == rel.source_id)
        ).scalar_one_or_none() if rel.source_id else None

        results.append({
            "relationship_code": rel.code,
            "kind": rel.kind,
            "from_actor": from_actor.code if from_actor else rel.from_id,
            "to_actor": to_actor.code if to_actor else rel.to_id,
            "confidence": rel.confidence,
            "band": rel.band,
            "source": source.name if source else "Unknown",
            "source_kind": source.kind if source else "unknown",
            "first_seen": rel.first_seen.isoformat() if rel.first_seen else None,
            "explanation": rel.explanation,
            "scoring_factors": rel.scoring_factors or [],
        })

    return results


@router.get("/sources", summary="View ingestion sources")
def ingestion_sources(
    session: DbSession,
) -> list[dict]:
    """List all sources and their ingestion status."""
    sources = list(session.execute(select(Source).order_by(Source.name)).scalars().all())
    results = []
    for src in sources:
        actor_count = session.execute(
            select(func.count()).select_from(Identifier).where(Identifier.source_id == src.id)
        ).scalar() or 0
        results.append({
            "id": src.id,
            "name": src.name,
            "kind": src.kind,
            "trust_level": src.trust_level,
            "enabled": src.enabled,
            "last_scanned_at": src.last_scanned_at.isoformat() if src.last_scanned_at else None,
            "identifiers": actor_count,
        })
    return results
