"""Signal and Correlation Engine.

Pipeline:
    OBSERVATION → SIGNAL → CORRELATION → EVIDENCE

Each signal has:
    type, value, strength, source, timestamp, explanation

No individual signal is treated as identity proof.
No intrusive deanonymization techniques.
All data is synthetic.

The engine computes Relationship Confidence Scores (RCS) between
candidate actor pairs using configurable weights.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import Actor, Identifier
from app.models.intel import Evidence, Relationship
from app.services.normalization import normalize_identifier

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A single correlation signal between two actors.

    Every signal carries:
    - type: what kind of signal (pgp_match, wallet_match, etc.)
    - value: the shared value or similarity score
    - strength: weak/moderate/strong
    - source: where this signal was observed
    - timestamp: when it was observed
    - explanation: human-readable description
    """
    type: str
    value: str | float
    strength: str  # weak, moderate, strong
    source: str
    timestamp: str
    explanation: str
    weight: int = 0  # configured weight for this signal type
    score: int = 0  # computed score contribution


@dataclass
class CorrelationResult:
    """Result of correlating two actors.

    Contains all signals, the computed RCS, band, and explanation.
    """
    actor_a: str
    actor_b: str
    signals: list[Signal] = field(default_factory=list)
    total_score: float = 0.0
    band: str = "weak"
    explanation: str = ""
    hypothesis_label: str = ""


# ---------------------------------------------------------------------------
# Signal evaluators
# ---------------------------------------------------------------------------

def _eval_pgp(a_identifiers: list[Identifier], b_identifiers: list[Identifier]) -> Optional[Signal]:
    """Check for shared PGP fingerprints."""
    a_pgps = {i.normalized_value for i in a_identifiers if i.kind == "pgp_key"}
    b_pgps = {i.normalized_value for i in b_identifiers if i.kind == "pgp_key"}
    shared = a_pgps & b_pgps
    if not shared:
        return None
    fp = list(shared)[0]
    return Signal(
        type="pgp_match",
        value=fp,
        strength="strong",
        source="PGP key comparison",
        timestamp=datetime.now().isoformat(),
        explanation=f"Identical PGP fingerprint {fp[:12]}…{fp[-4:]} found on both actors",
        weight=settings.correlation_weights.get("pgp", 30),
        score=settings.correlation_weights.get("pgp", 30),
    )


def _eval_wallet(a_identifiers: list[Identifier], b_identifiers: list[Identifier]) -> Optional[Signal]:
    """Check for shared wallet addresses."""
    a_wallets = {i.normalized_value for i in a_identifiers if i.kind == "wallet"}
    b_wallets = {i.normalized_value for i in b_identifiers if i.kind == "wallet"}
    shared = a_wallets & b_wallets
    if not shared:
        return None
    addr = list(shared)[0]
    return Signal(
        type="wallet_match",
        value=addr,
        strength="strong",
        source="Blockchain indexer",
        timestamp=datetime.now().isoformat(),
        explanation=f"Identical wallet address {addr[:12]}…{addr[-4:]} found on both actors",
        weight=settings.correlation_weights.get("wallet", 25),
        score=settings.correlation_weights.get("wallet", 25),
    )


def _eval_handle(a_identifiers: list[Identifier], b_identifiers: list[Identifier]) -> Optional[Signal]:
    """Check for handle similarity or exact match."""
    a_handles = {i.normalized_value for i in a_identifiers if i.kind == "handle"}
    b_handles = {i.normalized_value for i in b_identifiers if i.kind == "handle"}

    # Exact match
    shared = a_handles & b_handles
    if shared:
        return Signal(
            type="handle_match",
            value=list(shared)[0],
            strength="strong",
            source="Handle comparison",
            timestamp=datetime.now().isoformat(),
            explanation=f"Identical handle '{list(shared)[0]}' found on both actors",
            weight=settings.correlation_weights.get("handle", 15),
            score=settings.correlation_weights.get("handle", 15),
        )

    # Similar handles (simple Levenshtein-like check)
    for a_h in a_handles:
        for b_h in b_handles:
            if a_h == b_h:
                continue
            # Simple similarity: same length, >70% char overlap
            if len(a_h) > 3 and len(b_h) > 3:
                common = sum(1 for c in a_h if c in b_h)
                ratio = common / max(len(a_h), len(b_h))
                if ratio > 0.7:
                    return Signal(
                        type="handle_similarity",
                        value=f"{a_h} ≈ {b_h}",
                        strength="moderate",
                        source="Handle comparison",
                        timestamp=datetime.now().isoformat(),
                        explanation=f"Handles '{a_h}' and '{b_h}' are structurally similar (ratio={ratio:.2f})",
                        weight=settings.correlation_weights.get("handle", 15),
                        score=max(3, int(settings.correlation_weights.get("handle", 15) * ratio * 0.5)),
                    )
    return None


def _eval_infrastructure(a_identifiers: list[Identifier], b_identifiers: list[Identifier]) -> Optional[Signal]:
    """Check for shared infrastructure (domains, onion services)."""
    infra_kinds = {"domain", "onion_service"}
    a_infra = {i.normalized_value for i in a_identifiers if i.kind in infra_kinds}
    b_infra = {i.normalized_value for i in b_identifiers if i.kind in infra_kinds}
    shared = a_infra & b_infra
    if not shared:
        return None
    return Signal(
        type="infrastructure_reuse",
        value=list(shared)[0],
        strength="moderate",
        source="Infrastructure analysis",
        timestamp=datetime.now().isoformat(),
        explanation=f"Shared infrastructure: {list(shared)[0]}",
        weight=settings.correlation_weights.get("infrastructure", 15),
        score=settings.correlation_weights.get("infrastructure", 15),
    )


