# SHADOWGRAPH

### Explainable Dark Web Threat Intelligence & Actor Correlation Platform

> Connect the clues. Explain the evidence. Strengthen attribution.

**Problem Statement ID:** 26151 · **Theme:** Blockchain & Cybersecurity
**Organization:** National Technical Research Organisation (NTRO)

SHADOWGRAPH helps authorized investigators correlate publicly available, authorized, and
**synthetic** intelligence about threat-actor personas — handles, PGP fingerprints, wallets,
marketplace/forum identities, posts, domains, infrastructure and TLS metadata, stylometry,
and behavior — and produces **evidence-backed attribution hypotheses with transparent reasoning**.

> ⚠️ **Safety & Ethics by design.** SHADOWGRAPH is a *defensive* intelligence prototype.
> It never touches real systems, Tor, or real individuals. The entire demo runs on a
> deterministic synthetic ecosystem so it works fully offline. Inferred relationships are
> always labeled as hypotheses, never as proven identities, and every inference requires
> human-in-the-loop review.

---

## The Three Core SIH Capabilities

| # | Capability | What it does |
|---|-----------|--------------|
| 1 | **Infrastructure Intelligence** | Correlates DNS, TLS certificate metadata, domains, hosting/ASN and infrastructure reuse from synthetic/authorized records. |
| 2 | **Cross-Marketplace Actor Mapping** | Connects Actor → Handle → Marketplace/Forum → PGP → Wallet → Infrastructure → Evidence in a property graph (Neo4j). |
| 3 | **AI-Assisted Persona Correlation** | Stylometry + behavior analysis produce explainable similarity signals that feed the correlation engine. |

**Centerpiece:** the **Evidence Graph** — every rendered edge is a real backend relationship
with evidence IDs, scoring factors, and a human-readable explanation. Click any edge to see *WHY*.

### Terminology (locked)
- Score is called **Relationship Confidence Score** — never "probability this is the same person."
- Intelligence is classified as **OBSERVED FACT → DERIVED SIGNAL → CORRELATION → ANALYST HYPOTHESIS**.

---

## Quick Overview

- **Backend:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · PostgreSQL 16
- **Graph:** Neo4j 5.x + Cypher (official driver, thin repository layer)
- **ML/NLP:** scikit-learn (TF-IDF char/word n-grams) · spaCy (optional) · NumPy · pandas
  — all analyzers have an **offline fallback** so the demo never needs network access
- **Workers/Autonomy:** Celery + Redis + Beat (scheduler), SSE for live scan progress
- **Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · Cytoscape.js · Recharts
- **Deployment:** Docker + Docker Compose (dev & prod profiles)

---

## Repository Layout (target)

```
SIH2026/
├── docker-compose.yml          # Postgres + Neo4j + Redis + backend + worker + frontend
├── .env.example                # All configuration, no secrets in source
├── docs/
│   ├── schemas/
│   │   ├── postgres_schema.sql # Canonical DDL (Phase 1 artifact)
│   │   └── neo4j_schema.cypher # Canonical graph schema (Phase 1 artifact)
│   └── decisions.md            # Architecture Decision Records
├── backend/
│   ├── app/
│   │   ├── core/               # config, security, logging
│   │   ├── api/                # FastAPI routers
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── repositories/       # PostgreSQL data access
│   │   ├── graph/              # Neo4j (Cypher) data access
│   │   ├── services/           # correlation, stylometry, behavior, timeline,
│   │   │                       # evidence, confidence, infrastructure
│   │   ├── ingestion/          # synthetic loader & normalization
│   │   ├── data_generation/    # deterministic synthetic dataset generator
│   │   └── workers/            # Celery tasks + scheduler
│   ├── alembic/                # migrations
│   └── tests/
└── frontend/
    └── src/
        ├── components/  pages/  api/  context/  graph/
```

---

## Documentation Index

| Doc | Contents |
|-----|----------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System architecture, pipeline, component responsibilities |
| [`API.md`](API.md) | Full REST contract, error model, SSE, auth |
| [`DATABASE.md`](DATABASE.md) + [`docs/schemas/postgres_schema.sql`](docs/schemas/postgres_schema.sql) | PostgreSQL model design & canonical DDL |
| [`GRAPH_MODEL.md`](GRAPH_MODEL.md) + [`docs/schemas/neo4j_schema.cypher`](docs/schemas/neo4j_schema.cypher) | Neo4j node/edge model & schema |
| [`docs/DATASET.md`](docs/DATASET.md) | Synthetic ecosystem design, volumes, flagship & FP scenarios |
| [`ML_MODEL.md`](ML_MODEL.md) | Stylometry, behavior analysis, scoring & confidence |
| [`SECURITY.md`](SECURITY.md) | AuthN/AuthZ, hardening, audit, secrets |
| [`DEMO.md`](DEMO.md) | Five-minute SIH demo script, offline guarantee |
| [`TESTING.md`](TESTING.md) | Test pyramid & coverage matrix |
| [`SIH_PITCH.md`](SIH_PITCH.md) | Pitch narrative, differentiators, Q&A prep |

---

## Development Roadmap (Phases)

| Phase | Scope | Status |
|------|-------|--------|
| 1 | Architecture, schemas, API contracts, Docker design | ✅ (this deliverable) |
| 2 | Backend foundation: FastAPI, PostgreSQL, Neo4j, auth | ⏳ next |
| 3 | Synthetic dataset generator, ingestion, normalization | pending |
| 4 | Entity extraction, deduplication, resolution | pending |
| 5 | Graph engine & relationship creation | pending |
| 6 | Correlation, evidence & confidence engines | pending |
| 7 | Stylometry & behavior analysis | pending |
| 8 | Timeline engine | pending |
| 9 | Frontend: Command Center, Search, Actor Profile | pending |
| 10 | Graph UI, Evidence Explorer, Timeline | pending |
| 11 | Autonomous processing, alerts, scheduler | pending |
| 12 | Reports (PDF/CSV/JSON) | pending |
| 13 | Security hardening, tests, performance | pending |
| 14 | Full demo mode ("RUN INVESTIGATION") | pending |
| 15 | UI polish & presentation prep | pending |

*See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full road map details.*
