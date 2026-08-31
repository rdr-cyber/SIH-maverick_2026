"""Deterministic synthetic intelligence catalogue.

Every value in this module is FABRICATED for the SIH demonstration. No real
person, marketplace, key, wallet or onion address is represented. Wallet
addresses and PGP fingerprints are syntactically plausible but deliberately
invalid, so they cannot be confused with live artifacts.

The catalogue is a literal (not randomly generated) so the demo is byte-for-byte
reproducible: the same actors, identifiers and dates every run. Phase 9 replaces
this module with pluggable ``SourceAdapter`` implementations; the shape of the
records it yields is the contract those adapters will satisfy.
"""
from __future__ import annotations

from typing import Any


def I(kind: str, value: str, label: str | None = None, **attrs: Any) -> dict[str, Any]:
    """Shorthand for one identifier record."""
    return {"kind": kind, "value": value, "label": label, "attributes": attrs}


def P(
    name: str,
    platform: str,
    *,
    platform_type: str = "marketplace",
    status: str = "active",
    primary: bool = False,
    reputation: str | None = None,
    first_seen: str,
    last_seen: str,
    identifiers: list[dict[str, Any]],
    **attrs: Any,
) -> dict[str, Any]:
    """Shorthand for one platform-scoped persona."""
    return {
        "name": name,
        "platform": platform,
        "platform_type": platform_type,
        "status": status,
        "is_primary": primary,
        "reputation": reputation,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "attributes": attrs,
        "identifiers": identifiers,
    }


SOURCES: list[dict[str, Any]] = [
    {
        "name": "Silk Harbor Market",
        "kind": "marketplace",
        "reliability": 78,
        "description": "Synthetic multi-vendor marketplace used as the primary demo source.",
        "last_scanned_at": "2026-08-28T04:12:00",
    },
    {
        "name": "Nightfall Bazaar",
        "kind": "marketplace",
        "reliability": 64,
        "description": "Synthetic successor marketplace; frequent vendor migrations.",
        "last_scanned_at": "2026-08-28T04:19:00",
    },
    {
        "name": "CipherTalk Forum",
        "kind": "forum",
        "reliability": 71,
        "description": "Synthetic discussion forum with long-lived reputation threads.",
        "last_scanned_at": "2026-08-27T21:40:00",
    },
    {
        "name": "Hollowpaste",
        "kind": "paste_site",
        "reliability": 45,
        "description": "Synthetic paste site; low reliability, high identifier density.",
        "last_scanned_at": "2026-08-26T11:05:00",
    },
    {
        "name": "Transparency Log Mirror",
        "kind": "certificate_archive",
        "reliability": 92,
        "description": "Synthetic certificate-transparency mirror for TLS metadata pivots.",
        "last_scanned_at": "2026-08-29T02:30:00",
    },
    {
        "name": "Chain Indexer",
        "kind": "blockchain_indexer",
        "reliability": 88,
        "description": "Synthetic chain indexer supplying wallet clustering metadata.",
        "last_scanned_at": "2026-08-29T03:02:00",
    },
]

# Identifiers deliberately shared between actors. These are the seams the
# Milestone 3+ correlation engine is meant to discover; Milestone 1 already
# surfaces them through search.
PGP_ALPHA = "9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6"
WALLET_ALPHA = "bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx"
WALLET_LAUNDER = "bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z"
JABBER_SHARED = "obsidian.ops@synthetic-xmpp.invalid"

# ---------------------------------------------------------------------------
# Relationships: the SIH flagship correlation scenario
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Analysts: demo users for the investigation workspace
# ---------------------------------------------------------------------------
ANALYSTS: list[dict[str, Any]] = [
    {
        "username": "admin",
        "full_name": "System Administrator",
        "email": "admin@shadowgraph.local",
        "password": "admin123",
        "role": "admin",
    },
    {
        "username": "jmartinez",
        "full_name": "J. Martinez",
        "email": "jmartinez@shadowgraph.local",
        "password": "analyst123",
        "role": "senior_analyst",
    },
    {
        "username": "akim",
        "full_name": "A. Kim",
        "email": "akim@shadowgraph.local",
        "password": "analyst123",
        "role": "analyst",
    },
]

