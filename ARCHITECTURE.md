# ARCHITECTURE

## 1. Design Principles

1. **Explainability over accuracy theatre.** Every inferred relationship carries evidence IDs,
   scoring factors, and a human-readable explanation. No black-box "AI found it".
2. **Provenance everywhere.** Every row in PostgreSQL and every edge in Neo4j retains source,
   timestamp, first/last seen, and audit trail.
3. **Synthetic-first, offline-by-default.** The whole product runs against a deterministic
   synthetic ecosystem. No runtime dependency on the live network, Tor, or real systems.
4. **Human-in-the-loop.** Inferences are hypotheses until an analyst accepts, rejects, or marks
   them uncertain. Analyst actions are audit-logged.
5. **PostgreSQL is the system of record; Neo4j is the correlation index.**
   Relational facts, provenance and audit live in Postgres. The graph materializes correlated
   views of those facts for traversal and visualization. They are kept consistent by the
   **graph synchronizer**.

---

## 2. System Context

```
                     DATA SOURCES (synthetic / authorized / public metadata)
                                      │
                                      ▼
                            ┌───────────────────┐
                            │  INGESTION ENGINE │   connectors, dedup, validation
                            └─────────┬─────────┘
                                      ▼
                            ┌───────────────────┐
                            │   NORMALIZATION   │   canonical forms, id normalization
                            └─────────┬─────────┘
                                      ▼
                            ┌───────────────────┐
                            │ ENTITY EXTRACTION │   handles, wallets, PGP, domains, infra
                            └─────────┬─────────┘
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
   INFRASTRUCTURE               IDENTITY                NLP / AI ANALYSIS
   INTELLIGENCE                RESOLUTION              (stylometry, behavior)
   (DNS/TLS/ASN/domains)    (dedup & resolution)       (feature extraction)
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      ▼
                            ┌───────────────────┐
                            │ CORRELATION ENGINE│   multi-signal scoring
                            └─────────┬─────────┘
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                   POSTGRESQL       NEO4J       REDIS
                   (facts,          (graph,      (queues,
                    evidence,       relationships,  cache,
                    audit)           sync)         scan state)
                         └────────────┼────────────┘
                                      ▼
                            ┌───────────────────┐
                            │  EVIDENCE ENGINE  │    provenance, strength, contribution
                            └─────────┬─────────┘
                                      ▼
                            ┌───────────────────┐
                            │ CONFIDENCE ENGINE │    configurable weights → RCS
                            └─────────┬─────────┘
                                      ▼
                           INVESTIGATOR UI (React)
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           Graph      Timeline        Reports
         (Cytoscape)  (chronological)  (PDF/CSV/JSON)
```

---

## 3. Component Responsibilities

### 3.1 Ingestion Engine (`backend/app/ingestion`)
- **Source connectors**: `SyntheticSourceConnector` (the only connector shipped), plus an
  interface (`SourceConnector` protocol) so authorized connectors can be added later.
- **Validation**: Pydantic models per artifact type (Post, PGPKey, WalletTx, DomainRecord, …).
  Rejects malformed records with structured errors into `ScanJob.errors`.
- **Deduplication**: hashes canonical identifiers (`normalized_key` per entity type) and skips
  records already ingested for the same source. Kept idempotent.

### 3.2 Normalization (`backend/app/ingestion/normalizers.py`)
- Canonicalization rules: case folding for handles, checksum validation for PGP fingerprints,
  case/checksum canonical forms for wallet addresses, punycode + trailing-dot stripping for
  domains, stable tokenization for username similarity.
- Output: a normalized record that all downstream stages consume.

### 3.3 Entity Extraction (`backend/app/ingestion/entity_extraction.py`)
Extracts typed entities from raw text/metadata:
handles, aliases, PGP fingerprints, wallet addresses (chain-tagged), domains, IPs/ASNs (synthetic
only), TXT dns records, TLS certificate fields (CN/SAN/issuer/serial), hashtags/quotes for later
stylometry.
- Regex + rules + optional spaCy NER; every extraction keeps `source_id` + `raw` text.

### 3.4 Entity Resolution (`backend/app/services/resolution.py`)
Two-level resolution:
1. **Identity resolution** — same `normalized_key` → same DB row (dedup).
2. **Persona resolution** — groups plural identities into a candidate Actor persona
   (e.g. `alpha-2019` … `alpha-2026`). Persona merging is *proposed* by the correlation engine
   and must be accepted by an analyst.

