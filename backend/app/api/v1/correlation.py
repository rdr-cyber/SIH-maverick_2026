"""Correlation engine API endpoints.

Pipeline: OBSERVATION → SIGNAL → CORRELATION → EVIDENCE

Every signal has type, value, strength, source, timestamp, explanation.
No individual signal is treated as identity proof.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.services.correlation import CorrelationEngine

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/correlation", tags=["correlation"])


@router.get(
    "/evaluate",
    summary="Evaluate correlation between two actors",
)
def evaluate_correlation(
    session: DbSession,
    actor_a: Annotated[str, Query(description="First actor code")],
    actor_b: Annotated[str, Query(description="Second actor code")],
) -> dict:
    """Evaluate all signals between two actors and compute the RCS.

    Returns structured output with:
    - All detected signals (type, value, strength, source, timestamp, explanation)
    - Computed Relationship Confidence Score (RCS)
    - Confidence band (weak/low/moderate/high/very_high)
    - Human-readable explanation
    - Hypothesis label

    No individual signal is treated as identity proof.
    """
    engine = CorrelationEngine(session)
    result = engine.correlate(actor_a, actor_b)
    return {
        "actor_a": result.actor_a,
        "actor_b": result.actor_b,
        "signals": [
            {
                "signal_id": s.signal_id,
                "signal_type": s.signal_type,
                "source_entity": s.source_entity,
                "target_entity": s.target_entity,
                "raw_value": s.raw_value,
                "normalized_value": s.normalized_value,
                "strength": s.strength,
                "source": s.source,
                "timestamp": s.timestamp,
                "explanation": s.explanation,
                "weight": s.weight,
                "raw_score": s.raw_score,
                "weighted_score": s.weighted_score,
                "evidence_direction": s.evidence_direction,
                "temporal_decay_factor": s.temporal_decay_factor,
                "source_reliability": s.source_reliability,
                "details": s.details,
            }
            for s in result.signals
        ],
        "raw_score": result.raw_score,
        "weighted_score": result.weighted_score,
        "total_score": result.total_score,
        "band": result.band,
        "explanation": result.explanation,
        "hypothesis_label": result.hypothesis_label,
    }


@router.get(
    "/existing",
    summary="Get all existing correlations",
)
def get_existing_correlations(
    session: DbSession,
) -> list[dict]:
    """Get all existing relationships with their signal breakdown."""
    engine = CorrelationEngine(session)
    return engine.get_existing_correlations()