# ---------------------------------------------------------------------------
# Investigations: demo investigations linked to existing actors
# ---------------------------------------------------------------------------
INVESTIGATIONS: list[dict[str, Any]] = [
    {
        "code": "INV-001",
        "title": "DarkMerchant Identity Correlation",
        "description": "Investigate whether shadow_vendor is a rebrand of darkmerchant based on PGP, wallet, stylometric, and behavioral signals.",
        "status": "active",
        "lead_analyst": "jmartinez",
        "targets": ["darkmerchant", "shadow_vendor"],
        "parameters": {
            "min_confidence": 40,
            "signal_weights": {"pgp": 30, "wallet": 25, "stylometry": 10, "behavior": 5},
        },
    },
    {
        "code": "INV-002",
        "title": "LaunderPipe Wallet Overlap",
        "description": "Assess whether the shared BTC consolidation address between launderpipe and crimson_ledger indicates identity or mere financial interaction.",
        "status": "draft",
        "lead_analyst": "akim",
        "targets": ["launderpipe", "crimson_ledger"],
        "parameters": {"min_confidence": 25},
    },
]

# ---------------------------------------------------------------------------
# Relationships: the SIH flagship correlation scenario
# ---------------------------------------------------------------------------
RELATIONSHIPS: list[dict[str, Any]] = [
    # darkmerchant ↔ shadow_vendor: POSSIBLY_SAME_AS — confidence computed at seed time
    # NOTE: confidence and band are overwritten by the ConfidenceEngine during seeding.
    # The values below are initial placeholders; the authoritative RCS is computed from
    # PGP match (30) + wallet match (25) = 55 raw, then weighted by source reliability.
    {
        "code": "REL-DM-SV-001",
        "kind": "POSSIBLY_SAME_AS",
        "from_type": "actors",
        "from_code": "darkmerchant",
        "to_type": "actors",
        "to_code": "shadow_vendor",
        "confidence": 0.0,  # computed by ConfidenceEngine at seed time
        "band": "low",     # computed by ConfidenceEngine at seed time
        "status": "pending",
        "engine_ref": "correlation_engine",
        "hypothesis_label": "shadow_vendor is a rebrand of darkmerchant",
        "explanation": (
            "PGP fingerprint match (+30): both personas advertise the same "
            "40-hex RSA-4096 key 9F2A4C81…A8F6.  Wallet address match (+25): "
            "identical BTC payout address bc1qk7m3v…klzx used on both "
            "Silk Harbor Market and Nightfall Bazaar.  Source reliability "
            "weighting adjusts the raw score to reflect source quality."
        ),
        "scoring_factors": [
            {"signal": "pgp_match", "weight": 30, "score": 30, "note": "identical fingerprint"},
            {"signal": "wallet_match", "weight": 25, "score": 25, "note": "identical BTC address"},
            {"signal": "communication_match", "weight": 10, "score": 10, "note": "shared XMPP escrow contact"},
            {"signal": "stylometric_similarity", "weight": 10, "score": 7, "note": "79% stylometric similarity"},
            {"signal": "behavior_similarity", "weight": 5, "score": 2, "note": "56% behavioral similarity"},
        ],
        "first_seen": "2026-08-28",
        "last_seen": "2026-08-28",
    },
    # launderpipe ↔ crimson_ledger: POSSIBLY_SAME_AS — wallet only, confidence computed at seed time
    {
        "code": "REL-LP-CL-001",
        "kind": "POSSIBLY_SAME_AS",
        "from_type": "actors",
        "from_code": "launderpipe",
        "to_type": "actors",
        "to_code": "crimson_ledger",
        "confidence": 0.0,  # computed by ConfidenceEngine at seed time
        "band": "low",     # computed by ConfidenceEngine at seed time
        "status": "pending",
        "engine_ref": "correlation_engine",
        "hypothesis_label": 'wallet overlap between launderpipe and crimson_ledger',
        "explanation": (
            "Wallet match (+25): both personas use the same BTC consolidation "
            "address bc1q0w9e8…k2l1z.  No other identity signals overlap — "
            "handles are unrelated, no shared PGP, no shared infra.  This is "
            "a single-signal correlation and should be treated with caution."
        ),
        "scoring_factors": [
            {"signal": "wallet", "weight": 25, "score": 25, "note": "identical BTC consolidation address"},
        ],
        "first_seen": "2026-08-29",
        "last_seen": "2026-08-29",
    },
    # quietsteel ↔ iron_broker: POSSIBLY_SAME_AS — CERTIFICATE FINGERPRINT
    {
        "code": "REL-QS-IB-001",
        "kind": "POSSIBLY_SAME_AS",
        "from_type": "actors",
        "from_code": "quietsteel",
        "to_type": "actors",
        "to_code": "iron_broker",
        "confidence": 0.0,  # computed by ConfidenceEngine at seed time
        "band": "low",     # computed by ConfidenceEngine at seed time
        "status": "pending",
        "engine_ref": "correlation_engine",
        "hypothesis_label": 'certificate fingerprint shared between quietsteel and iron_broker',
        "explanation": (
            "Certificate fingerprint match: both actors' infrastructure uses the same TLS "
            "certificate (A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9). This indicates shared "
            "hosting or infrastructure, but not necessarily the same actor."
        ),
        "scoring_factors": [
            {"signal": "certificate_fingerprint", "weight": 15, "score": 15, "note": "identical TLS certificate fingerprint"},
        ],
        "first_seen": "2026-08-29",
        "last_seen": "2026-08-29",
    },
    # pharmakon ↔ redsparrow: POSSIBLY_SAME_AS — WEAK (shared XMPP only)
    {
        "code": "REL-PH-RS-001",
        "kind": "POSSIBLY_SAME_AS",
        "from_type": "actors",
        "from_code": "pharmakon",
        "to_type": "actors",
        "to_code": "redsparrow",
        "confidence": 0.0,  # computed by ConfidenceEngine at seed time
        "band": "low",     # computed by ConfidenceEngine at seed time
        "status": "rejected",
        "engine_ref": "correlation_engine",
        "reviewed_by": "demo_analyst",
        "review_note": "Shared XMPP is a false positive — redsparrow is a fraud reseller, not narcotics.",
        "hypothesis_label": 'weak XMPP overlap between pharmakon and redsparrow',
        "explanation": (
            "Handle overlap is absent.  The only signal is a shared XMPP contact "
            "obsidian.ops@synthetic-xmpp.invalid which is a generic support "
            "channel used by multiple unrelated personas.  Score is below the "
            "Low threshold."
        ),
        "scoring_factors": [
            {"signal": "handle", "weight": 15, "score": 3, "note": "XMPP shared, not handle"},
        ],
        "first_seen": "2026-08-26",
        "last_seen": "2026-08-28",
    },
]