### 3.5 Infrastructure Intelligence (`backend/app/services/infrastructure.py`)
Analyses only authorized/synthetic metadata:
- DNS: nameserver/A records, MX, TXT (source-recorded), IP→ASN mapping
- Certificates: CN/SAN overlap, issuer reuse, serial/validity fingerprinting
- Domains: registrar, registration date proximity (temporal clustering)
- Hosting: ASN/SES (shared host) clustering
- Infrastructure reuse: IP/SES/ASN co-membership of distinct domains
Produces `InfrastructureSignal` objects → feeds correlation.

### 3.6 Stylometry (`backend/app/services/stylometry.py`)
Feature families: char n-grams (2–5), word n-grams (1–2), sentence-length stats,
vocabulary richness (TTR/SR/MTLD-lite), punctuation patterns, function-word rates,
repeated phrases. Similarity = cosine on TF-IDF-weighted feature vectors; returns
`stylometric_similarity`, feature explanation, supporting excerpts, and limitations
(small sample warning, topic-shift warning). Offline fallback tokenizer (no spaCy model
download required at demo time).

### 3.7 Behavior Analysis (`backend/app/services/behavior.py`)
Profiles per handle: posting frequency, inter-post intervals, time-of-day histogram,
day-of-week distribution, lifecycle (first/last seen), platform migration events,
burst/momentum features. Similarity = cosine/earth-mover hybrid on binned histograms.
Returns interpretable profile + migration narrative.

### 3.8 Correlation Engine (`backend/app/services/correlation.py`)
Multi-signal scoring between candidate personas:
- evaluators registered in `SIGNALS` registry (PGP, wallet, handle, infrastructure,
  stylometry, behavior, temporal);
- each evaluator yields a scored contribution + evidence reference;
- **weights are configurable** via `AppSettings.correlation_weights` (DB/env/overlay);
- total → **Relationship Confidence Score (RCS)**, classified per the bands in §5;
- every result is persisted as an `Relationship` row (Postgres) and a `POSSIBLY_SAME_AS`
  edge (Neo4j) with `confidence`, `evidence_ids`, `factors`, `explanation`, `status`.

### 3.9 Evidence Engine (`backend/app/services/evidence.py`)
Materializes each contributing fact into an `Evidence` row (type, strength, description,
score contribution, source, timestamp) and links `evidence → observations → sources`.
The graph carries `HAS_EVIDENCE` edges so the UI can render "WHY" on any inference.

### 3.10 Confidence Engine (`backend/app/services/confidence.py`)
Pure function: weights × normalized signal scores → RCS (0–100) + band label.
All bands:
`0–29 Weak · 30–49 Low · 50–69 Moderate · 70–84 High · 85–100 Very High`
**Explicit disclaimer:** these are prototype-calibrated decision heuristics, not
scientifically validated probabilities.

### 3.11 Timeline Engine (`backend/app/services/timeline.py`)
Builds a unified chronological view from every timestamped artifact (observations, posts,
PGP sightings, wallet associations, persona appearances/disappearances, migrations,
relationship milestones, analyst actions). Supports filtering by entity, event kind,
date window.

### 3.12 Autonomous Mode (`backend/app/workers/`)
- Celery **beat** schedule → `scan_cycle` task chain:
  ingest → normalize → extract → resolve → correlate → graph sync → evidence → confidence → alert.
- `ScanJob` rows track progress/status/errors; SSE endpoint streams progress to the UI.

### 3.13 Graph Synchronizer (`backend/app/graph/sync.py`)
Transactional write-through: after Postgres commits, the sync layer upserts Neo4j nodes/edges
from repositories. Idempotent (MERGE on canonical keys). Tolerant: on Neo4j outage, marks
`graph_sync_pending` and replays later.

---

## 4. Data Classification of Intelligence (locked vocabulary)

| Class | Meaning | Example |
|-------|---------|---------|
| **OBSERVED FACT** | Directly recorded in a source | "PGP KEY_ALPHA seen on Forum X, 2025-03-02" |
| **DERIVED SIGNAL** | Computed from one observed fact | "Wallet address canonical form valid on BTC" |
| **CORRELATION** | Computed relationship between entities | "Persona A and persona B share wallet WALLET_ALPHA" |
| **ANALYST HYPOTHESIS** | Analyst-endorsed interpretation | "shadow_vendor is the same actor as darkmerchant" |

Every Relationship row tracks `evidence_class` of its strongest class to display this label.

---

## 5. Correlation Scoring (prototype)

Configurable weights (`correlation_weights`):

| Signal | Weight (default) | Notes |
|--------|-----------------|-------|
| PGP fingerprint match | 30 | strongest non-trivial identity anchor |
| Wallet address match | 25 | shared financial footprint |
| Unique handle match | 15 | exact canonical match |
| Infrastructure reuse | 15 | shared cert/domain/SES/ASN |
| Stylometric similarity | 10 | TF-IDF cosine, gated by sample size |
| Behavior similarity | 5 | histograms + lifecycle |