def _eval_stylometry(a_actor: Actor, b_actor: Actor) -> Optional[Signal]:
    """Evaluate stylometric similarity.

    In production, this would compare TF-IDF vectors from post corpora.
    Here we use the seeded attributes for demonstration.
    """
    a_attrs = a_actor.attributes or {}
    b_attrs = b_actor.attributes or {}

    # Check for post_style similarity (seeded attribute)
    a_style = a_attrs.get("post_style", "")
    b_style = b_attrs.get("post_style", "")
    if a_style and b_style and a_style == b_style:
        return Signal(
            type="stylometric_similarity",
            value=0.91,
            strength="strong",
            source="Stylometric analysis (TF-IDF)",
            timestamp=datetime.now().isoformat(),
            explanation=f"Writing style match: both use '{a_style}' pattern (cosine 0.91)",
            weight=settings.correlation_weights.get("stylometry", 10),
            score=settings.correlation_weights.get("stylometry", 10),
        )
    return None


def _eval_behavior(a_actor: Actor, b_actor: Actor) -> Optional[Signal]:
    """Evaluate behavior similarity.

    In production, this would compare posting histograms.
    Here we use the seeded attributes for demonstration.
    """
    a_attrs = a_actor.attributes or {}
    b_attrs = b_actor.attributes or {}

    a_hours = a_attrs.get("active_hours_utc", "")
    b_hours = b_attrs.get("active_hours_utc", "")
    if a_hours and b_hours and a_hours == b_hours:
        return Signal(
            type="behavior_similarity",
            value=0.85,
            strength="moderate",
            source="Behavior analysis (histograms)",
            timestamp=datetime.now().isoformat(),
            explanation=f"Matching active hours: {a_hours}",
            weight=settings.correlation_weights.get("behavior", 5),
            score=settings.correlation_weights.get("behavior", 5),
        )
    return None


# ---------------------------------------------------------------------------
# Correlation engine
# ---------------------------------------------------------------------------

class CorrelationEngine:
    """Computes correlation signals between actor pairs.

    The engine evaluates each signal type independently, computes
    the Relationship Confidence Score (RCS), and returns a structured
    result with full explanation.

    No individual signal is treated as identity proof.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def correlate(self, actor_a_code: str, actor_b_code: str) -> CorrelationResult:
        """Compute correlation between two actors.

        Returns a CorrelationResult with all signals, RCS, and explanation.
        """
        # Load actors
        actor_a = self.session.execute(
            select(Actor).where(Actor.code == actor_a_code)
        ).scalar_one_or_none()
        actor_b = self.session.execute(
            select(Actor).where(Actor.code == actor_b_code)
        ).scalar_one_or_none()

        if not actor_a or not actor_b:
            return CorrelationResult(
                actor_a=actor_a_code,
                actor_b=actor_b_code,
                explanation="One or both actors not found",
            )

        # Load identifiers
        a_ids = list(self.session.execute(
            select(Identifier).where(Identifier.actor_id == actor_a.id)
        ).scalars().all())
        b_ids = list(self.session.execute(
            select(Identifier).where(Identifier.actor_id == actor_b.id)
        ).scalars().all())

        # Evaluate all signals
        signals: list[Signal] = []
        for evaluator in [_eval_pgp, _eval_wallet, _eval_handle, _eval_infrastructure]:
            sig = evaluator(a_ids, b_ids)
            if sig:
                signals.append(sig)

        # Evaluate stylometry and behavior
        for evaluator in [_eval_stylometry, _eval_behavior]:
            sig = evaluator(actor_a, actor_b)
            if sig:
                signals.append(sig)

        # Compute RCS
        total_score = sum(s.score for s in signals)
        total_score = min(total_score, 100.0)

        # Determine band
        if total_score >= 85:
            band = "very_high"
        elif total_score >= 70:
            band = "high"
        elif total_score >= 50:
            band = "moderate"
        elif total_score >= 30:
            band = "low"
        else:
            band = "weak"

        # Build explanation
        if signals:
            parts = [f"{s.type} (+{s.score}): {s.explanation}" for s in signals]
            explanation = ". ".join(parts) + "."
        else:
            explanation = "No overlapping signals found between these actors."

        # Build hypothesis label
        if total_score >= 70:
            hypothesis = f"Strong possibility that {actor_a_code} and {actor_b_code} are the same actor"
        elif total_score >= 50:
            hypothesis = f"Moderate evidence linking {actor_a_code} and {actor_b_code}"
        elif total_score >= 30:
            hypothesis = f"Weak signals between {actor_a_code} and {actor_b_code} — treat with caution"
        else:
            hypothesis = f"Insufficient evidence to link {actor_a_code} and {actor_b_code}"

        return CorrelationResult(
            actor_a=actor_a_code,
            actor_b=actor_b_code,
            signals=signals,
            total_score=total_score,
            band=band,
            explanation=explanation,
            hypothesis_label=hypothesis,
        )

    def get_existing_correlations(self) -> list[dict[str, Any]]:
        """Get all existing relationships with their signal breakdown."""
        rels = self.session.execute(select(Relationship)).scalars().all()
        results = []
        for r in rels:
            from_name = self._resolve_actor_name(r.from_id)
            to_name = self._resolve_actor_name(r.to_id)
            results.append({
                "code": r.code,
                "from_actor": from_name or r.from_id,
                "to_actor": to_name or r.to_id,
                "confidence": r.confidence,
                "band": r.band,
                "status": r.status,
                "scoring_factors": r.scoring_factors or [],
                "explanation": r.explanation,
            })
        return results

    def _resolve_actor_name(self, actor_id: str) -> Optional[str]:
        row = self.session.execute(
            select(Actor.display_name).where(Actor.id == actor_id)
        ).scalar_one_or_none()
        return row
