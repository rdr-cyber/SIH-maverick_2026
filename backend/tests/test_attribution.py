"""Attribution test suite: false positives, certificates, temporal, contradictions.

Tests the correlation and confidence engines for:
- Strong attribution (darkmerchant ↔ shadow_vendor)
- Certificate fingerprint reuse (quietsteel ↔ iron_broker)
- Certificate false positive (common CA issuer only)
- Temporal boundaries
- Contradictory evidence
- Unrelated actor pairs
- Confidence explanation completeness

Run: python tests/test_attribution.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import os
os.environ["DATABASE_URL"] = "sqlite:///"
os.environ["SECRET_KEY"] = "test-key-for-attribution-tests"
os.environ["APP_MODE"] = "local"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"

from app.core.database import init_db, SessionLocal
from app.data_generation.seed import seed_database
from app.services.correlation import CorrelationEngine, compute_temporal_decay, TEMPORAL_DECAY_POLICY
from app.services.confidence import ConfidenceEngine

passed = 0
failed = 0
errors: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        msg = f"FAIL: {label} — {detail}" if detail else f"FAIL: {label}"
        errors.append(msg)
        print(f"  [FAIL] {label} ({detail})")


def section(title: str) -> None:
    print(f"\n  {title}")


# ============================================================================
# Setup
# ============================================================================
print("\n  TRILOK TRACE — Attribution Test Suite")
print("  " + "=" * 50)

init_db()
seed_database(reset=True)
session = SessionLocal()

# ============================================================================
# 1. DARKMERCHANT: Strong multi-signal attribution
# ============================================================================
section("1. DarkMerchant <-> shadow_vendor: Strong Attribution")

ce = ConfidenceEngine(session)
cr = ce.compute_confidence("darkmerchant", "shadow_vendor")

check("DM RCS > 0", cr.score > 0, str(cr.score))
check("DM RCS >= 40 (MEDIUM or higher)", cr.score >= 40, f"score={cr.score}, band={cr.band}")
check("DM band is MEDIUM or HIGH", cr.band in ("MEDIUM", "HIGH"), f"band={cr.band}")
check("DM raw_score > weighted_score", cr.raw_score >= cr.weighted_score, f"raw={cr.raw_score}, weighted={cr.weighted_score}")
check("DM has supporting signals", cr.evidence_quality.supporting_count > 0, str(cr.evidence_quality.supporting_count))
check("DM no contradicting signals", cr.evidence_quality.contradicting_count == 0, str(cr.evidence_quality.contradicting_count))
check("DM signal families >= 3", cr.evidence_quality.signal_families >= 3, str(cr.evidence_quality.signal_families))
check("DM has cryptographic signals", cr.evidence_quality.cryptographic_signals >= 1, str(cr.evidence_quality.cryptographic_signals))
check("DM has PGP match signal", any(s.signal_type == "pgp_match" for s in cr.signals), "missing pgp_match")
check("DM has wallet match signal", any(s.signal_type == "wallet_match" for s in cr.signals), "missing wallet_match")
check("DM has explanation", bool(cr.explanation), "empty explanation")
check("DM has disclaimer", bool(cr.disclaimer), "missing disclaimer")
check("DM has evidence_quality", bool(cr.evidence_quality), "missing evidence_quality")

# All DM signals should be SUPPORTING
dm_directions = [s.evidence_direction for s in cr.signals]
check("DM all signals SUPPORTING", all(d == "SUPPORTING" for d in dm_directions), str(dm_directions))


# ============================================================================
# 2. CERTIFICATE: Fingerprint reuse (quietsteel ↔ iron_broker)
# ============================================================================
section("2. quietsteel <-> iron_broker: Certificate Fingerprint Reuse")

cr2 = ce.compute_confidence("quietsteel", "iron_broker")

check("QS-IB RCS > 0", cr2.score > 0, str(cr2.score))
check("QS-IB has certificate_fingerprint signal",
      any(s.signal_type == "certificate_fingerprint" for s in cr2.signals),
      f"signals: {[s.signal_type for s in cr2.signals]}")
check("QS-IB has PGP match signal (shared cert fingerprint)",
      any(s.signal_type == "pgp_match" for s in cr2.signals),
      "missing pgp_match for shared cert fingerprint")

# The certificate signal should have high source reliability (cert archive)
cert_sig = next((s for s in cr2.signals if s.signal_type == "certificate_fingerprint"), None)
if cert_sig:
    check("QS-IB cert source_reliability >= 60", cert_sig.source_reliability >= 60, str(cert_sig.source_reliability))
    check("QS-IB cert evidence_direction SUPPORTING", cert_sig.evidence_direction == "SUPPORTING")
else:
    check("QS-IB cert signal exists", False, "certificate_fingerprint signal not found")

# Temporal correlation (both active in similar timeframe)
check("QS-IB has temporal correlation",
      any(s.signal_type == "temporal_correlation" for s in cr2.signals),
      f"signals: {[s.signal_type for s in cr2.signals]}")


# ============================================================================
# 3. CERTIFICATE FALSE POSITIVE: Common CA issuer only
# ============================================================================
section("3. ghostloader <-> iron_broker: Common CA Issuer Only (False Positive)")

cr3 = ce.compute_confidence("ghostloader", "iron_broker")

# These actors share a common CA issuer (Synthetic Interim CA R3) but
# different certificate fingerprints. This should NOT produce a strong signal.
check("GI RCS should be low", cr3.score < 30, f"score={cr3.score}")
check("GI band should be LOW", cr3.band == "LOW", f"band={cr3.band}")

# Should NOT have certificate_fingerprint signal (different fingerprints)
check("GI no certificate_fingerprint signal",
      not any(s.signal_type == "certificate_fingerprint" for s in cr3.signals),
      f"unexpected certificate_fingerprint in signals")

# Should have a neutral certificate_issuer_common signal
check("GI has neutral certificate_issuer_common signal",
      any(s.signal_type == "certificate_issuer_common" and s.evidence_direction == "NEUTRAL"
          for s in cr3.signals),
      f"signals: {[(s.signal_type, s.evidence_direction) for s in cr3.signals]}")


# ============================================================================
# 4. FALSE POSITIVE: Unrelated actors (darkmerchant ↔ quietsteel)
# ============================================================================
section("4. darkmerchant <-> quietsteel: Unrelated Actors (False Positive)")

cr4 = ce.compute_confidence("darkmerchant", "quietsteel")

check("DQ RCS should be very low (< 10)", cr4.score < 10, f"score={cr4.score}")
check("DQ band should be LOW", cr4.band == "LOW", f"band={cr4.band}")


# ============================================================================
# 5. FALSE POSITIVE: Common language only
# ============================================================================
section("5. nullbyte_9 <-> bazaar_ops: Common Language Only")

cr5 = ce.compute_confidence("nullbyte_9", "bazaar_ops")

check("NB-BO RCS should be 0 or very low", cr5.score < 10, f"score={cr5.score}")
check("NB-BO band should be LOW", cr5.band == "LOW", f"band={cr5.band}")


# ============================================================================
# 6. PHARMAKON ↔ REDSPARROW: Weak XMPP-only overlap
# ============================================================================
section("6. pharmakon <-> redsparrow: Weak XMPP Overlap")

cr6 = ce.compute_confidence("pharmakon", "redsparrow")

check("PH-RS RCS should be low", cr6.score < 15, f"score={cr6.score}")
check("PH-RS band should be LOW", cr6.band == "LOW", f"band={cr6.band}")
check("PH-RS has communication_match",
      any(s.signal_type == "communication_match" for s in cr6.signals),
      f"signals: {[s.signal_type for s in cr6.signals]}")
check("PH-RS communication_match is SUPPORTING not strong",
      any(s.signal_type == "communication_match" and s.evidence_direction == "SUPPORTING"
          for s in cr6.signals),
      "missing communication_match")


# ============================================================================
# 7. TEMPORAL DECAY: Policy and computation
# ============================================================================
section("7. Temporal Decay Policy")

check("pgp_match has no decay", compute_temporal_decay("pgp_match", 3650) == 1.0)
check("wallet_match has no decay", compute_temporal_decay("wallet_match", 3650) == 1.0)
check("certificate_fingerprint has no decay", compute_temporal_decay("certificate_fingerprint", 3650) == 1.0)

# Behavioral decay
decay_90 = compute_temporal_decay("behavior_similarity", 90)
decay_365 = compute_temporal_decay("behavior_similarity", 365)
check("behavior decay increases with age", decay_90 > decay_365, f"90d={decay_90}, 365d={decay_365}")
check("behavior 90d decay >= 0.5", decay_90 >= 0.5, str(decay_90))
check("behavior 365d decay < 0.1", decay_365 < 0.1, str(decay_365))

# Stylometric decay
decay_s90 = compute_temporal_decay("stylometric_similarity", 90)
decay_s365 = compute_temporal_decay("stylometric_similarity", 365)
check("stylometry decay increases with age", decay_s90 > decay_s365)

# 0 age = no decay
check("0 age = no decay for any type", compute_temporal_decay("behavior_similarity", 0) == 1.0)


# ============================================================================
# 8. CONTRADICTORY EVIDENCE: PGP nonmatch
# ============================================================================
section("8. Contradictory Evidence Detection")

from app.models.identity import Actor, Identifier
from sqlalchemy import select

# Create two actors with different PGP keys
actor_a_code = "test_actor_a"
actor_b_code = "test_actor_b"

from app.models.identity import Persona, Source

# Get a source
source = session.execute(select(Source).limit(1)).scalars().first()

# Create test actors
a_actor = Actor(code=actor_a_code, display_name="Test A", status="tracked",
                risk_level="low", category="other")
session.add(a_actor)
session.flush()

a_persona = Persona(actor_id=a_actor.id, source_id=source.id,
                    name="test_a", normalized_name="test_a", platform="test",
                    platform_type="forum", status="active", is_primary=True)
session.add(a_persona)
session.flush()

# Add PGP key for A
a_pgp = Identifier(actor_id=a_actor.id, persona_id=a_persona.id, source_id=source.id,
                   kind="pgp_key", value="AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555",
                   normalized_value="AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555")
session.add(a_pgp)

b_actor = Actor(code=actor_b_code, display_name="Test B", status="tracked",
                risk_level="low", category="other")
session.add(b_actor)
session.flush()

b_persona = Persona(actor_id=b_actor.id, source_id=source.id,
                    name="test_b", normalized_name="test_b", platform="test",
                    platform_type="forum", status="active", is_primary=True)
session.add(b_persona)
session.flush()

# Add DIFFERENT PGP key for B
b_pgp = Identifier(actor_id=b_actor.id, persona_id=b_persona.id, source_id=source.id,
                   kind="pgp_key", value="FFFF9999EEEE8888DDDD7777CCCC6666BBBB5555",
                   normalized_value="FFFF9999EEEE8888DDDD7777CCCC6666BBBB5555")
session.add(b_pgp)
session.flush()

# Now correlate
corr = CorrelationEngine(session)
result = corr.correlate(actor_a_code, actor_b_code)

check("Test actors have no PGP match signal",
      not any(s.signal_type == "pgp_match" for s in result.signals),
      f"unexpected pgp_match")

check("Test actors have PGP nonmatch contradicting signal",
      any(s.signal_type == "pgp_nonmatch" and s.evidence_direction == "CONTRADICTING"
          for s in result.signals),
      f"signals: {[(s.signal_type, s.evidence_direction) for s in result.signals]}")

# Also verify with confidence engine
cr_test = ce.compute_confidence(actor_a_code, actor_b_code)
check("Test actors RCS is 0 (only contradictory signal)", cr_test.score == 0, f"score={cr_test.score}")


# ============================================================================
# 9. CONFIDENCE EXPLANATION COMPLETENESS
# ============================================================================
section("9. Confidence Explanation Completeness")

cr_dm = ce.compute_confidence("darkmerchant", "shadow_vendor")

check("DM has raw_score", cr_dm.raw_score > 0, str(cr_dm.raw_score))
check("DM has weighted_score", cr_dm.weighted_score > 0, str(cr_dm.weighted_score))
check("DM has derivation chain", len(cr_dm.derivation) > 0, str(len(cr_dm.derivation)))
check("DM derivation contains signal types", any("pgp_match" in d for d in cr_dm.derivation))
check("DM explanation is non-empty", len(cr_dm.explanation) > 50, str(len(cr_dm.explanation)))
check("DM hypothesis_label is non-empty", len(cr_dm.hypothesis_label) > 20, str(cr_dm.hypothesis_label))

# Evidence quality completeness
eq = cr_dm.evidence_quality
check("EQ has source_reliability_avg", eq.source_reliability_avg > 0, str(eq.source_reliability_avg))
check("EQ has temporal_consistency", eq.temporal_consistency in ("High", "Moderate", "Low"))
check("EQ has identifier_strength", eq.identifier_strength in ("High", "Moderate", "Low"))
check("EQ has signal_families", eq.signal_families > 0, str(eq.signal_families))
check("EQ has cryptographic_signals", eq.cryptographic_signals > 0, str(eq.cryptographic_signals))


# ============================================================================
# 10. API-FRONTEND SCORE CONSISTENCY
# ============================================================================
section("10. API Score Consistency")

# Engine consistency (avoids TestClient session conflicts)
section("10. Engine Consistency")

corr_engine = CorrelationEngine(session)
corr_result = corr_engine.correlate("darkmerchant", "shadow_vendor")

check("Correlation result has raw_score", hasattr(corr_result, "raw_score"))
check("Correlation raw_score >= weighted_score", corr_result.raw_score >= corr_result.weighted_score)
check("Correlation weighted_score equals total_score", corr_result.weighted_score == corr_result.total_score)
check("Correlation has evidence_direction on signals",
      all(hasattr(s, "evidence_direction") for s in corr_result.signals))
check("Correlation has temporal_decay_factor on signals",
      all(hasattr(s, "temporal_decay_factor") for s in corr_result.signals))
check("Correlation has source_reliability on signals",
      all(hasattr(s, "source_reliability") for s in corr_result.signals))

# Confidence engine consistency
conf_result = ce.compute_confidence("darkmerchant", "shadow_vendor")
check("Confidence result has raw_score", hasattr(conf_result, "raw_score"))
check("Confidence result has weighted_score", hasattr(conf_result, "weighted_score"))
check("Confidence has evidence_quality", conf_result.evidence_quality is not None)
check("EQ has source_reliability_avg", conf_result.evidence_quality.source_reliability_avg > 0)
check("EQ has temporal_consistency", conf_result.evidence_quality.temporal_consistency in ("High", "Moderate", "Low"))
check("EQ has identifier_strength", conf_result.evidence_quality.identifier_strength in ("High", "Moderate", "Low"))
check("EQ has supporting_count", conf_result.evidence_quality.supporting_count > 0)
check("EQ has contradicting_count", conf_result.evidence_quality.contradicting_count == 0)
check("EQ has signal_families", conf_result.evidence_quality.signal_families > 0)


# ============================================================================
# Summary
# ============================================================================
print(f"\n{'=' * 60}")
print(f"  TOTAL: {passed} passed, {failed} failed, {passed + failed} checks")
print(f"{'=' * 60}")

if errors:
    print("\n  FAILURES:")
    for err in errors:
        print(f"    - {err}")

session.close()
sys.exit(1 if failed else 0)
