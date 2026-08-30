# API — REST Contract (Phase 1 design)

Base URL: `http://localhost:8000/api/v1` · OpenAPI generated live by FastAPI at `/docs`
(swagger) and `/redoc`. All bodies are JSON. IDs are UUIDs; human codes `ACTOR-…`, `EVID-…`,
`REL-…`, `INV-…`, `RPT-…` are exposed as `code` fields.

## 1. Conventions

### 1.1 Errors
```json
{ "error": { "code": "REL_NOT_FOUND", "message": "Relationship 89f4… not found", "details": {...}, "request_id": "req_123" } }
```
HTTP status mapping: 400 validation · 401 unauthenticated · 403 forbidden (RBAC) ·
404 missing · 409 conflict/dedup · 429 rate limited · 500 unexpected (safe error, no stack).

### 1.2 Pagination
Query params `limit` (default 50, max 500) & `cursor` (opaque base64 cursor).
Response envelope: `{ "items": [...], "next_cursor": "…", "total": 1234 }`.

### 1.3 Auth
`Authorization: Bearer <access_token>` (JWT, 15 min) · refresh token (7 d, httpOnly cookie
or body). Roles: `analyst`, `senior_analyst`, `admin`. RBAC matrix in `SECURITY.md`.

### 1.4 Search
Search endpoints accept: `q` (free-text), `type` (any of handle/alias/pgp/wallet/domain/
actor/marketplace/forum/post), `from_ts`/`to_ts`, and per-entity filters. Results return
matched entity + normalized form + `source` + links.

### 1.5 The evidence explanation envelope
Wherever a relationship/`POSSIBLY_SAME_AS` candidate appears it is serialized with a
mandatory explanation block:
```json
{
  "relationship_code": "REL-0012",
  "confidence": 72,
  "band": "high",
  "status": "pending",
  "hypothesis_label": "POSSIBLY_SAME_AS (hypothesis)",
  "evidence": [
    { "code": "EVID-0001", "kind": "pgp_match", "class": "OBSERVED_FACT",
      "strength": "strong", "score_contribution": 30,
      "description": "PGP KEY_ALPHA observed in signature metadata of both personas.",
      "source": {"name":"synthetic-marketplace-b","access_method":"synthetic"} }
  ],
  "scoring_factors": [
    { "signal": "pgp_match", "weight": 30, "score": 30, "note": "exact fingerprint match" }
  ],
  "explanation": "shadow_vendor and darkmerchant share PGP KEY_ALPHA (+30) and wallet WALLET_ALPHA (+25); stylometric cosine similarity 0.91 (+10)."
}
```
`confidence` is displayed as **Relationship Confidence Score**; the UI and exports must never
render it as "probability".

## 2. Auth
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | public | `{username, password}` → `{access_token, refresh_token, user}`; audit `auth.login` |
| POST | `/auth/refresh` | public | rotate refresh token |
| GET | `/auth/me` | any | current analyst profile + permissions |
| POST | `/auth/logout` | any | revoke refresh token; audit |

## 3. Command Center (analytics)
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/analytics/overview` | analyst | tracked actors, active investigations, new intelligence (24h), high-confidence pending relationships, recent alerts, last scan |
| GET | `/analytics/scans` | analyst | recent scan jobs w/ status & counters |
| GET | `/analytics/actors/:code` | analyst | per-actor stats |

## 4. Search
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/search` | analyst | global search across all entity types (`q`, `type`, date range) |
| GET | `/search/handles` | analyst | handle search incl. fuzzy (trigram `similarity`) |
| GET | `/search/pgp` | analyst | fingerprint/uid search |
| GET | `/search/wallets` | analyst | address search, chain filter |
| GET | `/search/domains` | analyst | domain/registrar/registration-window search |
| GET | `/search/infrastructure` | analyst | IP/ASN/SES search |

## 5. Actors
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/actors` | analyst | list actors (status, risk filter, paginate) |
| POST | `/actors` | senior_analyst | create Actor persona |
| GET | `/actors/:code` | analyst | full profile (handles, aliases, pgp, wallets, infra, platforms, timeline, related actors, confidence, sources) |
| PATCH | `/actors/:code` | senior_analyst | update persona fields |
| DELETE | `/actors/:code` | admin | archive persona (soft) |
| POST | `/actors/:code/merge` | senior_analyst | propose persona merge (creates proposed relationship for review) |
## 6. Evidence Graph
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/graph/subgraph` | analyst | `?entity_type&entity_id&depth=2&max_nodes=250&min_confidence&from_ts&to_ts&types=...` → Cytoscape-ready `{nodes, edges}` (node: `{id,label,group,meta}`, edge: `{id,source,target,type,label,confidence,band,status,evidence_ids,explanation}`) |
| GET | `/graph/relationship/:code` | analyst | full evidence-chain view for one relationship (used by the edge panel / "WHY?") |
| GET | `/graph/paths` | analyst | path search between two entities `?from=&to=&max_hops=4` |
| GET | `/graph/infrastructure-clusters` | analyst | shared-IP/ASN/cert/registration clusters |
| POST | `/graph/expand` | analyst | expand a node's neighborhood (returns the delta subgraph) |

