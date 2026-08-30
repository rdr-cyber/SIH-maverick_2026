# Architecture Decision Records (SHADOWGRAPH)

Status: **Accepted** unless noted. New ADRs appended as phases progress.

## ADR-001 — Postgres as system of record, Neo4j as correlation index
Most facts, evidence, review state, and audit live in Postgres; Neo4j materializes the
correlated graph for traversal/visualization. Rationale: transactional integrity for
provenance and reviews; graph engine tuned for neighborhood exploration; the two are
reconciled by an idempotent sync layer with `graph_sync_state` bookkeeping.

## ADR-002 — Raw Cypher via official driver (no ORM on Neo4j)
Constraints/indexes and sync in plain parameterized Cypher; avoids ORM abstraction leaks,
keeps full control of MERGE semantics and the inference-edge property contract.

## ADR-003 — Deterministic synthetic dataset, offline demo
Generator uses fixed seed `20260726`; demo needs no network egress. All analyzer pipelines
have offline fallbacks (regex tokenizer, TF-IDF) so spaCy/sentence-transformers are optional.

## ADR-004 — Score terminology and semantics
"Relationship Confidence Score" (RCS 0–100) with bands Weak/Low/Moderate/High/Very High.
Explicitly a decision heuristic, never a probability; UI and exports enforce the label.

## ADR-005 — Intelligence taxonomy enforced end-to-end
OBSERVED FACT / DERIVED SIGNAL / CORRELATION / ANALYST HYPOTHESIS — columns (`class`,
`hypothesis_label`) and UI badges so the platform cannot silently present inference as fact.

## ADR-006 — Human-in-the-loop hard gate
Correlation engine writes `POSSIBLY_SAME_AS` edges with `status='pending'`; only a
senior_analyst can accept/reject/uncertain; every review writes an audit event with a note.
No background pathway can auto-accept an inference.

## ADR-007 — Celery + Redis for autonomy
Beat-driven scan cycles; SSE for live progress; scan jobs resume idempotently (dedup keys,
batch ids). Chosen over a hand-rolled scheduler for reliability and observability.

## ADR-008 — Frontend: React/TS/Vite/Tailwind + Cytoscape.js
Cytoscape for the evidence graph (zoom/pan/filter/select), Recharts for analytics panels;
all graph edges rendered straight from backend `graph` endpoints (no client-side derivation),
guaranteeing "the graph is the backend".

## ADR-009 — Docker profiles demo/dev
`demo` = production-like single-stack, offline; `dev` = hot-reload backend + vite.
Service ports unexposed on demo where possible; secrets via `.env` only, fail-fast with `${VAR:?}`.

## ADR-010 — Honest limitations surfaced in UI
Reliability gates (small corpora), feature-level explanations, and "limitations" fields are
part of every AI signal payload; the UI renders them rather than hiding them.