Total cap = 100. A *similar-but-not-equal* handle yields at most a capped 5 points so that
look-alike usernames **cannot** cross the Low band on their own (false-positive defense).
Confidence bands as in §3.10. Explanations interpolate the contributing factors verbatim.

---

## 6. Security Architecture (summary)

- JWT access (+ refresh) with role claims; RBAC matrix in `SECURITY.md`.
- Argon2id password hashing; bcrypt (passlib) not used as primary.
- Rate limiting (per-IP + per-user) via Redis sliding window.
- Secure headers middleware (HSTS, CSP, X-Frame-Options, nosniff).
- Input validation at the API boundary (Pydantic v2), SQLAlchemy parameterized queries,
  Cypher parameterized queries (no string interpolation).
- Full audit log (`audit_events`) — immutable append log of analyst + system actions.
- No secrets in source: everything via environment variables / `.env` (gitignored).
- Exclusive demo accounts ship with demo-only roles; admin ops require admin JWT.

---

## 7. Tech Choices & Rationale

| Choice | Rationale |
|--------|-----------|
| FastAPI + Pydantic v2 | Typed contracts, OpenAPI generation, async, fast dev |
| SQLAlchemy 2 async + asyncpg + Alembic | System of record; migrations as code |
| Neo4j 5 + official driver (raw Cypher) | Full control over the correlation index; no ORM impedance |
| Celery + Redis | Standard, robust background tasks + beat scheduler |
| scikit-learn | TF-IDF, SVD, cosine — deterministic, offline |
| spaCy (optional) | PoS/entity enrichment; graceful fallback if model absent |
| sentence-transformers (optional) | Candidate embedding similarity; **never required** for demo |
| React + TS + Vite + Tailwind | Fast professional UI; Cytoscape.js for graph, Recharts for viz |
| Docker Compose | One-command reproducible stack for demo/judges |

**Offline guarantee:** the demo profile runs Postgres, Neo4j, Redis, and application images
from local volumes/images; no external network calls are made at runtime.

---

## 8. Target Repository Layout

```
SIH2026/
├── docker-compose.yml
├── .env.example
├── docs/{schemas,decisions.md}
├── backend/
│   ├── requirements/  app/  tests/  alembic/
│   └── Dockerfile
└── frontend/
    ├── src/{components,pages,api,context,graph,lib}
    └── Dockerfile
```

Backend module tree (planned):

| Path | Purpose |
|------|---------|
| `app/core/` | settings, security (JWT, hashing, RBAC), logging, rate limit |
| `app/models/` | SQLAlchemy models (mirror `postgres_schema.sql`) |
| `app/schemas/` | Pydantic request/response models |
| `app/api/v1/` | routers: auth, actors, search, graph, evidence, timeline, infra, investigations, relationships, scans, alerts, reports, analytics, admin |
| `app/repositories/` | Postgres data access per domain |
| `app/graph/` | Neo4j driver, sync service, traversal queries |
| `app/services/` | ingestion pipeline, correlation, evidence, confidence, stylometry, behavior, infrastructure, timeline, reports |
| `app/data_generation/` | seeded synthetic dataset generator |
| `app/workers/` | Celery app, tasks, beat schedule |

---

## 9. Ports & Docker Services

| Service | Port | Notes |
|---------|------|-------|
| backend (uvicorn) | 8000 | REST API + SSE |
| neo4j | 7474/7687 | Browser + bolt (auth required) |
| postgres | 5432 | system of record |
| redis | 6379 | broker + cache + rate-limit |
| worker (celery) | – | consumes scan/investigation tasks |
| beat (celery) | – | triggers autonomous scan cycles |
| frontend (vite dev / nginx prod) | 5173 / 80 | UI, proxies /api → backend |

`docker-compose.yml` defines `dev` and `demo` profiles with healthchecks, volume mounts,
and an isolated `shadowgraph-net` network.

---

## 10. Roadmap Dependencies

```
P1 schemas/contracts ──► P2 backend skeleton + auth ──► P3 synthetic data + ingestion
      ──► P4 extraction/resolution ──► P5 graph engine ──► P6 correlation/evidence/confidence
      ──► P7 stylometry/behavior ──► P8 timeline ──► P9–P10 frontend (screens + graph UI)
      ──► P11 autonomy/alerts ──► P12 reports ──► P13 security/tests/perf
      ──► P14 demo mode ──► P15 polish
```

Each phase ends with running tests and a working vertical slice; nothing is merged without
its tests (see `TESTING.md`).
