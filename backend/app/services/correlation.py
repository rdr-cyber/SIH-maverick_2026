"""Signal and Correlation Engine.

Pipeline:
    OBSERVATION -> SIGNAL -> CORRELATION -> EVIDENCE

Signal types:
    1. PGP_MATCH
    2. WALLET_MATCH
    3. HANDLE_SIMILARITY
    4. STYLOMETRY_SIMILARITY
    5. BEHAVIOR_SIMILARITY
    6. INFRASTRUCTURE_RELATIONSHIP
    7. DOMAIN_RELATIONSHIP
    8. CERTIFICATE_RELATIONSHIP
    9. COMMUNICATION_IDENTIFIER_MATCH
    10. TEMPORAL_CORRELATION

Every signal must contain:
    signal_id, signal_type, source_entity, target_entity,
    raw_value, normalized_value, strength, source, timestamp, explanation,
    evidence_direction (SUPPORTING / CONTRADICTING / NEUTRAL),
    temporal_decay_factor

No individual signal is treated as identity proof.
No intrusive deanonymization techniques.
All data is synthetic.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import Actor, Identifier
from app.models.intel import Evidence, Relationship

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Temporal decay policy (documented, deterministic)
# ---------------------------------------------------------------------------
# Cryptographic identifiers (PGP, wallet, cert fingerprint) do NOT decay.
# Communication identifiers decay slowly.
# Behavioral signals decay faster.
# Stylometric signals decay moderately.

TEMPORAL_DECAY_POLICY: dict[str, float] = {
    # type -> half-life in days (None means no decay)
    "pgp_match": None,  # cryptographic: no decay
    "wallet_match": None,  # cryptographic: no decay
    "certificate_fingerprint": None,  # cryptographic: no decay
    "handle_match": 730,  # 2-year half-life (handles can be reused intentionally)
    "handle_similarity": 365,  # 1-year half-life
    "communication_match": 365,  # XMPP contacts are somewhat persistent
    "infrastructure_reuse": 365,  # domains/onion services
    "certificate_domain_relationship": 365,  # cert-domain binding
    "stylometric_similarity": 180,  # 6-month half-life (writing style evolves)
    "behavior_similarity": 90,  # 3-month half-life (behavior patterns shift)
    "temporal_correlation": 180,  # timing evidence
}


def compute_temporal_decay(signal_type: str, observation_age_days: float) -> float:
    """Compute deterministic temporal decay factor for a signal type.

    Returns 0.0 to 1.0 where 1.0 = no decay, 0.0 = fully decayed.

    Decay formula: factor = 2^(-age / half_life)
    Cryptographic identifiers (half_life=None) always return 1.0.
    """
    half_life = TEMPORAL_DECAY_POLICY.get(signal_type)
    if half_life is None or half_life <= 0:
        return 1.0
    if observation_age_days <= 0:
        return 1.0
    import math
    return math.pow(2, -observation_age_days / half_life)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A single correlation signal between two actors.

    Every signal carries full explainability metadata:
    - signal_id: deterministic unique ID for this signal
    - signal_type: what kind of signal
    - source_entity: first entity (actor code)
    - target_entity: second entity (actor code)
    - raw_value: the raw observed value
    - normalized_value: normalized/comparable value
    - strength: weak/moderate/strong
    - source: where this signal was observed
    - timestamp: when it was observed
    - explanation: human-readable description
    - weight: configured weight for this signal type
    - raw_score: score before source reliability and temporal decay
    - weighted_score: score after reliability and decay applied
    - evidence_direction: SUPPORTING, CONTRADICTING, or NEUTRAL
    - temporal_decay_factor: how much age has reduced this signal (1.0 = no decay)
    - source_reliability: reliability of the source (0-100)
    - details: structured metadata about the match
    """
    signal_id: str
    signal_type: str
    source_entity: str
    target_entity: str
    raw_value: str | float
    normalized_value: str | float
    strength: str  # weak, moderate, strong
    source: str
    timestamp: str
    explanation: str
    weight: int = 0
    raw_score: int = 0
    weighted_score: float = 0.0
    evidence_direction: str = "SUPPORTING"  # SUPPORTING, CONTRADICTING, NEUTRAL
    temporal_decay_factor: float = 1.0
    source_reliability: float = 50.0
    details: dict[str, Any] = field(default_factory=dict)

    # Legacy compat: score = raw_score
    @property
    def score(self) -> int:
        return self.raw_score

    @score.setter
    def score(self, value: int) -> None:
        self.raw_score = value


