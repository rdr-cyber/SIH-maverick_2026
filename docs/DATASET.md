# SYNTHETIC DATASET — Structure (Phase 1 design)

Generator: `backend/app/data_generation/` (Phase 3). Deterministic — same seed → same bytes.

## 1. Guaranteed volume targets

| Artifact | Target | Floor |
|----------|--------|-------|
| Actor personas | 9 | 6 |
| Handles | 60 | 50 |
| PGP keys | 24 | 20 |
| Wallets | 36 | 30 |
| Domains | 40 | 30 |
| Infrastructure records (IP/ASN/SES/netblock) | 48 | 40 |
| TLS certificates | 30 | 25 |
| Posts (forums + marketplaces) | 140 | 100 |
| Timeline events | 800 | 500 |
| Observational records (raw) | 900 | — |
| Sources | 10 | 8 |
| Marketplace/Forum platforms | 4 | 4 |
| Migration events | 8 | 6 |
| False-positive scenarios | 3 | 3 |

## 2. Ecosystem layout (fictional)

- **Platforms:** Marketplace A (`Marketplace A`, codename "A" operating), Marketplace B
  (operating), Forum X (operating), Forum Y (operating).
- **Sources:** `synthetic-marketplace-a`, `synthetic-marketplace-b`, `synthetic-forum-x`,
  `synthetic-forum-y`, `synthetic-dns-archive`, `synthetic-cert-archive`,
  `synthetic-blockchain-indexer`, `synthetic-pgp-keyserver`, `synthetic-paste-site`,
  `synthetic-shared-host`. All `access_method = 'synthetic'`.

## 3. Persona blueprint table

| Persona | Handles (platform) | PGP | Wallet | Style group | Behavior group | Role in demo |
|---------|--------------------|-----|--------|-------------|----------------|--------------|
| ALPHA-1 (`shadow_vendor`) | `shadow_vendor` (A), `shadow_vendor` (X) | KEY_ALPHA | WALLET_ALPHA | S1 | B1 | flagship: disappears 2025-11 |
| ALPHA-2 (`darkmerchant`) | `darkmerchant` (B) → also Forum Y | KEY_ALPHA | WALLET_ALPHA | S1 | B1 | flagship: appears 2026-01 |
| BETA | `shadow_vend0r` (B), `v3nd0r_shad0w` (Y) | KEY_BETA | WALLET_BETA | S2 | B2 | **FP: lookalike handle** |
| GAMMA | `grey_market_ghost` (A), `greyfish` (X) | KEY_GAMMA | WALLET_GAMMA | S3 | B3 | unrelated; shares marketplace A |
| DELTA | `shadowcopier` (B) | KEY_DELTA | WALLET_DELTA | S1 (copycat) | B4 | **FP: copycat style** |
| EPSILON | `epsilon_1922`, `eps_dev` (f) | KEY_EPSILON | WALLET_EPSILON | S4 | B5 | background |
| … | 6–9 total personas for graph depth | |

## 4. Infrastructure clusters (synthetic TEST-NET ranges only)

- `203.0.113.0/24` (TEST-NET-3), `198.51.100.0/24` (TEST-NET-2), `192.0.2.0/24` (TEST-NET-1) —
  documented safe ranges.
- **Cluster EX-1 (Alpha):** domains `alpha-store-*.test` → SES + cert issuer CN "shared-ca"
  shared *only* by Alpha's two eras (timing separated) — infrastructure reuse signal.
- **Cluster EX-2 (Beta):** a domain on the *same shared host* as an unrelated persona — the
  shared-hosting false positive.
- **Cluster EX-3 (decoy):** registration-date proximity of two unrelated domains in one week —
  temporal trap.

## 5. Content corpus (stylometry fuel)

- 4 style families (S1…S4) with distinct char/word n-gram fingerprints.
- S1 flagship signature phrases: `escrow only, no FE`, `shipping via drop`, `no FE, no escrow`,
  distinctive punctuation (`!?` rare, `..` frequent), mean sentence length ~11 words.
- DELTA is seeded to borrow S1 phrases but with different function-word rates and shorter
  sentences (the distinguishing features the analyzer must find).
- 140 posts: ~45 for Alpha across eras, ~25 Beta, ~20 Gamma, ~15 Delta, remainder background.

## 6. Behavior blueprint (B1…B5)

- **B1:** posts Tue/Thu/Sun evenings (18–22 UTC), bursts of 2–3, hibernation Nov 2025–Jan 2026,
  then resumes on Marketplace B with same schedule.
- **B2 (Beta):** random daytime hours, 7-day week spread, no hibernation.
- **B4 (Delta):** mimics B1's *times* but high-frequency bursts (the distinguishing feature).
- Migration events recorded as timeline + observation kinds (`persona_migration`).

## 7. Wallet/PGP ledger semantics

- WALLET_ALPHA: transfers flagged on the synthetic indexer during both eras
  (`wallet_transfer` observations with timestamps) — the provenance trail the evidence engine
  cites. Decoy wallets for B2/Gamma on shared hosting never co-mingle with ALPHA.
- KEY_ALPHA: fingerprints in both eras; PGP `user_id` strings deliberately different for
  era-2 to prove fingerprint-only linking prevails.

## 8. Generator CLI (Phase 3)

```
python -m app.data_generation.seed --seed 20260726 --out data/seed --format json
   -> data/seed/{artifacts,posts,timeline,sources}.json + dataset_manifest.json (checksums)
python -m app.data_generation.seed --help
```

Loader: `app/ingestion/synthetic_loader.py` replays these files through the *real* ingestion
pipeline (validation → dedup → normalization → extraction → correlation → graph → evidence →
confidence → timeline → alerts). Demo `RUN INVESTIGATION` pulls batch B+1 from a prepared
`data/seed/batch_b1/` folder — simulated "new intelligence".

## 9. Constraints

- All domains end in `.test`; all IPs inside TEST-NET ranges; all wallet chains synthetic;
  all content fictional (no real handles/names/addresses anywhere).
- Manifest checksums let tests assert dataset stability across runs/machines.