## 7. Evidence Explorer
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/evidence` | analyst | browse evidence (kind/class/strength/date filters, paginate) |
| GET | `/evidence/:code` | analyst | evidence detail + source + observations + relationship it supports |
| GET | `/evidence/:code/observations` | analyst | raw observations behind the evidence |
| POST | `/evidence` | senior_analyst | manual analyst observation evidence (audit-logged) |

## 8. Timeline
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/timeline` | analyst | events (actor/kind/date-range filters, paginate); ordered `occurred_at ASC` |
| GET | `/timeline/actors/:code` | analyst | persona timeline w/ milestone highlights |
| GET | `/timeline/summary` | analyst | compressed view for UI ribbon |

## 9. Infrastructure
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/infrastructure/domains` | analyst | domains list/filters |
| GET | `/infrastructure/domains/:pgkey` | analyst | domain detail (DNS, certs, related handles via graph) |
| GET | `/infrastructure/certificates` | analyst | cert browse (cn/issuer/serial/date) |
| GET | `/infrastructure/certificates/:pgkey` | analyst | cert detail + domain reuse |
| GET | `/infrastructure/hosts` | analyst | infrastructure entities (ip/asn/ses) |
| GET | `/infrastructure/indicators` | analyst | **historical indicators**: registration proximity, cert issuance bursts, IP reuse timeline |

## 10. Investigations & workflow
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| POST | `/investigations` | analyst | create investigation |
| GET | `/investigations` | analyst | list (status/lead/date filters) |
| GET | `/investigations/:code` | analyst | detail incl. targets, notes, run history |
| PATCH | `/investigations/:code` | analyst (lead) | update |
| POST | `/investigations/:code/status` | analyst (lead) | `draft→active→paused→closed` |
| POST | `/investigations/:code/targets` | analyst | add search target (entity_type+id) |
| DELETE | `/investigations/:code/targets/:id` | analyst | remove target |
| POST | `/investigations/:code/notes` | analyst | add note (body, visibility) |
| POST | `/investigations/:code/run` | analyst (lead) | **RUN INVESTIGATION** (demo entrypoint) — triggered pipeline, see `DEMO.md` |
| GET | `/investigations/:code/status` | analyst | live pipeline progress (SSE) |

## 11. Relationship review (human-in-the-loop)
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/relationships` | analyst | browse w/ filters (`status`, `band`, `kind`, min confidence) |
| GET | `/relationships/:code` | analyst | detail incl. full evidence chain |
| POST | `/relationships/:code/review` | senior_analyst | body `{decision: accepted\|rejected\|uncertain, note}` — writes audit event, updates graph edge |
| GET | `/relationships/pending-high` | analyst | pending relationships with `band≥high` (Command Center) |

## 12. Autonomous monitoring
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/scans` | analyst | scan job list & counters |
| GET | `/scans/:code` | analyst | detail incl. errors digest |
| POST | `/scans/run` | senior_analyst | trigger `demo_run`/`manual` cycle on demand |
| GET | `/scans/stream` | analyst | SSE `scan.job.{id}` events: `{phase, processed, found, errors}` |
| GET | `/alerts` | analyst | alerts feed (severity/kind/date filters) |
| POST | `/alerts/:code/acknowledge` | analyst | acknowledge; audit |

## 13. Reports
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| POST | `/reports` | analyst | request report `{investigation_code, kind: pdf\|csv\|json, filters}` |
| GET | `/reports` | analyst | list with status |
| GET | `/reports/:code` | analyst | metadata + download URL when `ready` |
| GET | `/reports/:code/download` | analyst | file download (PDF/CSV/JSON) |
| GET | `/reports/preview` | analyst | preview JSON of report content before generation |

## 14. Admin
| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET/POST | `/admin/analysts` | admin | list/create analysts |
| PATCH | `/admin/analysts/:id` | admin | update role/status |
| GET | `/admin/audit` | admin | audit log browse (action/analyst/date filters) |
| GET | `/admin/system` | admin | service health: db, neo4j, redis, worker queue depth |
| POST | `/admin/resync-graph` | admin | force graph resync from Postgres |
| POST | `/admin/weights` | admin | update correlation weights (persisted overlay) |
| GET | `/admin/weights` | any | read current weights |

## 15. SSE contract (Graph/Live updates)
Event format: `data: {"type": "...", "payload": {...}}\n\n`.
Types: `scan.job.progress`, `scan.job.finished`, `alert.created`, `relationship.reviewed`,
`graph.updated`, `pipeline.phase` (investigation run). Clients subscribe per scope
(`?investigation=INV-0001&scan=SCN-…`).

## 16. Sequencing guarantees
- All mutating endpoints are idempotent where sensible (dedup via `normalized_key`/`external_id`).
- Relationship review accepts stale-prevention header `If-Match: <updated_at>` (409 on conflict).
- Data export endpoints never include plain-text credentials or raw internal errors.