# ---------------------------------------------------------------------------
# Evidence items supporting relationships
# ---------------------------------------------------------------------------
EVIDENCE: list[dict[str, Any]] = [
    {
        "code": "EVID-001",
        "kind": "pgp_match",
        "title": "Shared PGP fingerprint",
        "description": "darkmerchant and shadow_vendor both advertise PGP key 9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6",
        "strength": "strong",
        "evidence_class": "OBSERVED_FACT",
        "score_contribution": 30.0,
        "relationship_code": "REL-DM-SV-001",
        "details": {"fingerprint": "9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6", "algorithm": "RSA-4096"},
    },
    {
        "code": "EVID-002",
        "kind": "wallet_match",
        "title": "Shared BTC payout address",
        "description": "Both personas use bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx as escrow payout",
        "strength": "strong",
        "evidence_class": "OBSERVED_FACT",
        "score_contribution": 25.0,
        "relationship_code": "REL-DM-SV-001",
        "details": {"address": "bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx", "chain": "btc"},
    },
    {
        "code": "EVID-003",
        "kind": "communication_match",
        "title": "Shared XMPP escrow contact",
        "description": "Both darkmerchant and shadow_vendor advertise the same XMPP contact dm-escrow@synthetic-xmpp.invalid for escrow coordination",
        "strength": "moderate",
        "evidence_class": "OBSERVED_FACT",
        "score_contribution": 10.0,
        "relationship_code": "REL-DM-SV-001",
        "details": {"jid": "dm-escrow@synthetic-xmpp.invalid", "channel": "xmpp", "match_type": "exact"},
    },
    {
        "code": "EVID-004",
        "kind": "stylometric_similarity",
        "title": "Stylometric similarity (79%)",
        "description": "Identical writing pattern 'terse numbered offers'; shared listing categories credential_dumps, card_data (Jaccard=0.67); shared language en (Jaccard=0.50); similar listing description style (trigram cosine=1.0)",
        "strength": "moderate",
        "evidence_class": "DERIVED_SIGNAL",
        "score_contribution": 7.0,
        "relationship_code": "REL-DM-SV-001",
        "details": {
            "similarity": 0.792,
            "features_compared": 4,
            "features_matched": 3.17,
            "features": [
                {"feature": "writing_pattern", "value": "terse numbered offers", "match": "exact"},
                {"feature": "listing_categories", "value": "credential_dumps, card_data", "jaccard": 0.67},
                {"feature": "languages", "value": "en", "jaccard": 0.50},
                {"feature": "description_style", "value": "credential dump listings", "trigram_cosine": 1.0}
            ]
        },
    },
    {
        "code": "EVID-005",
        "kind": "behavior_similarity",
        "title": "Behavioral similarity (56%)",
        "description": "Active hours overlap 100% (21:00-05:00 vs 21:30-05:30); matching product categories credential_dumps, card_data (Jaccard=0.67)",
        "strength": "moderate",
        "evidence_class": "DERIVED_SIGNAL",
        "score_contribution": 2.0,
        "relationship_code": "REL-DM-SV-001",
        "details": {
            "similarity": 0.556,
            "features_compared": 3,
            "features_matched": 1.67,
            "features": [
                {"feature": "active_hours", "value_a": "21:00-05:00", "value_b": "21:30-05:30", "overlap": 1.0},
                {"feature": "product_categories", "value": "credential_dumps, card_data", "jaccard": 0.67},
                {"feature": "hibernation_timing", "description": "shadow_vendor appeared 38d after darkmerchant went inactive"}
            ]
        },
    },
    {
        "code": "EVID-006",
        "kind": "wallet_match",
        "title": "Shared BTC consolidation address",
        "description": "launderpipe and crimson_ledger both use bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z",
        "strength": "strong",
        "evidence_class": "OBSERVED_FACT",
        "score_contribution": 25.0,
        "relationship_code": "REL-LP-CL-001",
        "details": {"address": "bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z", "chain": "btc"},
    },
    {
        "code": "EVID-007",
        "kind": "infrastructure_reuse",
        "title": "Shared TLS certificate fingerprint",
        "description": "Both quietsteel and iron_broker have infrastructure using the same TLS certificate (A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9), indicating shared hosting.",
        "strength": "strong",
        "evidence_class": "OBSERVED_FACT",
        "score_contribution": 15.0,
        "relationship_code": "REL-QS-IB-001",
        "details": {
            "fingerprint": "A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9",
            "match_type": "exact_fingerprint",
            "note": "Certificate fingerprint reuse is strong infrastructure evidence but not identity proof",
        },
    },
]

