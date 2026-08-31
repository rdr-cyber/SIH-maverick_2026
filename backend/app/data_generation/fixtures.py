"""Synthetic ingestion fixtures for SHADOWGRAPH.

Every fixture is FABRICATED for demonstration. No real criminal data.
Fixtures are deterministic and idempotent — re-running produces the same results.

Each fixture contains enough evidence to demonstrate the ingestion pipeline:
  extraction → normalization → resolution → relationship creation → correlation → confidence
"""
from __future__ import annotations

from app.services.ingestion import RawObservation


# ---------------------------------------------------------------------------
# Fixture 1: DarkMerchant — shared PGP, wallet, and XMPP identifiers
# ---------------------------------------------------------------------------

FIXTURE_DM_MARKETPLACE = RawObservation(
    source_name="Nightfall Bazaar",
    source_type="marketplace",
    content_type="listing",
    external_id="NF-2025-10-02-001",
    retrieved_at="2025-10-02T14:30:00",
    published_at="2025-10-02T14:30:00",
    content=(
        "New vendor: shadow_vendor\n"
        "PGP: 9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6\n"
        "BTC payout: bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx\n"
        "Contact: dm-escrow@synthetic-xmpp.invalid\n"
        "Categories: credential_dumps, card_data\n"
        "Shipping: worldwide\n"
        "Tor mirror: nf4wq9zt6ry2plx8.onion"
    ),
    metadata={
        "vendor_tier": "silver",
        "initial_rating": 4.7,
        "listing_count": 12,
    },
    identifiers=[
        {"kind": "handle", "value": "shadow_vendor", "label": "vendor handle"},
        {"kind": "pgp_key", "value": "9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6", "label": "vendor signing key"},
        {"kind": "wallet", "value": "bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx", "label": "escrow payout"},
        {"kind": "jabber", "value": "dm-escrow@synthetic-xmpp.invalid", "label": "escrow contact"},
        {"kind": "onion_service", "value": "nf4wq9zt6ry2plx8.onion", "label": "shop mirror"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 2: DarkMerchant forum activity (different platform, same identifiers)
# ---------------------------------------------------------------------------

FIXTURE_DM_FORUM = RawObservation(
    source_name="CipherTalk Forum",
    source_type="forum",
    content_type="post",
    external_id="CT-2025-10-11-042",
    retrieved_at="2025-10-11T09:15:00",
    published_at="2025-10-11T09:15:00",
    content=(
        "[ANNOUNCE] shadowvendor here\n"
        "Previously active on Nightfall Bazaar as shadow_vendor.\n"
        "Same PGP key for verification: 9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6\n"
        "Escrow contact: dm-escrow@synthetic-xmpp.invalid\n"
        "BTC address for direct deals: bc1qk7m3v9x2p4qwe8r5t6y7u8i9o0asdfghjklzx\n"
        "Specializing in credential dumps and card data.\n"
        "All listings priced in BTC tiers."
    ),
    metadata={
        "post_type": "announcement",
        "thread_id": "shadowvendor-intro",
    },
    identifiers=[
        {"kind": "handle", "value": "shadowvendor", "label": "forum handle"},
        {"kind": "alias", "value": "SV", "label": "short alias"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 3: LaunderPipe wallet overlap with crimson_ledger
# ---------------------------------------------------------------------------

FIXTURE_LAUNDERPIPE = RawObservation(
    source_name="CipherTalk Forum",
    source_type="forum",
    content_type="post",
    external_id="CT-2026-08-09-187",
    retrieved_at="2026-08-09T16:45:00",
    published_at="2026-08-09T16:45:00",
    content=(
        "[SERVICE] launderpipe mixing service\n"
        "Fee: 7% on BTC and XMR\n"
        "BTC consolidation: bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z\n"
        "ETH bridge: 0x7a3f91c04e82b56d19af73c208e5b41d96f0a2c8\n"
        "Contact: launderpipe@synthetic-xmpp.invalid\n"
        "Supports: btc, xmr\n"
        "Minimum: 0.01 BTC"
    ),
    metadata={
        "service_type": "mixing",
        "fee_percentage": 7,
    },
    identifiers=[
        {"kind": "handle", "value": "launderpipe", "label": "service handle"},
        {"kind": "wallet", "value": "bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z", "label": "consolidation address"},
        {"kind": "wallet", "value": "0x7a3f91c04e82b56d19af73c208e5b41d96f0a2c8", "label": "ETH bridge"},
        {"kind": "jabber", "value": "launderpipe@synthetic-xmpp.invalid", "label": "support contact"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 4: crimson_ledger paste with same wallet
# ---------------------------------------------------------------------------

FIXTURE_CRIMSON_LEDGER = RawObservation(
    source_name="Hollowpaste",
    source_type="paste_site",
    content_type="paste",
    external_id="HP-2026-08-09-342",
    retrieved_at="2026-08-09T18:00:00",
    published_at="2026-08-09T17:30:00",
    content=(
        "crimson_ledger bookkeeping services\n"
        "Accepting BTC for invoice processing.\n"
        "Payment address: bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z\n"
        "Contact: crimson.ledger@synthetic-mail.invalid\n"
        "Languages: English, Spanish\n"
        "Specializing in transaction obfuscation"
    ),
    metadata={
        "paste_type": "service_ad",
        "views": 234,
    },
    identifiers=[
        {"kind": "handle", "value": "crimson_ledger", "label": "service handle"},
        {"kind": "wallet", "value": "bc1q0w9e8r7t6y5u4i3o2p1a9s8d7f6g5h4j3k2l1z", "label": "payment address"},
        {"kind": "email", "value": "crimson.ledger@synthetic-mail.invalid", "label": "contact email"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 5: Pharmakon with shared XMPP
# ---------------------------------------------------------------------------

FIXTURE_PHARMAKON = RawObservation(
    source_name="Silk Harbor Market",
    source_type="marketplace",
    content_type="listing",
    external_id="SH-2026-08-14-089",
    retrieved_at="2026-08-14T11:20:00",
    published_at="2026-08-14T11:20:00",
    content=(
        "pharmakon listing: premium pharmaceutical grade\n"
        "PGP: 3B71E90C58AD24F6712B08E5C4903DA7F1650B82\n"
        "BTC payout: bc1qz3x5c7v9b1n3m5q7w9e1r3t5y7u9i1o3p5a7s9\n"
        "Support: obsidian.ops@synthetic-xmpp.invalid\n"
        "Shipping: EU (claimed)\n"
        "Escrow: mandatory\n"
        "Languages: en, de"
    ),
    metadata={
        "vendor_tier": "gold",
        "rating": 4.9,
        "sales": 2760,
    },
    identifiers=[
        {"kind": "handle", "value": "pharmakon", "label": "vendor handle"},
        {"kind": "pgp_key", "value": "3B71E90C58AD24F6712B08E5C4903DA7F1650B82", "label": "vendor signing key"},
        {"kind": "wallet", "value": "bc1qz3x5c7v9b1n3m5q7w9e1r3t5y7u9i1o3p5a7s9", "label": "payout address"},
        {"kind": "jabber", "value": "obsidian.ops@synthetic-xmpp.invalid", "label": "support contact"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 6: redsparrow with shared XMPP (false positive scenario)
# ---------------------------------------------------------------------------

FIXTURE_REDSPARROW = RawObservation(
    source_name="Hollowpaste",
    source_type="paste_site",
    content_type="paste",
    external_id="HP-2026-05-28-156",
    retrieved_at="2026-05-28T08:15:00",
    published_at="2026-05-28T08:00:00",
    content=(
        "redsparrow refund fraud tutorial\n"
        "Step-by-step guide available.\n"
        "Contact: obsidian.ops@synthetic-xmpp.invalid\n"
        "Languages: en\n"
        "Price: 0.05 BTC\n"
        "Payment: BTC only"
    ),
    metadata={
        "paste_type": "tutorial",
        "views": 892,
    },
    identifiers=[
        {"kind": "handle", "value": "redsparrow", "label": "tutorial author"},
        {"kind": "jabber", "value": "obsidian.ops@synthetic-xmpp.invalid", "label": "support contact"},
        {"kind": "alias", "value": "r3dsparrow", "label": "alternate handle"},
    ],
)

# ---------------------------------------------------------------------------
# Fixture 7: Ghostloader domain + certificate metadata
# ---------------------------------------------------------------------------

FIXTURE_GHOSTLOADER = RawObservation(
    source_name="Transparency Log Mirror",
    source_type="certificate_archive",
    content_type="certificate_observation",
    external_id="TL-2026-08-27-012",
    retrieved_at="2026-08-27T21:30:00",
    published_at="2026-08-27T21:30:00",
    content=(
        "Certificate observation:\n"
        "Subject CN: ghostloader-support.invalid\n"
        "Issuer: Synthetic Interim CA R3\n"
        "SAN: ghostloader-support.invalid, gl5tk8wq2ny7bmv4.onion\n"
        "Valid: 2026-03-01 to 2027-03-01\n"
        "Fingerprint: C71D4A2E90B58F6314D7C82A5E093B41F6250D8A"
    ),
    metadata={
        "cert_issuer": "Synthetic Interim CA R3",
        "valid_from": "2026-03-01",
        "valid_to": "2027-03-01",
    },
    identifiers=[
        {"kind": "domain", "value": "ghostloader-support.invalid", "label": "support domain from SAN"},
        {"kind": "onion_service", "value": "gl5tk8wq2ny7bmv4.onion", "label": "panel from SAN"},
        {"kind": "pgp_key", "value": "C71D4A2E90B58F6314D7C82A5E093B41F6250D8A", "label": "contact key from cert"},
    ],
)


# ---------------------------------------------------------------------------
# Fixture 8: New discovery — quietsteel and iron_broker share a certificate
# ---------------------------------------------------------------------------

FIXTURE_QUIETSTEEL_CERT = RawObservation(
    source_name="Transparency Log Mirror",
    source_type="certificate_archive",
    content_type="certificate_observation",
    external_id="TL-2026-08-29-045",
    retrieved_at="2026-08-29T03:15:00",
    published_at="2026-08-29T03:15:00",
    content=(
        "Certificate observation for quietsteel shop mirror:\n"
        "Subject CN: qs2mv8kd5tf7nwl3.invalid\n"
        "Issuer: Synthetic Interim CA R3\n"
        "SAN: qs2mv8kd5tf7nwl3.invalid\n"
        "Valid: 2026-01-01 to 2027-01-01\n"
        "Fingerprint: A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9\n"
        "Note: Same issuer as iron-broker-parts.invalid"
    ),
    metadata={
        "cert_issuer": "Synthetic Interim CA R3",
        "valid_from": "2026-01-01",
        "valid_to": "2027-01-01",
        "shared_issuer_with": "iron-broker-parts.invalid",
    },
    identifiers=[
        {"kind": "domain", "value": "qs2mv8kd5tf7nwl3.invalid", "label": "shop mirror domain from SAN"},
        {"kind": "pgp_key", "value": "A0C4D82F61B935E7204C8AF3D91E56B7480CA2E9", "label": "cert fingerprint"},
    ],
)


# ---------------------------------------------------------------------------
# All fixtures
# ---------------------------------------------------------------------------

ALL_FIXTURES: list[RawObservation] = [
    FIXTURE_DM_MARKETPLACE,
    FIXTURE_DM_FORUM,
    FIXTURE_LAUNDERPIPE,
    FIXTURE_CRIMSON_LEDGER,
    FIXTURE_PHARMAKON,
    FIXTURE_REDSPARROW,
    FIXTURE_GHOSTLOADER,
    FIXTURE_QUIETSTEEL_CERT,
]

# Fixtures that demonstrate the DarkMerchant identity correlation
DARKMERCHANT_FIXTURES: list[RawObservation] = [
    FIXTURE_DM_MARKETPLACE,
    FIXTURE_DM_FORUM,
]

# Fixtures that demonstrate the LaunderPipe wallet overlap
LAUNDERPIPE_FIXTURES: list[RawObservation] = [
    FIXTURE_LAUNDERPIPE,
    FIXTURE_CRIMSON_LEDGER,
]

# Fixtures that demonstrate the Pharmakon ↔ Redsparrow false positive
PHARMAKON_FIXTURES: list[RawObservation] = [
    FIXTURE_PHARMAKON,
    FIXTURE_REDSPARROW,
]