def _make_signal_id(sig_type: str, entity_a: str, entity_b: str, value: str) -> str:
    """Deterministic signal ID from type + entities + value."""
    raw = f"{sig_type}:{entity_a}:{entity_b}:{value}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class CorrelationResult:
    """Result of correlating two actors."""
    actor_a: str
    actor_b: str
    signals: list[Signal] = field(default_factory=list)
    total_score: float = 0.0
    raw_score: float = 0.0
    weighted_score: float = 0.0
    band: str = "low"
    explanation: str = ""
    hypothesis_label: str = ""


# ---------------------------------------------------------------------------
# Helper: parse time windows
# ---------------------------------------------------------------------------

def _parse_time_window(window: str) -> tuple[int, int] | None:
    """Parse 'HH:MM-HH:MM' into (start_hour, end_hour)."""
    m = re.match(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", window)
    if not m:
        return None
    return int(m.group(1)), int(m.group(3))


def _time_overlap(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Compute overlap ratio between two time windows (wrapping at 24h).

    Returns 0.0 to 1.0 where 1.0 = perfect overlap.
    """
    a_start, a_end = a
    b_start, b_end = b

    # Normalize: if end < start, it wraps past midnight
    a_len = (a_end - a_start) % 24 or 24
    b_len = (b_end - b_start) % 24 or 24

    # Compute overlap
    overlap = 0
    for h in range(24):
        in_a = (h - a_start) % 24 < a_len
        in_b = (h - b_start) % 24 < b_len
        if in_a and in_b:
            overlap += 1

    max_len = max(a_len, b_len)
    return overlap / max_len if max_len > 0 else 0.0


def _jaccard_similarity(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def _cosine_ngram_similarity(a: str, b: str, n: int = 2) -> float:
    """Character n-gram cosine similarity (deterministic, interpretable)."""
    if len(a) < n or len(b) < n:
        return 0.0

    def ngrams(s: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for i in range(len(s) - n + 1):
            ng = s[i:i + n]
            counts[ng] = counts.get(ng, 0) + 1
        return counts

    a_ng = ngrams(a.lower())
    b_ng = ngrams(b.lower())

    # Dot product
    dot = sum(a_ng.get(k, 0) * b_ng.get(k, 0) for k in set(a_ng) | set(b_ng))
    mag_a = sum(v ** 2 for v in a_ng.values()) ** 0.5
    mag_b = sum(v ** 2 for v in b_ng.values()) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _make_signal(
    sig_type: str,
    entity_a: str,
    entity_b: str,
    value: str | float,
    *,
    normalized_value: str | float | None = None,
    strength: str,
    source: str,
    explanation: str,
    weight: int,
    raw_score: int | None = None,
    evidence_direction: str = "SUPPORTING",
    details: dict[str, Any] | None = None,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Signal:
    """Factory that computes weighted_score from raw_score, source_reliability, and temporal decay."""
    _raw = raw_score if raw_score is not None else weight
    _decay = compute_temporal_decay(sig_type, observation_age_days)
    # Source reliability factor: maps 0-100 -> 0.5-1.0
    _rel_factor = 0.5 + (source_reliability / 200.0)
    _weighted = _raw * _rel_factor * _decay

    return Signal(
        signal_id=_make_signal_id(sig_type, entity_a, entity_b, str(value)),
        signal_type=sig_type,
        source_entity=entity_a,
        target_entity=entity_b,
        raw_value=value,
        normalized_value=normalized_value if normalized_value is not None else value,
        strength=strength,
        source=source,
        timestamp=datetime.now().isoformat(),
        explanation=explanation,
        weight=weight,
        raw_score=_raw,
        weighted_score=round(_weighted, 1),
        evidence_direction=evidence_direction,
        temporal_decay_factor=round(_decay, 4),
        source_reliability=source_reliability,
        details=details or {},
    )


# ---------------------------------------------------------------------------
# Signal evaluators
# ---------------------------------------------------------------------------

def _eval_pgp(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Check for shared PGP fingerprints."""
    a_pgps = {i.normalized_value for i in a_ids if i.kind == "pgp_key"}
    b_pgps = {i.normalized_value for i in b_ids if i.kind == "pgp_key"}
    shared = a_pgps & b_pgps
    if not shared:
        return None
    fp = list(shared)[0]
    weight = settings.correlation_weights.get("pgp", 30)
    return _make_signal(
        "pgp_match", entity_a, entity_b, fp,
        strength="strong",
        source="PGP key comparison",
        explanation=f"Identical PGP fingerprint {fp[:12]}\u2026{fp[-4:]} found on both actors",
        weight=weight,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={"fingerprint": fp, "match_type": "exact", "algorithm": "RSA-4096"},
    )


def _eval_pgp_negative(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
) -> Optional[Signal]:
    """Check for contradictory PGP: both have PGP keys but none shared.

    This is a CONTRADICTING signal when both actors have PGP keys but no overlap.
    This is NOT generated when one or both actors lack PGP keys (that's absence, not contradiction).
    """
    a_pgps = {i.normalized_value for i in a_ids if i.kind == "pgp_key"}
    b_pgps = {i.normalized_value for i in b_ids if i.kind == "pgp_key"}
    if not a_pgps or not b_pgps:
        return None  # One or both lack PGP: no contradiction signal
    shared = a_pgps & b_pgps
    if shared:
        return None  # They share: positive signal already generated
    # Both have PGP keys but none overlap: contradictory evidence
    return _make_signal(
        "pgp_nonmatch", entity_a, entity_b, "none_shared",
        normalized_value="different_keys",
        strength="moderate",
        source="PGP key comparison",
        explanation=(
            f"Actors have different PGP keys: "
            f"{entity_a} has {len(a_pgps)} key(s), {entity_b} has {len(b_pgps)} key(s), "
            f"no fingerprints match"
        ),
        weight=0,  # Contradicting signals have negative impact
        raw_score=0,
        evidence_direction="CONTRADICTING",
        source_reliability=source_reliability,
        details={
            "a_key_count": len(a_pgps),
            "b_key_count": len(b_pgps),
            "shared_count": 0,
            "note": "Differing PGP keys reduce confidence in same-actor hypothesis",
        },
    )


def _eval_wallet(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Check for shared wallet addresses."""
    a_wallets = {i.normalized_value for i in a_ids if i.kind == "wallet"}
    b_wallets = {i.normalized_value for i in b_ids if i.kind == "wallet"}
    shared = a_wallets & b_wallets
    if not shared:
        return None
    addr = list(shared)[0]
    weight = settings.correlation_weights.get("wallet", 25)
    return _make_signal(
        "wallet_match", entity_a, entity_b, addr,
        strength="strong",
        source="Blockchain indexer",
        explanation=f"Identical wallet address {addr[:12]}\u2026{addr[-4:]} found on both actors",
        weight=weight,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={"address": addr, "chain": "btc"},
    )


def _eval_handle(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Check for handle similarity or exact match."""
    a_handles = {i.normalized_value for i in a_ids if i.kind == "handle"}
    b_handles = {i.normalized_value for i in b_ids if i.kind == "handle"}

    # Exact match
    shared = a_handles & b_handles
    if shared:
        handle = list(shared)[0]
        weight = settings.correlation_weights.get("handle", 15)
        return _make_signal(
            "handle_match", entity_a, entity_b, handle,
            strength="strong",
            source="Handle comparison",
            explanation=f"Identical handle '{handle}' found on both actors",
            weight=weight,
            source_reliability=source_reliability,
            observation_age_days=observation_age_days,
            details={"handle": handle, "match_type": "exact"},
        )

    # Similar handles using character n-gram cosine similarity
    best_ratio = 0.0
    best_pair: tuple[str, str] | None = None
    for a_h in a_handles:
        for b_h in b_handles:
            if a_h == b_h:
                continue
            ratio = _cosine_ngram_similarity(a_h, b_h, n=2)
            if ratio > best_ratio:
                best_ratio = ratio
                best_pair = (a_h, b_h)

    if best_ratio > 0.5 and best_pair:
        weight = settings.correlation_weights.get("handle", 15)
        raw_score = max(3, int(weight * best_ratio * 0.5))
        strength = "strong" if best_ratio > 0.8 else "moderate"
        return _make_signal(
            "handle_similarity", entity_a, entity_b, f"{best_pair[0]}~{best_pair[1]}",
            normalized_value=round(best_ratio, 3),
            strength=strength,
            source="Handle comparison (n-gram cosine)",
            explanation=f"Handles '{best_pair[0]}' and '{best_pair[1]}' are structurally similar (cosine={best_ratio:.2f})",
            weight=weight,
            raw_score=raw_score,
            source_reliability=source_reliability,
            observation_age_days=observation_age_days,
            details={"pair": best_pair, "cosine": round(best_ratio, 3), "match_type": "similarity"},
        )
    return None


def _eval_jabber(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Check for shared communication identifiers (XMPP/Jabber)."""
    a_jids = {i.normalized_value for i in a_ids if i.kind == "jabber"}
    b_jids = {i.normalized_value for i in b_ids if i.kind == "jabber"}
    shared = a_jids & b_jids
    if not shared:
        return None
    jid = list(shared)[0]
    # XMPP shared support contacts are weaker signals than identity signals
    weight = settings.correlation_weights.get("jabber", 10)
    return _make_signal(
        "communication_match", entity_a, entity_b, jid,
        strength="moderate",
        source="Communication identifier comparison",
        explanation=f"Shared XMPP contact '{jid}' found on both actors",
        weight=weight,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={"jid": jid, "match_type": "exact", "channel": "xmpp"},
    )


def _eval_infrastructure(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Check for shared infrastructure (domains, onion services)."""
    infra_kinds = {"domain", "onion_service"}
    a_infra = {i.normalized_value for i in a_ids if i.kind in infra_kinds}
    b_infra = {i.normalized_value for i in b_ids if i.kind in infra_kinds}
    shared = a_infra & b_infra
    if not shared:
        return None
    infra = list(shared)[0]
    weight = settings.correlation_weights.get("infrastructure", 15)
    return _make_signal(
        "infrastructure_reuse", entity_a, entity_b, infra,
        strength="moderate",
        source="Infrastructure analysis",
        explanation=f"Shared infrastructure: {infra}",
        weight=weight,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={"infra": infra, "match_type": "exact"},
    )


def _eval_certificate(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 90.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Evaluate certificate relationships.

    Distinguishes:
    1. EXACT FINGERPRINT REUSE: same certificate fingerprint (strong signal)
    2. DOMAIN-CERT BINDING: same domain appears in both actors' identifiers AND a cert relationship exists

    Does NOT treat sharing a common CA issuer as identity evidence.
    """
    # Look for certificate-related identifiers
    # PGP keys that were observed from certificate observations serve as cert fingerprints
    a_certs = {i.normalized_value for i in a_ids if i.kind == "pgp_key"}
    b_certs = {i.normalized_value for i in b_ids if i.kind == "pgp_key"}

    # Also check for shared domains (which might indicate cert-domain binding)
    a_domains = {i.normalized_value for i in a_ids if i.kind == "domain"}
    b_domains = {i.normalized_value for i in b_ids if i.kind == "domain"}
    shared_domains = a_domains & b_domains

    # Exact fingerprint reuse
    shared_certs = a_certs & b_certs
    if shared_certs:
        fp = list(shared_certs)[0]
        # Only emit if this looks like a cert-sourced key (has a domain nearby)
        has_domain_context = bool(a_domains or b_domains)
        if has_domain_context:
            return _make_signal(
                "certificate_fingerprint", entity_a, entity_b, fp,
                strength="strong",
                source="Certificate transparency log",
                explanation=(
                    f"Same certificate fingerprint {fp[:12]}\u2026{fp[-4:]} observed "
                    f"for both actors' infrastructure, indicating TLS certificate reuse"
                ),
                weight=15,
                source_reliability=source_reliability,
                observation_age_days=observation_age_days,
                details={
                    "fingerprint": fp,
                    "match_type": "exact_fingerprint",
                    "note": "Certificate fingerprint reuse is strong infrastructure evidence",
                },
            )

    # Domain-certificate binding: same domain in both actors' identifiers
    # This is a weaker signal than fingerprint reuse
    if shared_domains:
        domain = list(shared_domains)[0]
        return _make_signal(
            "certificate_domain_relationship", entity_a, entity_b, domain,
            strength="moderate",
            source="Certificate transparency / infrastructure analysis",
            explanation=(
                f"Domain '{domain}' appears in both actors' infrastructure, "
                f"suggesting shared TLS certificate or hosting"
            ),
            weight=10,
            raw_score=8,
            source_reliability=source_reliability,
            observation_age_days=observation_age_days,
            details={
                "domain": domain,
                "match_type": "domain_binding",
                "note": "Domain overlap is moderate evidence of shared infrastructure",
            },
        )

    return None


def _eval_certificate_negative(
    a_ids: list[Identifier], b_ids: list[Identifier],
    entity_a: str, entity_b: str,
    *,
    source_reliability: float = 90.0,
) -> Optional[Signal]:
    """Check for false positive: actors share same CA issuer but different certificates.

    This is a NEUTRAL signal — it should NOT increase confidence.
    Only exact fingerprint reuse is meaningful.
    """
    a_domains = {i.normalized_value for i in a_ids if i.kind == "domain"}
    b_domains = {i.normalized_value for i in b_ids if i.kind == "domain"}
    if not a_domains or not b_domains:
        return None
    shared = a_domains & b_domains
    if shared:
        return None  # Already handled by _eval_certificate

    # Both have domains but none overlap, no shared cert fingerprint
    a_certs = {i.normalized_value for i in a_ids if i.kind == "pgp_key"}
    b_certs = {i.normalized_value for i in b_ids if i.kind == "pgp_key"}
    if a_certs & b_certs:
        return None  # Already handled

    if a_domains and b_domains and not (a_certs & b_certs):
        return _make_signal(
            "certificate_issuer_common", entity_a, entity_b, "different_certs",
            normalized_value="common_issuer_only",
            strength="weak",
            source="Certificate transparency log",
            explanation=(
                "Actors use certificates from different issuers with no overlapping fingerprints. "
                "Sharing a common CA (e.g. Let's Encrypt) is NOT identity evidence."
            ),
            weight=0,
            raw_score=0,
            evidence_direction="NEUTRAL",
            source_reliability=source_reliability,
            details={
                "a_cert_count": len(a_certs),
                "b_cert_count": len(b_certs),
                "shared_fp_count": 0,
                "note": "Common CA issuer is NOT evidence of same actor — this signal is neutral",
            },
        )
    return None


def _eval_stylometry(
    a_actor: Actor, b_actor: Actor,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Evaluate stylometric similarity using deterministic features.

    Compares:
    - post_style attribute (terse numbered offers, etc.)
    - listing_categories overlap
    - languages overlap
    Uses cosine n-gram similarity for text comparison.
    """
    a_attrs = a_actor.attributes or {}
    b_attrs = b_actor.attributes or {}

    features_compared = 0
    features_matched = 0
    explanations = []

    # 1. Post style comparison (exact match on writing pattern)
    a_style = a_attrs.get("post_style", "")
    b_style = b_attrs.get("post_style", "")
    if a_style and b_style:
        features_compared += 1
        if a_style == b_style:
            features_matched += 1
            explanations.append(f"identical writing pattern '{a_style}'")
        else:
            # Compare using character n-gram cosine similarity
            style_sim = _cosine_ngram_similarity(a_style, b_style, n=2)
            if style_sim > 0.7:
                features_matched += style_sim
                explanations.append(f"similar writing patterns (cosine={style_sim:.2f})")

    # 2. Listing categories overlap (what types of products/listings)
    a_cats = set(a_attrs.get("listing_categories", []))
    b_cats = set(b_attrs.get("listing_categories", []))
    if a_cats and b_cats:
        features_compared += 1
        jaccard = _jaccard_similarity(a_cats, b_cats)
        if jaccard > 0.3:
            features_matched += jaccard
            shared_cats = a_cats & b_cats
            explanations.append(f"shared listing categories: {', '.join(shared_cats)} (Jaccard={jaccard:.2f})")

    # 3. Language overlap (require >=2 shared languages — sharing just 'en' is too weak)
    a_langs = set(a_attrs.get("languages", []))
    b_langs = set(b_attrs.get("languages", []))
    if a_langs and b_langs:
        shared_langs = a_langs & b_langs
        if len(shared_langs) >= 2:
            features_compared += 1
            jaccard = _jaccard_similarity(a_langs, b_langs)
            features_matched += jaccard
            explanations.append(f"shared languages: {', '.join(shared_langs)} (Jaccard={jaccard:.2f})")

    # 4. Listing description style (n-gram similarity of summaries)
    a_summary = a_attrs.get("summary_style", "")
    b_summary = b_attrs.get("summary_style", "")
    if a_summary and b_summary:
        features_compared += 1
        sim = _cosine_ngram_similarity(a_summary, b_summary, n=3)
        if sim > 0.5:
            features_matched += sim
            explanations.append(f"similar listing description style (trigram cosine={sim:.2f})")

    if features_compared == 0 or features_matched == 0:
        return None

    # Compute aggregate similarity
    similarity = features_matched / features_compared if features_compared > 0 else 0.0
    weight = settings.correlation_weights.get("stylometry", 10)
    raw_score = max(2, int(weight * similarity))

    strength = "strong" if similarity > 0.8 else "moderate" if similarity > 0.5 else "weak"

    return _make_signal(
        "stylometric_similarity", a_actor.code, b_actor.code, round(similarity, 3),
        strength=strength,
        source="Stylometric analysis (deterministic features)",
        explanation=f"Stylometric similarity ({similarity:.0%}): {'; '.join(explanations)}",
        weight=weight,
        raw_score=raw_score,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={
            "features_compared": features_compared,
            "features_matched": round(features_matched, 2),
            "similarity": round(similarity, 3),
            "explanations": explanations,
        },
    )


def _eval_behavior(
    a_actor: Actor, b_actor: Actor,
    *,
    source_reliability: float = 50.0,
    observation_age_days: float = 0.0,
) -> Optional[Signal]:
    """Evaluate behavior similarity using deterministic features.

    Compares:
    - Active hours (time window overlap)
    - Posting frequency patterns
    - Category preferences
    - Migration timing
    """
    a_attrs = a_actor.attributes or {}
    b_attrs = b_actor.attributes or {}

    features_compared = 0
    features_matched = 0.0
    explanations = []

    # 1. Active hours overlap
    a_hours = a_attrs.get("active_hours_utc", "")
    b_hours = b_attrs.get("active_hours_utc", "")
    if a_hours and b_hours:
        a_window = _parse_time_window(a_hours)
        b_window = _parse_time_window(b_hours)
        if a_window and b_window:
            features_compared += 1
            overlap = _time_overlap(a_window, b_window)
            if overlap > 0.3:
                features_matched += overlap
                explanations.append(
                    f"active hours overlap ({a_hours} vs {b_hours}, {overlap:.0%} overlap)"
                )

    # 2. Category preference match
    a_cats = set(a_attrs.get("listing_categories", []))
    b_cats = set(b_attrs.get("listing_categories", []))
    if a_cats and b_cats:
        features_compared += 1
        jaccard = _jaccard_similarity(a_cats, b_cats)
        if jaccard > 0.3:
            features_matched += jaccard
            explanations.append(f"matching product categories (Jaccard={jaccard:.2f})")

    # 3. Hibernation / migration gap
    a_last = a_actor.last_seen
    b_first = b_actor.first_seen
    if a_last and b_first:
        features_compared += 1
        # Check if b appeared shortly after a went inactive
        gap_days = abs((b_first - a_last).days)
        if gap_days <= 60:  # Within 2 months
            match_score = max(0.3, 1.0 - gap_days / 60.0)
            features_matched += match_score
            explanations.append(
                f"migration timing: {b_actor.code} appeared {gap_days}d after {a_actor.code} went inactive"
            )

    # 4. Mirror rotation pattern similarity
    a_rotation = a_attrs.get("mirror_rotation_days", 0)
    b_rotation = b_attrs.get("mirror_rotation_days", 0)
    if a_rotation and b_rotation:
        features_compared += 1
        # Similar rotation patterns
        ratio = min(a_rotation, b_rotation) / max(a_rotation, b_rotation)
        if ratio > 0.7:
            features_matched += ratio
            explanations.append(f"similar mirror rotation pattern ({a_rotation}d vs {b_rotation}d)")

    if features_compared == 0 or features_matched == 0:
        return None

    similarity = features_matched / features_compared if features_compared > 0 else 0.0
    weight = settings.correlation_weights.get("behavior", 5)
    raw_score = max(1, int(weight * similarity))

    strength = "strong" if similarity > 0.8 else "moderate" if similarity > 0.5 else "weak"

    return _make_signal(
        "behavior_similarity", a_actor.code, b_actor.code, round(similarity, 3),
        strength=strength,
        source="Behavior analysis (deterministic features)",
        explanation=f"Behavioral similarity ({similarity:.0%}): {'; '.join(explanations)}",
        weight=weight,
        raw_score=raw_score,
        source_reliability=source_reliability,
        observation_age_days=observation_age_days,
        details={
            "features_compared": features_compared,
            "features_matched": round(features_matched, 2),
            "similarity": round(similarity, 3),
            "explanations": explanations,
        },
    )


def _eval_temporal(
    a_actor: Actor, b_actor: Actor,
    *,
    source_reliability: float = 50.0,
) -> Optional[Signal]:
    """Evaluate temporal correlation between two actors.

    Computes deterministic temporal features:
    - Activity overlap (are they active during the same period?)
    - Migration gap (how long between A disappearing and B appearing?)
    - Identifier reuse timing (same identifiers used after gap)
    """
    explanations = []
    features_compared = 0
    features_matched = 0.0

    a_last = a_actor.last_seen
    b_first = b_actor.first_seen
    b_last = b_actor.last_seen
    a_first = a_actor.first_seen

    if a_last and b_first:
        features_compared += 1
        gap_days = (b_first - a_last).days

        if -30 <= gap_days <= 60:
            # Overlap or small gap: strong temporal signal
            if gap_days <= 0:
                explanations.append(
                    f"Active period overlap: {b_actor.code} appeared while {a_actor.code} was still active "
                    f"({abs(gap_days)}d overlap)"
                )
                features_matched += 0.8
            else:
                explanations.append(
                    f"Migration gap: {b_actor.code} appeared {gap_days}d after "
                    f"{a_actor.code} went inactive — consistent with rebranding"
                )
                match_score = max(0.3, 1.0 - gap_days / 60.0)
                features_matched += match_score
        elif gap_days > 60:
            explanations.append(
                f"Large temporal gap: {gap_days}d between {a_actor.code} inactive and "
                f"{b_actor.code} first appearance — weak temporal correlation"
            )
            features_matched += 0.1

    # Activity duration comparison
    if a_first and a_last and b_first and b_last:
        features_compared += 1
        a_duration = (a_last - a_first).days
        b_duration = (b_last - b_first).days
        if a_duration > 0 and b_duration > 0:
            ratio = min(a_duration, b_duration) / max(a_duration, b_duration)
            if ratio > 0.3:
                features_matched += ratio * 0.5
                explanations.append(
                    f"Similar activity durations ({a_duration}d vs {b_duration}d)"
                )

    if features_compared == 0 or features_matched == 0:
        return None

    similarity = features_matched / features_compared
    weight = 5  # Temporal correlation is a supporting signal
    raw_score = max(1, int(weight * similarity))
    strength = "strong" if similarity > 0.7 else "moderate" if similarity > 0.4 else "weak"

    # Compute gap for explanation
    gap_desc = "concurrent"
    if a_last and b_first:
        gap = (b_first - a_last).days
        gap_desc = f"{gap}d gap"

    return _make_signal(
        "temporal_correlation", a_actor.code, b_actor.code, round(similarity, 3),
        strength=strength,
        source="Temporal analysis (deterministic)",
        explanation=f"Temporal correlation ({similarity:.0%}, {gap_desc}): {'; '.join(explanations)}",
        weight=weight,
        raw_score=raw_score,
        source_reliability=source_reliability,
        details={
            "features_compared": features_compared,
            "features_matched": round(features_matched, 2),
            "similarity": round(similarity, 3),
            "explanations": explanations,
            "gap_days": (b_first - a_last).days if a_last and b_first else None,
        },
    )


# ---------------------------------------------------------------------------
# Contradictory signal evaluator
# ---------------------------------------------------------------------------

def _eval_behavior_negative(
    a_actor: Actor, b_actor: Actor,
    *,
    source_reliability: float = 50.0,
) -> Optional[Signal]:
    """Check for contradictory behavior: strongly inconsistent activity windows.

    Only generates a contradiction signal when BOTH actors have active_hours
    and those windows have ZERO overlap.
    """
    a_attrs = a_actor.attributes or {}
    b_attrs = b_actor.attributes or {}
    a_hours = a_attrs.get("active_hours_utc", "")
    b_hours = b_attrs.get("active_hours_utc", "")

    if not a_hours or not b_hours:
        return None

    a_window = _parse_time_window(a_hours)
    b_window = _parse_time_window(b_hours)
    if not a_window or not b_window:
        return None

    overlap = _time_overlap(a_window, b_window)
    if overlap > 0.0:
        return None  # There is some overlap, not contradictory

    # Zero overlap in active hours: contradictory
    return _make_signal(
        "behavior_time_mismatch", a_actor.code, b_actor.code, "zero_overlap",
        normalized_value=0.0,
        strength="moderate",
        source="Behavior analysis (temporal windows)",
        explanation=(
            f"Active hours do not overlap: {a_actor.code} active {a_hours} UTC, "
            f"{b_actor.code} active {b_hours} UTC — inconsistent activity patterns"
        ),
        weight=0,
        raw_score=0,
        evidence_direction="CONTRADICTING",
        source_reliability=source_reliability,
        details={
            "a_hours": a_hours,
            "b_hours": b_hours,
            "overlap": 0.0,
            "note": "Zero active-hours overlap reduces confidence in same-actor hypothesis",
        },
    )


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
        Separates raw correlation from reliability-weighted attribution.
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

        # Compute source reliabilities for both actors
        a_reliability = self._get_avg_source_reliability(actor_a)
        b_reliability = self._get_avg_source_reliability(actor_b)
        avg_reliability = (a_reliability + b_reliability) / 2.0

        # Compute evidence age based on when evidence was LAST SEEN (not first_seen).
        # A PGP key seen last month is fresh evidence regardless of when the actor appeared.
        reference_date = datetime.utcnow()
        a_last = actor_a.last_seen or actor_a.first_seen
        b_last = actor_b.last_seen or actor_b.first_seen
        a_age = (reference_date - a_last).days if a_last else 180
        b_age = (reference_date - b_last).days if b_last else 180
        avg_age = (a_age + b_age) / 2.0

        # Evaluate all identifier-based signals
        signals: list[Signal] = []
        signal_kwargs = dict(
            source_reliability=avg_reliability,
            observation_age_days=avg_age,
        )

        for evaluator in [_eval_pgp, _eval_wallet, _eval_handle, _eval_jabber, _eval_infrastructure]:
            sig = evaluator(a_ids, b_ids, actor_a_code, actor_b_code, **signal_kwargs)
            if sig:
                signals.append(sig)

        # Certificate evaluation (high-reliability sources)
        cert_sig = _eval_certificate(a_ids, b_ids, actor_a_code, actor_b_code,
                                     source_reliability=90.0)
        if cert_sig:
            signals.append(cert_sig)

        # Evaluate behavioral signals
        for evaluator in [_eval_stylometry, _eval_behavior]:
            sig = evaluator(actor_a, actor_b, **signal_kwargs)
            if sig:
                signals.append(sig)

        # Temporal correlation
        temporal_sig = _eval_temporal(actor_a, actor_b, source_reliability=avg_reliability)
        if temporal_sig:
            signals.append(temporal_sig)

        # Contradictory evidence (negative signals)
        neg_pgp = _eval_pgp_negative(a_ids, b_ids, actor_a_code, actor_b_code,
                                      source_reliability=avg_reliability)
        if neg_pgp:
            signals.append(neg_pgp)

        neg_cert = _eval_certificate_negative(a_ids, b_ids, actor_a_code, actor_b_code,
                                               source_reliability=90.0)
        if neg_cert:
            signals.append(neg_cert)

        neg_behavior = _eval_behavior_negative(actor_a, actor_b, source_reliability=avg_reliability)
        if neg_behavior:
            signals.append(neg_behavior)

        # Compute scores
        # Raw score: sum of all raw_score values
        supporting_signals = [s for s in signals if s.evidence_direction == "SUPPORTING"]
        contradicting_signals = [s for s in signals if s.evidence_direction == "CONTRADICTING"]

        raw_total = sum(s.raw_score for s in supporting_signals)
        raw_total = min(raw_total, 100.0)

        # Weighted score: sum of weighted_score values (after reliability + decay)
        weighted_total = sum(s.weighted_score for s in supporting_signals)
        # Apply contradiction penalty: each contradicting signal reduces by 5 points
        contradiction_penalty = len(contradicting_signals) * 5
        weighted_total = max(0.0, weighted_total - contradiction_penalty)
        weighted_total = min(weighted_total, 100.0)

        # The total_score is the weighted score (used as the primary RCS)
        total_score = weighted_total

        # Determine band — consistent with confidence engine (LOW / MEDIUM / HIGH)
        if total_score >= 70:
            band = "high"
        elif total_score >= 40:
            band = "medium"
        else:
            band = "low"

        # Build explanation
        if supporting_signals:
            parts = [f"{s.signal_type} (+{s.weighted_score:.1f}): {s.explanation}" for s in supporting_signals]
            explanation = ". ".join(parts) + "."
        else:
            explanation = "No overlapping signals found between these actors."

        if contradicting_signals:
            neg_parts = [f"{s.signal_type}: {s.explanation}" for s in contradicting_signals]
            explanation += " CONTRADICTING: " + ". ".join(neg_parts) + "."

        # Build hypothesis label
        if total_score >= 70:
            hypothesis = f"Strong possibility that {actor_a_code} and {actor_b_code} are the same actor"
        elif total_score >= 50:
            hypothesis = f"Moderate evidence linking {actor_a_code} and {actor_b_code}"
        elif total_score >= 30:
            hypothesis = f"Weak signals between {actor_a_code} and {actor_b_code} \u2014 treat with caution"
        else:
            hypothesis = f"Insufficient evidence to link {actor_a_code} and {actor_b_code}"

        return CorrelationResult(
            actor_a=actor_a_code,
            actor_b=actor_b_code,
            signals=signals,
            total_score=total_score,
            raw_score=raw_total,
            weighted_score=weighted_total,
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

    def _get_avg_source_reliability(self, actor: Actor) -> float:
        """Get the average source reliability for an actor's identifiers."""
        from app.models.identity import Source
        stmt = (
            select(Source.reliability)
            .join(Identifier, Identifier.source_id == Source.id)
            .where(Identifier.actor_id == actor.id)
        )
        reliabilities = list(self.session.execute(stmt).scalars().all())
        if reliabilities:
            return sum(reliabilities) / len(reliabilities)
        if actor.primary_source_id:
            source = self.session.execute(
                select(Source.reliability).where(Source.id == actor.primary_source_id)
            ).scalar_one_or_none()
            if source is not None:
                return float(source)
        return 50.0

    def _resolve_actor_name(self, actor_id: str) -> Optional[str]:
        row = self.session.execute(
            select(Actor.display_name).where(Actor.id == actor_id)
        ).scalar_one_or_none()
        return row