# ---------------------------------------------------------------------------
# Timeline events
# ---------------------------------------------------------------------------
TIMELINE_EVENTS: list[dict[str, Any]] = [
    # darkmerchant history
    {"kind": "appearance", "actor_code": "darkmerchant", "occurred_at": "2021-03-14", "title": "darkmerchant appears on Silk Harbor Market", "detail": "First listing observed — credential dumps category"},
    {"kind": "pgp_seen", "actor_code": "darkmerchant", "occurred_at": "2021-03-14", "title": "PGP key 9F2A4C81…A8F6 first advertised"},
    {"kind": "activity", "actor_code": "darkmerchant", "occurred_at": "2021-05-02", "title": "dark_merchant persona appears on CipherTalk Forum"},
    {"kind": "activity", "actor_code": "darkmerchant", "occurred_at": "2024-11-08", "title": "dm_supply persona appears on Nightfall Bazaar"},
    {"kind": "disappearance", "actor_code": "darkmerchant", "occurred_at": "2025-09-14", "title": "dm_supply persona goes inactive on Nightfall Bazaar"},
    # shadow_vendor history
    {"kind": "appearance", "actor_code": "shadow_vendor", "occurred_at": "2025-10-02", "title": "shadow_vendor appears on Nightfall Bazaar", "detail": "New vendor persona — weeks after darkmerchant paused"},
    {"kind": "pgp_seen", "actor_code": "shadow_vendor", "occurred_at": "2025-10-02", "title": "Same PGP key 9F2A4C81…A8F6 advertised by shadow_vendor"},
    {"kind": "wallet_associated", "actor_code": "shadow_vendor", "occurred_at": "2025-10-02", "title": "Same BTC payout address used by shadow_vendor"},
    {"kind": "activity", "actor_code": "shadow_vendor", "occurred_at": "2025-10-11", "title": "shadowvendor persona appears on CipherTalk Forum"},
    # Correlation events
    {"kind": "relationship_added", "actor_code": "darkmerchant", "occurred_at": "2026-08-28", "title": "POSSIBLY_SAME_AS relationship created (darkmerchant → shadow_vendor)", "detail": "Signals: PGP match + wallet match. RCS computed by confidence engine."},
    {"kind": "relationship_added", "actor_code": "launderpipe", "occurred_at": "2026-08-29", "title": "POSSIBLY_SAME_AS relationship created (launderpipe → crimson_ledger)", "detail": "Signals: wallet match only. Single-signal correlation."},
    {"kind": "relationship_added", "actor_code": "pharmakon", "occurred_at": "2026-08-26", "title": "POSSIBLY_SAME_AS relationship created (pharmakon → redsparrow)", "detail": "Weak signals. Rejected by analyst as false positive."},
    {"kind": "analyst_note", "actor_code": "pharmakon", "occurred_at": "2026-08-28", "title": "Analyst rejected pharmakon ↔ redsparrow relationship", "detail": "Shared XMPP is a false positive"},
]

