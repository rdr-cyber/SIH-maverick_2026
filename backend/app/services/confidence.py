"""Confidence Engine: explainable Relationship Confidence Score.

Computes the RCS from:
1. Signal scores (from correlation engine)
2. Source reliability weighting
3. Evidence strength

Output:
- Score (0-100)
- Band (LOW / MEDIUM / HIGH)
- Explanation (how the score was derived)
- Supporting signals (with their contributions)

IMPORTANT: This is a decision heuristic for analysts, NOT a probability
of identity.  No claim of certainty is ever made.

The UI must show exactly how the score was derived.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.identity import Actor, Identifier, Source
from app.models.intel import Evidence, Relationship
from app.services.correlation import CorrelationEngine, Signal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confidence bands (simplified per requirements: LOW / MEDIUM / HIGH)
# ---------------------------------------------------------------------------

def _score_to_band(score: float) -> str:
    """Map RCS to confidence band.

    Per requirements: LOW / MEDIUM / HIGH
    """
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


# ---------------------------------------------------------------------------
# Confidence derivation
# ---------------------------------------------------------------------------

@dataclass
class SignalContribution:
    """How one signal contributed to the final score."""
    signal_type: str
    raw_score: int
    weight: int
    source_reliability: float
    weighted_score: float
    explanation: str
    source_name: str


@dataclass
class ConfidenceResult:
    """Full confidence derivation for a relationship.

    Contains:
    - The final RCS score and band
    - Every signal's contribution with source reliability
    - The derivation chain showing how the score was computed
    - A human-readable explanation
    """
    actor_a: str
    actor_b: str
    score: float
    band: str
    signals: list[SignalContribution] = field(default_factory=list)
    derivation: list[str] = field(default_factory=list)
    explanation: str = ""
    hypothesis_label: str = ""
    source_reliability_avg: float = 0.0
    disclaimer: str = (
        "This is a Relationship Confidence Score — a decision heuristic "
        "for analysts. It is NOT a probability of identity and does NOT "
        "claim certainty. Every inference requires human review."
    )


class ConfidenceEngine:
    """Computes explainable confidence scores with source reliability.

    The engine:
    1. Gathers signals from the correlation engine
    2. Looks up source reliability for each signal's evidence
    3. Applies source reliability as a weighting factor
    4. Computes the final RCS
    5. Produces a full derivation chain

    Source reliability ranges from 0-100:
    - 90+: certificate archives, blockchain indexers (high confidence)
    - 70-89: established marketplaces (moderate confidence)
    - 50-69: forums, paste sites (lower confidence)
    - <50: unverified sources (lowest confidence)
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.correlation = CorrelationEngine(session)

    def compute_confidence(
        self,
        actor_a_code: str,
        actor_b_code: str,
    ) -> ConfidenceResult:
        """Compute full confidence derivation for a relationship.

        Returns ConfidenceResult with score, band, derivation chain,
        and every signal's contribution with source reliability.
        """
        # Get correlation signals
        corr = self.correlation.correlate(actor_a_code, actor_b_code)

        if not corr.signals:
            return ConfidenceResult(
                actor_a=actor_a_code,
                actor_b=actor_b_code,
                score=0.0,
                band="LOW",
                explanation="No overlapping signals found between these actors.",
                hypothesis_label=f"Insufficient evidence to link {actor_a_code} and {actor_b_code}",
            )

        # Load actors for source lookup
        actor_a = self.session.execute(
            select(Actor).where(Actor.code == actor_a_code)
        ).scalar_one_or_none()
        actor_b = self.session.execute(
            select(Actor).where(Actor.code == actor_b_code)
        ).scalar_one_or_none()

        # Compute source reliability for each signal
        contributions: list[SignalContribution] = []
        derivation: list[str] = []
        total_weighted = 0.0
        total_weight = 0
        reliabilities: list[float] = []

        for signal in corr.signals:
            # Find source reliability
            reliability = self._get_signal_reliability(signal, actor_a, actor_b)
            reliabilities.append(reliability)

            # Apply source reliability as weighting factor (0.5 to 1.0)
            reliability_factor = 0.5 + (reliability / 200.0)  # Maps 0-100 → 0.5-1.0
            weighted_score = signal.score * reliability_factor

            # Find source name
            source_name = self._get_signal_source_name(signal, actor_a, actor_b)

            contrib = SignalContribution(
                signal_type=signal.type,
                raw_score=signal.score,
                weight=signal.weight,
                source_reliability=reliability,
                weighted_score=round(weighted_score, 1),
                explanation=signal.explanation,
                source_name=source_name,
            )
            contributions.append(contrib)

            total_weighted += weighted_score
            total_weight += signal.weight

            derivation.append(
                f"{signal.type}: raw={signal.score}/{signal.weight} "
                f"× reliability_factor={reliability_factor:.2f} "
                f"(source={source_name}, reliability={reliability}) "
                f"= {weighted_score:.1f}"
            )

        # Cap at 100
        final_score = min(total_weighted, 100.0)
        band = _score_to_band(final_score)

        # Average source reliability
        avg_reliability = sum(reliabilities) / len(reliabilities) if reliabilities else 0.0

        # Build explanation
        signal_parts = []
        for c in contributions:
            signal_parts.append(
                f"{c.signal_type} (+{c.weighted_score:.1f}): {c.explanation} "
                f"[source: {c.source_name}, reliability: {c.source_reliability}/100]"
            )
        explanation = ". ".join(signal_parts) + "."

        # Add source reliability note
        if avg_reliability < 60:
            explanation += (
                f" NOTE: Average source reliability is {avg_reliability:.0f}/100 "
                f"(below 60) — treat this score with additional caution."
            )

        # Build hypothesis label
        if final_score >= 70:
            hypothesis = (
                f"Strong possibility that {actor_a_code} and {actor_b_code} "
                f"are the same actor — but this is a hypothesis, not a conclusion"
            )
        elif final_score >= 40:
            hypothesis = (
                f"Moderate evidence linking {actor_a_code} and {actor_b_code} "
                f"— requires analyst review before any action"
            )
        else:
            hypothesis = (
                f"Weak signals between {actor_a_code} and {actor_b_code} "
                f"— insufficient for attribution"
            )

        return ConfidenceResult(
            actor_a=actor_a_code,
            actor_b=actor_b_code,
            score=round(final_score, 1),
            band=band,
            signals=contributions,
            derivation=derivation,
            explanation=explanation,
            hypothesis_label=hypothesis,
            source_reliability_avg=round(avg_reliability, 1),
        )

    def _get_signal_reliability(
        self,
        signal: Signal,
        actor_a: Optional[Actor],
        actor_b: Optional[Actor],
    ) -> float:
        """Get the average source reliability for a signal's evidence.

        Looks up the source of the identifiers that produced this signal.
        """
        if not actor_a or not actor_b:
            return 50.0  # default

        # Map signal type to identifier kind
        kind_map = {
            "pgp_match": "pgp_key",
            "wallet_match": "wallet",
            "handle_match": "handle",
            "handle_similarity": "handle",
            "infrastructure_reuse": "domain",  # approximation
            "stylometric_similarity": None,
            "behavior_similarity": None,
        }
        id_kind = kind_map.get(signal.type)

        if id_kind is None:
            # Stylometry/behavior — use actor's primary source reliability
            return self._get_actor_source_reliability(actor_a)

        # Find source reliability for matching identifiers
        stmt = (
            select(Source.reliability)
            .join(Identifier, Identifier.source_id == Source.id)
            .where(Identifier.kind == id_kind)
            .where(Identifier.actor_id.in_([actor_a.id, actor_b.id]))
        )
        reliabilities = list(self.session.execute(stmt).scalars().all())
        if reliabilities:
            return sum(reliabilities) / len(reliabilities)
        return 50.0

    def _get_actor_source_reliability(self, actor: Actor) -> float:
        """Get the reliability of an actor's primary source."""
        if actor.primary_source_id:
            source = self.session.execute(
                select(Source.reliability).where(Source.id == actor.primary_source_id)
            ).scalar_one_or_none()
            if source is not None:
                return float(source)
        return 50.0

    def _get_signal_source_name(
        self,
        signal: Signal,
        actor_a: Optional[Actor],
        actor_b: Optional[Actor],
    ) -> str:
        """Get the source name for a signal."""
        if signal.type in ("stylometric_similarity", "behavior_similarity"):
            return "Analytical engine"
        if not actor_a or not actor_b:
            return "Unknown"

        kind_map = {
            "pgp_match": "pgp_key",
            "wallet_match": "wallet",
            "handle_match": "handle",
            "handle_similarity": "handle",
            "infrastructure_reuse": "domain",
        }
        id_kind = kind_map.get(signal.type)
        if not id_kind:
            return "Unknown"

        stmt = (
            select(Source.name)
            .join(Identifier, Identifier.source_id == Source.id)
            .where(Identifier.kind == id_kind)
            .where(Identifier.actor_id.in_([actor_a.id, actor_b.id]))
            .limit(1)
        )
        name = self.session.execute(stmt).scalar_one_or_none()
        return name or "Unknown"
