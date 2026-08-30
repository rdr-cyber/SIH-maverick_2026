# DEMO — Script & Offline Guarantee (Phase 1 design)

## 1. The promise

> The five-minute SIH demo runs 100% offline on synthetic data. No network, no Tor,
> no live services, no external APIs. One command brings up the whole stack.

```
docker compose --profile demo pull      # once, on a networked dev machine (image fetch only)
docker compose --profile demo up -d     # everything on local volumes
open http://localhost:8000/docs         # API (also at :80 for the SPA)
```

For an even lighter path (no Docker on the judging laptop), Phase 14 ships a
`start_local.ps1`/`start_local.sh` bootstrap that runs Postgres/Neo4j/Redis only if present
and otherwise degrades to an **embedded in-memory mode** for the graph demo — still backed by
the real engine code paths.

## 2. Synthetic ecosystem (Phase 3 generator — deterministic)

| Entity | Target size | Purpose |
|--------|-------------|---------|
| Actor personas | 8–10 | Alpha (flagship), Beta (false positive), Gamma (unrelated), Delta (copycat), plus background |
| Handles | ≥ 50 | within-platform and migration variants |
| PGP keys | ≥ 20 | KEY_ALPHA shared across Alpha's personas; others unique |
| Wallet IDs | ≥ 30 | WALLET_ALPHA shared; decoy wallets shared on shared hosting |
| Domains | ≥ 30 | infra clusters; registration-date proximity traps |
| Posts | ≥ 100 | corpus for stylometry (≥ 40 for flagship personas) |
| Timeline events | ≥ 500 | full chronological richness |
| Infrastructure records | ≥ 40 | certs/DNS/ASN/SES records |
| Migration events | ≥ 6 | Alpha's Marketplace A → B story + decoys |

Seeded RNG → byte-identical dataset on every run; generator outputs a
`dataset_manifest.json` (checksums) for test assertions.

### Flagship hidden relationship (not hard-coded anywhere in UI/API)
Personas: ALPHA-1 (`shadow_vendor`: Marketplace A + Forum X) and ALPHA-2
(`darkmerchant`: Marketplace B + Forum Y). Shared: PGP `KEY_ALPHA`, wallet `WALLET_ALPHA`,
similar writing (corpus designed with shared phrase `escrow only, no FE`, similar sentence
length distribution) and similar posting schedule (evening UTC, Tue/Thu/Sun). Expected
engine result: RCS ≥ 70 (**High**), band high, status pending, explanation names exactly
the PGP/wallet/stylometry/behavior factors.

### False positives (present and NOT incorrectly merged)
- **Beta:** handle `shadow_vend0r` (misspelled lookalike) — different PGP, different wallet,
  different writing profile and schedule. Expected RCS < 50 (**Low**).
- **Delta (copycat):** deliberately mimics shadow_vendor's phrasing — high stylometry but no
  identity anchors. Expected RCS ≤ Moderate (stylometry alone can't reach High).
- **Shared-hosting pair:** unrelated domains on one synthetic shared host — infra signal alone
  ≤ Moderate.

## 3. The five-minute story (the demo script)

| Time | On screen | Narrator line |
|------|-----------|---------------|
| 0:00 | Login (demo analyst) | "Authorized analyst access, audit-logged from here." |
| 0:15 | Command Center | Tracked actors, active investigations, new intelligence ticking up, pending high-confidence relationship, alerts. |
| 0:40 | Search → `shadow_vendor` | "Actor Alpha — needled out of 50+ handles, 20 PGP keys, 30 wallets." |
| 1:00 | Actor Profile | Handles, PGP, wallet, platforms, timeline heads-up: went quiet on Marketplace A in 2025-11. |
| 1:30 | Timeline | "Alpha disappears … a new persona `darkmerchant` appears on Marketplace B in 2026-01." |
| 1:50 | **RUN INVESTIGATION** | Pipeline animates: ingest → normalize → extract → correlate → stylometry → behavior → evidence → confidence. |
| 2:30 | Graph | The `POSSIBLY_SAME_AS` edge renders — **High confidence (72)**. Click it. |
| 2:50 | Evidence panel (WHY) | "Same PGP KEY_ALPHA (+30), same wallet WALLET_ALPHA (+25), writing similarity 0.91 (+10), behavior similarity (+5)." |
| 3:15 | False-positive review | "But watch this — Beta's `shadow_vend0r` scores 22. Weak. Not merged." (show both, side by side) |
| 3:45 | Analyst review | Senior analyst **accepts** the relationship with a note; audit event appears. |
| 4:10 | Reports | Generate PDF + CSV + JSON export in one click; download opens. |
| 4:40 | Autonomous monitor | "And the scheduler keeps watching — new artifacts, new identifiers, alerts" — next beat tick visible. |
| 5:00 | Q&A | Architecture board, ethics board, security board. |

## 4. RUN INVESTIGATION contract (Phase 14)

`POST /investigations/:code/run` executes the documented 11 steps atomically per scan batch:

1. Load new intelligence (synthetic source connector, seeded batch B+1)
2. Extract entities (handles/pgp/wallets/domains/certs/infra)
3. Normalize (canonical keys)
4. Correlate (candidate personas in graph neighborhood)
5. Update graph (nodes + `POSSIBLY_SAME_AS` edges, status pending)
6. Run stylometry (per-handle corpora)
7. Run behavior analysis (histograms + migration narrative)
8. Generate evidence rows (with score contributions + explanations)
9. Calculate confidence (weights → bands) and update relationships
10. Update timeline events (appearance/migration/relationship milestones)
11. Return investigation result with review-ready relationship list

Progress streams over SSE (`scan.stream`); Command Center and the Actor view update live.

## 5. Demo-mode guardrails

- The `demo` profile sets `APP_ENV=demo`; ingest connector asserts `access_method ∈
  {synthetic, authorized, public}` and refuses anything else.
- Network egress from the backend in demo mode is **blocked** (outbound firewall rule in the
  compose network or `--network none` on a dedicated second interface) — proving offline.
- Demo accounts: `demo_analyst` (analyst) and `demo_admin` (admin) created at first boot
  from env vars; no real credentials anywhere.

## 6. Backup plans

- **B1 (no Docker):** `start_local` embedded-mode boots the full engine with in-memory stores
  (SQLite + remote-less graph stub backed by the same sync code), same demo.
- **B2 (no display):** API-first demo via `/docs` + curl runs of RUN INVESTIGATION.
- **B3 (no time):** pre-rendered graph screenshots + static evidence exports from the dataset
  manifest, if the live demo dies; JSON report exports are already generated.

## 7. What judges should remember

"Connect the clues. Explain the evidence. Strengthen attribution." — the platform correlates
identities across marketplaces, explains *why* with evidence chains, and never overstates:
**hypothesis, not verdict** — human review on every inference.