ACTORS: list[dict[str, Any]] = [
    {
        "code": "darkmerchant",
        "display_name": "darkmerchant",
        "category": "stolen_data",
        "risk_level": "critical",
        "status": "tracked",
        "attribution_confidence": 84.0,
        "summary": "High-volume vendor of stolen credential sets and payment-card data. Operates across two marketplaces and a forum, reusing one PGP key and one payout wallet across all three.",
        "primary_source": "Silk Harbor Market",
        "first_seen": "2021-03-14",
        "last_seen": "2026-07-19",
        "last_scan_at": "2026-08-28T04:12:00",
        "attributes": {
            "languages": ["en", "ru"],
            "active_hours_utc": "21:00-05:00",
            "listing_categories": ["credential_dumps", "card_data", "fullz"],
            "post_style": "terse numbered offers",
            "summary_style": "credential dump listings with price tiers",
        },
        "personas": [
            P("darkmerchant", "Silk Harbor Market", primary=True, vendor_tier="gold",
              reputation="4.8/5 - 1204 sales", first_seen="2021-03-14", last_seen="2026-07-19",
              identifiers=[
                  I("handle", "darkmerchant"),
                  I("pgp_key", PGP_ALPHA, "vendor signing key", algorithm="RSA-4096"),
                  I("wallet", WALLET_ALPHA, "escrow payout address", chain="btc"),
                  I("onion_service", "sh7kqx2mfp4vbn3s.onion", "vendor shop mirror"),
                  I("jabber", "dm-escrow@synthetic-xmpp.invalid", "escrow support contact"),
              ]),
            P("dark_merchant", "CipherTalk Forum", platform_type="forum",
              reputation="senior member - 3891 posts", first_seen="2021-05-02", last_seen="2026-06-30",
              post_style="terse numbered offers",
              identifiers=[
                  I("handle", "dark_merchant"),
                  I("alias", "DM"),
                  I("pgp_key", PGP_ALPHA, "same key advertised on forum"),
                  I("email", "darkmerchant@synthetic-mail.invalid"),
              ]),
            P("dm_supply", "Nightfall Bazaar", status="inactive",
              reputation="4.6/5 - 218 sales", first_seen="2024-11-08", last_seen="2025-09-14",
              identifiers=[
                  I("handle", "dm_supply"),
                  I("wallet", WALLET_ALPHA, "reused payout address", chain="btc"),
              ]),
        ],
    },
    {
        "code": "shadow_vendor",
        "display_name": "shadow_vendor",
        "category": "stolen_data",
        "risk_level": "high",
        "status": "tracked",
        "attribution_confidence": 61.0,
        "summary": "Vendor persona that appeared weeks after darkmerchant's Silk Harbor listings paused. Advertises the same product mix and presents the same PGP fingerprint, which makes it a rebranding candidate rather than a confirmed identity.",
        "primary_source": "Nightfall Bazaar",
        "first_seen": "2025-10-02",
        "last_seen": "2026-08-21",
        "last_scan_at": "2026-08-28T04:19:00",
        "attributes": {
            "languages": ["en"],
            "active_hours_utc": "21:30-05:30",
            "listing_categories": ["credential_dumps", "card_data"],
            "post_style": "terse numbered offers",
            "summary_style": "credential dump listings with price tiers",
            "suspected_rebrand_of": "darkmerchant",
        },
        "personas": [
            P("shadow_vendor", "Nightfall Bazaar", primary=True, vendor_tier="silver",
              reputation="4.7/5 - 386 sales", first_seen="2025-10-02", last_seen="2026-08-21",
              identifiers=[
                  I("handle", "shadow_vendor"),
                  I("pgp_key", PGP_ALPHA, "identical fingerprint to darkmerchant", algorithm="RSA-4096"),
                  I("wallet", WALLET_ALPHA, "identical payout address", chain="btc"),
                  I("onion_service", "nf4wq9zt6ry2plx8.onion", "shop mirror"),
                  I("jabber", "dm-escrow@synthetic-xmpp.invalid", "same escrow support contact"),
              ]),
            P("shadowvendor", "CipherTalk Forum", platform_type="forum",
              reputation="member - 412 posts", first_seen="2025-10-11", last_seen="2026-08-18",
              post_style="terse numbered offers",
              identifiers=[
                  I("handle", "shadowvendor"),
                  I("alias", "SV"),
                  I("jabber", "shadowvendor@synthetic-xmpp.invalid"),
              ]),
        ],
    },
    {
        "code": "pharmakon",
        "display_name": "pharmakon",
        "category": "narcotics",
        "risk_level": "high",
        "status": "tracked",
        "attribution_confidence": 57.0,
        "summary": "Narcotics vendor with a stable single-marketplace footprint and a shared XMPP contact reused by an unrelated fraud persona.",
        "primary_source": "Silk Harbor Market",
        "first_seen": "2022-07-21",
        "last_seen": "2026-08-14",
        "last_scan_at": "2026-08-28T04:12:00",
        "attributes": {"languages": ["en", "de"], "shipping_origin": "EU (claimed)"},
        "personas": [
            P("pharmakon", "Silk Harbor Market", primary=True, vendor_tier="gold",
              reputation="4.9/5 - 2760 sales", first_seen="2022-07-21", last_seen="2026-08-14",
              identifiers=[
                  I("handle", "pharmakon"),
                  I("pgp_key", "3B71E90C58AD24F6712B08E5C4903DA7F1650B82", "vendor signing key"),
                  I("wallet", "bc1qz3x5c7v9b1n3m5q7w9e1r3t5y7u9i1o3p5a7s9", "payout", chain="btc"),
                  I("jabber", JABBER_SHARED, "support contact"),
              ]),
        ],
    },
    {
        "code": "quietsteel",
        "display_name": "quietsteel",
        "category": "weapons",
        "risk_level": "critical",
        "status": "tracked",
        "attribution_confidence": 73.0,
        "summary": "Arms-listing persona operating through a forum broker model rather than a marketplace storefront. Rotates onion mirrors frequently.",
        "primary_source": "CipherTalk Forum",
        "first_seen": "2023-01-09",
        "last_seen": "2026-08-25",
        "last_scan_at": "2026-08-27T21:40:00",
        "attributes": {"languages": ["en"], "broker_model": True, "mirror_rotation_days": 11},
        "personas": [
            P("quietsteel", "CipherTalk Forum", platform_type="forum", primary=True,
              reputation="trusted broker - 1077 posts", first_seen="2023-01-09", last_seen="2026-08-25",
              identifiers=[
                  I("handle", "quietsteel"),
                  I("pgp_key", "A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9", "broker key"),
                  I("onion_service", "qs2mv8kd5tf7nwl3.onion", "current mirror"),
                  I("onion_service", "qs9xb3rp7mk2vdc6.onion", "retired mirror", status="retired"),
              ]),
        ],
    },
    {
        "code": "launderpipe",
        "display_name": "launderpipe",
        "category": "money_laundering",
        "risk_level": "high",
        "status": "tracked",
        "attribution_confidence": 66.0,
        "summary": "Mixing and cash-out service advertised on a forum. Shares a consolidation wallet with crimson_ledger.",
        "primary_source": "CipherTalk Forum",
        "first_seen": "2022-02-18",
        "last_seen": "2026-08-09",
        "last_scan_at": "2026-08-29T03:02:00",
        "attributes": {"languages": ["en"], "advertised_fee": "7%", "chains": ["btc", "xmr"]},
        "personas": [
            P("launderpipe", "CipherTalk Forum", platform_type="forum", primary=True,
              reputation="verified service - 655 posts", first_seen="2022-02-18", last_seen="2026-08-09",
              identifiers=[
                  I("handle", "launderpipe"),
                  I("wallet", WALLET_LAUNDER, "consolidation address", chain="btc"),
                  I("wallet", "0x7a3f91c04e82b56d19af73c208e5b41d96f0a2c8", "bridge address", chain="eth"),
                  I("jabber", "launderpipe@synthetic-xmpp.invalid"),
              ]),
        ],
    },
    {
        "code": "crimson_ledger",
        "display_name": "crimson_ledger",
        "category": "money_laundering",
        "risk_level": "moderate",
        "status": "tracked",
        "attribution_confidence": 48.0,
        "summary": "Bookkeeping-for-hire persona. Wallet overlap with launderpipe is the only strong signal; handles and writing style differ markedly.",
        "primary_source": "Hollowpaste",
        "first_seen": "2024-04-30",
        "last_seen": "2026-07-02",
        "last_scan_at": "2026-08-26T11:05:00",
        "attributes": {"languages": ["en", "es"], "note": "handle similarity to launderpipe is absent"},
        "personas": [
            P("crimson_ledger", "Hollowpaste", platform_type="paste_site", primary=True,
              first_seen="2024-04-30", last_seen="2026-07-02",
              identifiers=[
                  I("handle", "crimson_ledger"),
                  I("wallet", WALLET_LAUNDER, "same consolidation address as launderpipe", chain="btc"),
                  I("email", "crimson.ledger@synthetic-mail.invalid"),
              ]),
        ],
    },
    {
        "code": "ghostloader",
        "display_name": "ghostloader",
        "category": "hacking_services",
        "risk_level": "moderate",
        "status": "tracked",
        "attribution_confidence": 52.0,
        "summary": "Loader and initial-access broker. Advertises on a forum with a clearnet-registered support domain visible in TLS metadata.",
        "primary_source": "Transparency Log Mirror",
        "first_seen": "2023-09-12",
        "last_seen": "2026-08-27",
        "last_scan_at": "2026-08-29T02:30:00",
        "attributes": {"languages": ["en"], "tls_san_leak": True},
        "personas": [
            P("ghostloader", "CipherTalk Forum", platform_type="forum", primary=True,
              reputation="member - 289 posts", first_seen="2023-09-12", last_seen="2026-08-27",
              identifiers=[
                  I("handle", "ghostloader"),
                  I("domain", "ghostloader-support.invalid", "SAN entry on shop certificate"),
                  I("onion_service", "gl5tk8wq2ny7bmv4.onion", "panel"),
                  I("pgp_key", "C71D4A2E90B58F6314D7C82A5E093B41F6250D8A", "contact key"),
              ]),
        ],
    },
    {
        "code": "redsparrow",
        "display_name": "redsparrow",
        "category": "fraud",
        "risk_level": "moderate",
        "status": "tracked",
        "attribution_confidence": 39.0,
        "summary": "Refund-fraud tutorial seller. Shares an XMPP contact with pharmakon, which is a weak signal on its own and is retained as a documented false-positive candidate.",
        "primary_source": "Hollowpaste",
        "first_seen": "2025-02-14",
        "last_seen": "2026-05-28",
        "last_scan_at": "2026-08-26T11:05:00",
        "attributes": {"languages": ["en"], "false_positive_candidate": True},
        "personas": [
            P("redsparrow", "Hollowpaste", platform_type="paste_site", primary=True,
              first_seen="2025-02-14", last_seen="2026-05-28",
              identifiers=[
                  I("handle", "redsparrow"),
                  I("jabber", JABBER_SHARED, "shared support contact - shop front reseller"),
                  I("alias", "r3dsparrow"),
              ]),
        ],
    },
    {
        "code": "nullbyte_9",
        "display_name": "nullbyte_9",
        "category": "hacking_services",
        "risk_level": "low",
        "status": "dormant",
        "attribution_confidence": 21.0,
        "summary": "Low-activity exploit-request persona. Insufficient corpus for stylometric comparison; retained to show reliability gating.",
        "primary_source": "CipherTalk Forum",
        "first_seen": "2026-01-06",
        "last_seen": "2026-03-19",
        "last_scan_at": "2026-08-27T21:40:00",
        "attributes": {"languages": ["en"], "corpus_words": 214, "stylometry_gated": True},
        "personas": [
            P("nullbyte_9", "CipherTalk Forum", platform_type="forum", primary=True,
              status="inactive", reputation="new member - 17 posts",
              first_seen="2026-01-06", last_seen="2026-03-19",
              identifiers=[I("handle", "nullbyte_9"), I("alias", "nullbyte")]),
        ],
    },
    {
        "code": "bazaar_ops",
        "display_name": "bazaar_ops",
        "category": "other",
        "risk_level": "low",
        "status": "archived",
        "attribution_confidence": 12.0,
        "summary": "Marketplace administration account, archived after the synthetic marketplace closed. Kept to exercise archived-state filtering.",
        "primary_source": "Nightfall Bazaar",
        "first_seen": "2024-08-01",
        "last_seen": "2025-12-30",
        "last_scan_at": "2026-08-28T04:19:00",
        "attributes": {"languages": ["en"], "role": "marketplace_staff"},
        "personas": [
            P("bazaar_ops", "Nightfall Bazaar", primary=True, status="abandoned",
              first_seen="2024-08-01", last_seen="2025-12-30",
              identifiers=[I("handle", "bazaar_ops"), I("email", "ops@synthetic-mail.invalid")]),
        ],
    },
    {
        "code": "veil_courier",
        "display_name": "veil_courier",
        "category": "narcotics",
        "risk_level": "high",
        "status": "tracked",
        "attribution_confidence": 44.0,
        "summary": "Reshipping persona active on two marketplaces with distinct keys per platform, illustrating an actor who does not reuse identifiers.",
        "primary_source": "Nightfall Bazaar",
        "first_seen": "2023-06-25",
        "last_seen": "2026-08-11",
        "last_scan_at": "2026-08-28T04:19:00",
        "attributes": {"languages": ["en", "nl"], "opsec_note": "no identifier reuse across platforms"},
        "personas": [
            P("veil_courier", "Nightfall Bazaar", primary=True, reputation="4.4/5 - 512 sales",
              first_seen="2023-06-25", last_seen="2026-08-11",
              identifiers=[
                  I("handle", "veil_courier"),
                  I("pgp_key", "E82B0D5C74A19F3620C58BE4D07A93F156B4C20D", "bazaar key"),
              ]),
            P("vc_dispatch", "Silk Harbor Market", reputation="4.2/5 - 143 sales",
              first_seen="2024-02-03", last_seen="2026-04-27",
              identifiers=[
                  I("handle", "vc_dispatch"),
                  I("pgp_key", "5D93F71A28C4B06E852F1DC9A430E7B85C216F04", "separate harbour key"),
              ]),
        ],
    },
    {
        "code": "terra_fund",
        "display_name": "terra_fund",
        "category": "terror_financing",
        "risk_level": "critical",
        "status": "tracked",
        "attribution_confidence": 69.0,
        "summary": "Solicitation persona requesting donations through rotating wallets. Highest-priority category in the synthetic set.",
        "primary_source": "Hollowpaste",
        "first_seen": "2024-10-17",
        "last_seen": "2026-08-29",
        "last_scan_at": "2026-08-29T03:02:00",
        "attributes": {"languages": ["en", "ar"], "wallet_rotation_days": 6, "priority": "P1"},
        "personas": [
            P("terra_fund", "Hollowpaste", platform_type="paste_site", primary=True,
              first_seen="2024-10-17", last_seen="2026-08-29",
              identifiers=[
                  I("handle", "terra_fund"),
                  I("wallet", "bc1q4t6y8u0i2o4p6a8s0d2f4g6h8j0k2l4z6x8c0", "rotation slot 14", chain="btc"),
                  I("wallet", "0x1c5e93a72f04b81d6a39cf25e08b74d61af93027", "rotation slot 15", chain="eth"),
                  I("onion_service", "tf6nq3wz9mk5bvx2.onion", "appeal page"),
              ]),
        ],
    },
    {
        "code": "iron_broker",
        "display_name": "iron_broker",
        "category": "weapons",
        "risk_level": "moderate",
        "status": "dormant",
        "attribution_confidence": 48.0,
        "summary": "Intermittent weapons-parts broker. Only clearnet-adjacent indicator is a certificate issuer reused by quietsteel's retired mirror.",
        "primary_source": "Transparency Log Mirror",
        "first_seen": "2022-11-11",
        "last_seen": "2025-08-20",
        "last_scan_at": "2026-08-29T02:30:00",
        "attributes": {"languages": ["en"], "shared_cert_issuer": "Synthetic Interim CA R3"},
        "personas": [
            P("iron_broker", "CipherTalk Forum", platform_type="forum", primary=True,
              status="inactive", reputation="member - 96 posts",
              first_seen="2022-11-11", last_seen="2025-08-20",
              identifiers=[
                  I("handle", "iron_broker"),
                  I("domain", "iron-broker-parts.invalid", "certificate subject CN"),
                  I("pgp_key", "A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9", "same cert fingerprint as quietsteel", algorithm="RSA-2048"),
              ]),
        ],
    },
]
