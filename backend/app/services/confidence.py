"""Confidence Engine: explainable Relationship Confidence Score.

Computes the RCS from:
1. Signal scores (from correlation engine)
2. Source reliability weighting
3. Evidence quality factors
4. Temporal decay
5. Contradictory evidence penalty

Output:
- Raw correlation score (before reliability/decay)
- Final attribution confidence (after reliability/decay/contradiction)
- Score (0-100)
- Band (LOW / MEDIUM / HIGH)
- Explanation (how the score was derived)
- Supporting signals (with their contributions)
- Contradicting signals (with their impact)
- Evidence quality summary

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
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import Actor, Identifier, Source
from app.models.intel import Evidence, Relationship
from app.services.correlation import CorrelationEngine, Signal, TEMPORAL_DECAY_POLICY

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
    evidence_direction: str = "SUPPORTING"
    temporal_decay_factor: float = 1.0
    matched_values: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceQualitySummary:
    """Summary of evidence quality factors."""
    source_reliability_avg: float = 0.0
    temporal_consistency: str = "Unknown"
    identifier_strength: str = "Unknown"
    supporting_count: int = 0
    contradicting_count: int = 0
    neutral_count: int = 0
    signal_families: int = 0
    cryptographic_signals: int = 0
    behavioral_signals: int = 0


@dataclass
class ConfidenceResult:
    """Full confidence derivation for a relationship.

    Contains:
    - The final RCS score and band
    - The raw correlation score (before reliability adjustment)
    - Every signal's contribution with source reliability
    - The derivation chain showing how the score was computed
    - Supporting and contradicting signal breakdowns
    - Evidence quality summary
    - A human-readable explanation
    """
    actor_a: str
    actor_b: str
    score: float
    band: str
    raw_score: float = 0.0
    weighted_score: float = 0.0
    signals: list[SignalContribution] = field(default_factory=list)
    derivation: list[str] = field(default_factory=list)
    explanation: str = ""
    hypothesis_label: str = ""
    source_reliability_avg: float = 0.0
    evidence_quality: EvidenceQualitySummary = field(default_factory=EvidenceQualitySummary)
    disclaimer: str = (
        "This is a Relationship Confidence Score — a decision heuristic "
        "for analysts. It is NOT a probability of identity and does NOT "
        "claim certainty. Every inference requires human review."
    )


CRYPTOGRAPHIC_SIGNALS = {"pgp_match", "wallet_match", "certificate_fingerprint"}
BEHAVIORAL_SIGNALS = {"stylometric_similarity", "behavior_similarity", "temporal_correlation"}


class ConfidenceEngine:
    """Computes explainable confidence scores with source reliability.

    The engine:
    1. Gathers signals from the correlation engine
    2. Looks up source reliability for each signal's evidence
    3. Applies source reliability as a weighting factor
    4. Applies temporal decay
    5. Applies contradictory evidence penalty
    6. Computes the final RCS
    7. Produces a full derivation chain
    8. Separates raw correlation from final attribution confidence

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
        Separates raw correlation from final attribution confidence.
        """
        # Get correlation signals
        corr = self.correlation.correlate(actor_a_code, actor_b_code)

        if not corr.signals:
            return ConfidenceResult(
                actor_a=actor_a_code,
                actor_b=actor_b_code,
                score=0.0,
                band="LOW",
                raw_score=0.0,
                weighted_score=0.0,
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
        total_raw = 0.0
        total_weight = 0
        reliabilities: list[float] = []
        supporting_count = 0
        contradicting_count = 0
        neutral_count = 0
        signal_families: set[str] = set()
        cryptographic_count = 0
        behavioral_count = 0

        for signal in corr.signals:
            # Find source reliability
            reliability = self._get_signal_reliability(signal, actor_a, actor_b)
            reliabilities.append(reliability)

            # Apply source reliability as weighting factor (0.5 to 1.0)
            reliability_factor = 0.5 + (reliability / 200.0)  # Maps 0-100 -> 0.5-1.0

            # Apply temporal decay
            decay_factor = signal.temporal_decay_factor

            # Final weighted score
            weighted = signal.raw_score * reliability_factor * decay_factor

            # Find source name
            source_name = self._get_signal_source_name(signal, actor_a, actor_b)

            # Extract matched values from details
            matched = {}
            if signal.details.get("fingerprint"):
                matched["fingerprint"] = signal.details["fingerprint"]
            if signal.details.get("address"):
                matched["address"] = signal.details["address"]
            if signal.details.get("jid"):
                matched["jid"] = signal.details["jid"]
            if signal.details.get("handle"):
                matched["handle"] = signal.details["handle"]

            contrib = SignalContribution(
                signal_type=signal.signal_type,
                raw_score=signal.raw_score,
                weight=signal.weight,
                source_reliability=reliability,
                weighted_score=round(weighted, 1),
                explanation=signal.explanation,
                source_name=source_name,
                evidence_direction=signal.evidence_direction,
                temporal_decay_factor=decay_factor,
                matched_values=matched,
            )
            contributions.append(contrib)

            # Track statistics
            signal_families.add(signal.signal_type)
            if signal.signal_type in CRYPTOGRAPHIC_SIGNALS:
                cryptographic_count += 1
            if signal.signal_type in BEHAVIORAL_SIGNALS:
                behavioral_count += 1

            if signal.evidence_direction == "SUPPORTING":
                supporting_count += 1
                total_weighted += weighted
                total_raw += signal.raw_score
                total_weight += signal.weight
            elif signal.evidence_direction == "CONTRADICTING":
                contradicting_count += 1
                # Contradicting signals reduce the score
                total_weighted -= weighted * 0.5  # Half the weighted value as penalty
            else:
                neutral_count += 1

            direction_str = f" [{signal.evidence_direction}]" if signal.evidence_direction != "SUPPORTING" else ""
            derivation.append(
                f"{signal.signal_type}: raw={signal.raw_score}/{signal.weight} "
                f"x reliability_factor={reliability_factor:.2f} "
                f"x decay={decay_factor:.2f} "
                f"(source={source_name}, reliability={reliability}) "
                f"= {weighted:.1f}{direction_str}"
            )

        # Cap at 100
        final_score = max(0.0, min(total_weighted, 100.0))
        band = _score_to_band(final_score)

        # Average source reliability
        avg_reliability = sum(reliabilities) / len(reliabilities) if reliabilities else 0.0

        # Determine temporal consistency
        temporal_consistency = "High"
        if contradicting_count > 0:
            temporal_consistency = "Low"
        elif behavioral_count >= 2:
            temporal_consistency = "High"
        elif behavioral_count == 1:
            temporal_consistency = "Moderate"

        # Determine identifier strength
        identifier_strength = "High"
        if cryptographic_count >= 2:
            identifier_strength = "High"
        elif cryptographic_count == 1:
            identifier_strength = "Moderate"
        elif cryptographic_count == 0:
            identifier_strength = "Low"

        # Build evidence quality summary
        eq = EvidenceQualitySummary(
            source_reliability_avg=round(avg_reliability, 1),
            temporal_consistency=temporal_consistency,
            identifier_strength=identifier_strength,
            supporting_count=supporting_count,
            contradicting_count=contradicting_count,
            neutral_count=neutral_count,
            signal_families=len(signal_families),
            cryptographic_signals=cryptographic_count,
            behavioral_signals=behavioral_count,
        )

        # Build explanation
        supporting_contribs = [c for c in contributions if c.evidence_direction == "SUPPORTING"]
        contradicting_contribs = [c for c in contributions if c.evidence_direction == "CONTRADICTING"]

        signal_parts = []
        for c in supporting_contribs:
            signal_parts.append(
                f"{c.signal_type} (+{c.weighted_score:.1f}): {c.explanation} "
                f"[source: {c.source_name}, reliability: {c.source_reliability}/100]"
            )
        explanation = ". ".join(signal_parts) + "." if signal_parts else "No supporting signals."

        if contradicting_contribs:
            neg_parts = [f"{c.signal_type}: {c.explanation}" for c in contradicting_contribs]
            explanation += " CONTRADICTING: " + ". ".join(neg_parts) + "."

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
            raw_score=round(total_raw, 1),
            weighted_score=round(total_weighted, 1),
            signals=contributions,
            derivation=derivation,
            explanation=explanation,
            hypothesis_label=hypothesis,
            source_reliability_avg=round(avg_reliability, 1),
            evidence_quality=eq,
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
            "infrastructure_reuse": "domain",
            "communication_match": "jabber",
            "certificate_fingerprint": "pgp_key",
            "certificate_domain_relationship": "domain",
            "stylometric_similarity": None,
            "behavior_similarity": None,
            "temporal_correlation": None,
        }
        id_kind = kind_map.get(signal.signal_type)

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
        if signal.signal_type in ("stylometric_similarity", "behavior_similarity", "temporal_correlation"):
            return "Analytical engine"
        if not actor_a or not actor_b:
            return "Unknown"

        kind_map = {
            "pgp_match": "pgp_key",
            "wallet_match": "wallet",
            "handle_match": "handle",
            "handle_similarity": "handle",
            "infrastructure_reuse": "domain",
            "communication_match": "jabber",
            "certificate_fingerprint": "pgp_key",
            "certificate_domain_relationship": "domain",
        }
        id_kind = kind_map.get(signal.signal_type)
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
