# TESTING — Plan (Phase 1 design)

## 1. Principles

- **Test the behavior, not the implementation.** Each phase ships with its tests; nothing
  merges without a green `backend/tests` + `frontend` unit run.
- Deterministic: fixtures are versioned in-repo (`backend/tests/fixtures/`), seeded, and the
  flagship scenarios assert exact expected scores.
- Fast by default: unit tests avoid Docker where possible (SQLite/asyncpg test engine and a
  Neo4j-less graph service stub); integration tests run against the compose stack in CI.

## 2. Test pyramid

| Layer | Framework | Scope |
|-------|-----------|-------|
| Unit | pytest + pytest-asyncio | normalization, extraction, scoring math, stylometry, behavior, confidence bands, report serializers |
| Repository | pytest w/ test DB | SQLAlchemy CRUD, dedup, provenance FKs, audit writes |
| Graph | pytest w/ neo4j test container (or stub) | sync upserts, traversal queries, evidence-chain reconstruction |
| API | FastAPI TestClient + httpx | every endpoint: status, RBAC, validation errors, pagination, SSE shape |
| E2E/demo | Playwright (frontend) | login → search → actor profile → graph → evidence → review → report; RUN INVESTIGATION |
| Security | pytest + pytest-security | auth flows, RBAC matrix, rate limit, headers, safe errors |
| Perf smoke | locust (optional) | subgraph endpoint under load (target < 300 ms @ 50 rps local) |

## 3. Coverage matrix (feature → test file)

| Feature | Test file (planned) | Key assertions |
|---------|--------------------|----------------|
| Normalization | `test_normalizers.py` | handle case-folding, PGP checksum, wallet canonical, domain punycode |
| Entity extraction | `test_entity_extraction.py` | typed entities found in synthetic post text w/ source + raw |
| Dedup | `test_dedup.py` | re-ingest same record → no dup rows; UNIQUE violations mapped to 409 |
| Entity resolution | `test_resolution.py` | alias→persona grouping; ambiguous candidate handling |
| Correlation | `test_correlation.py` | RCS math, weight config overlay, sub-rules, candidate generation |
| Scoring bands | `test_confidence.py` | boundary values 29/30/49/50/69/70/84/85 |
| Stylometry | `test_stylometry.py` | feature extraction determinism; similarity monotonicity; reliability gate; no-tokenizer fallback |
| Behavior | `test_behavior.py` | histogram overlap, migration narrative, small-sample gate |
| Graph | `test_graph_sync.py` | MERGE idempotency, POSSIBLY_SAME_AS props round-trip, evidence chain query |
| Timeline | `test_timeline.py` | chronological ordering, filters, milestone generation |
| Reports | `test_reports.py` | PDF/CSV/JSON generation determinism; RBAC on download |
| API | `test_api_*.py` per router | status codes, schema validation, pagination cursors |
| Auth/RBAC | `test_security.py` | login/refresh/logout, per-route role matrix, 429, headers, no stack traces |
| **False positives** | `test_false_positives.py` | Beta < 50 (Low), Delta ≤ Moderate, shared-host ≤ Moderate, Alpha ≥ 70 (High) |
| **Workflow** | `test_workflow.py` | create investigation → target → run → evidence → review → report (full path) |

## 4. Fixtures

- `backend/tests/fixtures/actors.yaml` — persona definitions (Alpha/Beta/Gamma/Delta + background)
- `backend/tests/fixtures/migration_story.yaml` — flagship hidden-relationship ground truth
- `backend/tests/fixtures/false_positive_cases.yaml` — the three FP scenarios
- `backend/tests/fixtures/corpora/*.txt` — canonical posts for stylometry determinism tests
- `backend/tests/dataset_manifest.json` — generator output checksums (compare per run)

Regeneration command: `python -m app.data_generation.seed --seed 20260726 --out tests/fixtures/`

## 5. Key assertions for the flagship scenario (Alpha)

1. Ingestion of batch B+1 yields `new_identifiers ≥ 5` and creates 0 duplicate rows.
2. `stylometry` for `darkmerchant` vs `shadow_vendor` cosine ≥ 0.85 with reliability adequate.
3. `correlation.evaluate` yields RCS **70–79** (High) and explanation lists 4 factors.
4. Graph contains `Actor(ALPHA-1)-[:POSSIBLY_SAME_AS]->Actor(ALPHA-2)` with
   `status='pending'`, `evidence_ids` length ≥ 4.
5. Timeline orders appearance → PGP → wallet → migration → relationship.
6. Analyst accept → audit event + edge `status='accepted'`.
7. Report generation round-trips JSON, CSV header, PDF byte-header.

## 6. False-positive assertions (Beta & friends)

1. Beta `shadow_vend0r` → RCS < 50 and band ∈ {weak, low}.
2. Copycat Delta stylometry high but RCS ≤ Moderate.
3. Shared-hosting infra pair RCS ≤ Moderate.
4. No `POSSIBLY_SAME_AS` edge created for 1–3 (below candidate threshold) — this is the
   presentation proof that the system resists decoys.

## 7. Commands

```bash
# backend
cd backend
python -m pytest -q                                  # unit + API w/ test engine
python -m pytest -m integration                      # against compose stack
# frontend
cd frontend && npx tsc --noEmit && npx vitest run    # types + component tests
npx playwright test                                   # e2e (optional in CI)
```

## 8. CI (Phase 13)

GitHub Actions: lint (ruff), typecheck (mypy/pyright), unit tests, compose integration,
frontend build, security scans (pip-audit, npm audit), coverage report (target ≥ 80% core
modules). Everything runs on `pull_request` and on `main`.
