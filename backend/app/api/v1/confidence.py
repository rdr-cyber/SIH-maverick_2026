"""Confidence engine API endpoint.

Computes explainable Relationship Confidence Scores with:
- Score (0-100)
- Band (LOW / MEDIUM / HIGH)
- Full derivation chain showing how the score was computed
- Source reliability weighting
- Every signal's contribution

IMPORTANT: This is a decision heuristic, NOT a probability of identity.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.models.identity import Actor
from app.models.intel import Relationship
from app.services.confidence import ConfidenceEngine

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/confidence", tags=["confidence"])


@router.get(
    "/evaluate",
    summary="Compute explainable confidence score for a relationship",
)
def evaluate_confidence(
    session: DbSession,
    actor_a: Annotated[str, Query(description="First actor code")],
    actor_b: Annotated[str, Query(description="Second actor code")],
) -> dict:
    """Compute the Relationship Confidence Score with full derivation.

    Returns:
    - score: 0-100 RCS
    - band: LOW / MEDIUM / HIGH
    - signals: each signal's contribution with source reliability
    - derivation: step-by-step computation chain
    - explanation: human-readable summary
    - hypothesis_label: what this score means
    - source_reliability_avg: average reliability of sources used
    - disclaimer: that this is NOT a probability of identity
    """
    engine = ConfidenceEngine(session)
    result = engine.compute_confidence(actor_a, actor_b)
    eq = result.evidence_quality
    return {
        "actor_a": result.actor_a,
        "actor_b": result.actor_b,
        "score": result.score,
        "band": result.band,
        "raw_score": result.raw_score,
        "weighted_score": result.weighted_score,
        "signals": [
            {
                "signal_type": s.signal_type,
                "raw_score": s.raw_score,
                "weight": s.weight,
                "source_reliability": s.source_reliability,
                "weighted_score": s.weighted_score,
                "explanation": s.explanation,
                "source_name": s.source_name,
                "evidence_direction": s.evidence_direction,
                "temporal_decay_factor": s.temporal_decay_factor,
                "matched_values": s.matched_values,
            }
            for s in result.signals
        ],
        "derivation": result.derivation,
        "explanation": result.explanation,
        "hypothesis_label": result.hypothesis_label,
        "source_reliability_avg": result.source_reliability_avg,
        "evidence_quality": {
            "source_reliability_avg": eq.source_reliability_avg,
            "temporal_consistency": eq.temporal_consistency,
            "identifier_strength": eq.identifier_strength,
            "supporting_count": eq.supporting_count,
            "contradicting_count": eq.contradicting_count,
            "neutral_count": eq.neutral_count,
            "signal_families": eq.signal_families,
            "cryptographic_signals": eq.cryptographic_signals,
            "behavioral_signals": eq.behavioral_signals,
        },
        "disclaimer": result.disclaimer,
    }


@router.get(
    "/existing",
    summary="List all existing relationships with confidence scores",
)
def existing_relationships(session: DbSession) -> dict:
    """Return all seeded/existing relationships with confidence evaluation."""
    # Get actors by code for resolving from_id/to_id
    actor_stmt = select(Actor)
    actors_by_id = {a.id: a for a in list(session.execute(actor_stmt).scalars().all())}

    stmt = (
        select(Relationship)
        .where(Relationship.kind == "POSSIBLY_SAME_AS")
        .order_by(Relationship.confidence.desc())
    )
    rels = list(session.execute(stmt).scalars().all())
    engine = ConfidenceEngine(session)

    results = []
    for rel in rels:
        actor_a = actors_by_id.get(rel.from_id)
        actor_b = actors_by_id.get(rel.to_id)
        if not actor_a or not actor_b:
            continue
        # Re-compute confidence from raw signals
        result = engine.compute_confidence(actor_a.code, actor_b.code)
        results.append({
            "code": rel.code,
            "actor_a": actor_a.code,
            "actor_b": actor_b.code,
            "kind": rel.kind,
            "score": result.score,
            "band": result.band,
            "status": rel.status,
            "disclaimer": result.disclaimer,
        })

    return {"relationships": results}
