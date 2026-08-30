# GRAPH MODEL — Neo4j (Cypher)

Neo4j is the **correlation index**: it materializes the linked view of personas, their
identities, content, and infrastructure, and it hosts the evidence graph that the UI renders.
**PostgreSQL is the system of record** (see `DATABASE.md`); every node/edge below stores
`{postgres_uuid}` so the two stores stay reconcilable — the graph synchronizer upserts from
Postgres facts.

## 1. Node labels & properties

Every node carries the common property block:
`{ postgres_uuid, first_seen, last_seen, source_ref (source name), created_at, updated_at }`
plus label-specific properties below. `pgkey` is the canonical dedup key in Neo4j
(mirrors `normalized_key` in Postgres) — used with `MERGE` for idempotent sync.

### Identity
| Label | Identity property | Extra properties |
|-------|-------------------|------------------|
| `Actor` | `pgkey` (persona code) | `code`, `display_name`, `status`, `risk_level`, `notes` |
| `Handle` | `pgkey` (normalized) | `value`, `display` (raw), `category`, `status` |
| `Alias` | `pgkey` | `value`, `kind` |
| `PGPKey` | `pgkey` (UPPER fp) | `fingerprint`, `key_id`, `user_id`, `algorithm` |
| `Wallet` | `pgkey` (chain:addr) | `address`, `chain`, `address_type` |
| `Post` | `pgkey` (source+ext id) | `external_id`, `title`, `excerpt` (first 400 chars), `language`, `posted_at` |

### Infrastructure
| Label | Identity property | Extra properties |
|-------|-------------------|------------------|
| `Domain` | `pgkey` | `name`, `registrar`, `registration_date`, `status` |
| `Infrastructure` | `pgkey` | `kind` (ip/asn/server/shared_host/netblock), `value`, `organization`, `country` |
| `Certificate` | `pgkey` | `serial`, `cn`, `san` (list), `issuer`, `not_before`, `not_after`, `fingerprint_sha256` |

### Platforms & knowledge
| Label | Identity property | Extra properties |
|-------|-------------------|------------------|
| `Marketplace` | `pgkey` (name) | `name`, `codename`, `status` |
| `Forum` | `pgkey` (name) | `name`, `codename`, `status`, `category` |
| `Evidence` | `pgkey` (evidence code) | `code`, `kind`, `title`, `strength`, `class`, `score_contribution`, `description` |
| `TimelineEvent` | `pgkey` | `kind`, `title`, `occurred_at`, `confidence_delta` |

## 2. Relationship types & semantics

### Identity edges
| Edge | From → To | Semantics |
|------|-----------|-----------|
| `USES` | Actor → Handle | persona historically used this handle |
| `USES` | Actor → Alias | persona used this label |
| `USES` | Actor → PGPKey | persona's key fingerprint observed |
| `ASSOCIATED_WITH` | Actor → Wallet | financial footprint link |
| `ASSOCIATED_WITH` | Actor → Infrastructure | shared infra footprint |
| `HAS_EVIDENCE` | Actor → Evidence | evidence attached to persona |

### Behavioral & content edges
| Edge | From → To | Semantics |
|------|-----------|-----------|
| `APPEARS_ON` | Handle → Marketplace / Forum | handle observed on platform |
| `AUTHORED` | Handle → Post | handle authored post |
| `ACTIVE_DURING` | Actor → TimelineEvent | persona active/event on timeline |

### Infrastructure edges
| Edge | From → To | Semantics |
|------|-----------|-----------|
| `RESOLVES_TO` | Domain → Infrastructure | DNS resolution (synthetic), has `record_kind` |
| `HAS_CERTIFICATE` | Domain → Certificate | TLS cert observed on domain |

### Inference edges
| Edge | From → To | Semantics |
|------|-----------|-----------|
| `POSSIBLY_SAME_AS` | Actor → Actor | **the key inference edge** — hypothesis of persona overlap |

Also allowed (added by graph sync as evidence chains): `USES` between different entities via
intermediate edges is expressed as paths; we do not shortcut facts — the graph preserves the
full evidence path from Actor → evidence anchor.

## 3. Inference edge properties (POSSIBLY_SAME_AS)

```
confidence        : Float 0..1   (stored 0..1; UI maps to 0..100 for display)
band              : String  weak|low|moderate|high|very_high
status            : String  pending|accepted|rejected|uncertain
evidence_ids      : List<String>   EVID-0001, EVID-0002, ...
scoring_factors   : List<Map>      [{signal, weight, score, note}]
explanation       : String         human-readable WHY
hypothesis_label  : String         e.g. "POSSIBLY_SAME_AS (hypothesis)"
engine_ref        : String         correlation_engine | analyst | ingestion
reviewed_by       : String         analyst username (nullable)
reviewed_at       : DateTime
created_at / updated_at : DateTime
```

Rules:
- **No edge is auto-accepted.** The correlation engine writes with `status: "pending"`.
- Analysts transition `pending → accepted/rejected/uncertain` via the API; the sync layer
  updates the edge and logs an audit event.
- All other (non-inference) edges are `OBSERVED FACT` edges — they mirror observed data and
  carry no confidence (or `confidence: 1.0` with `class: OBSERVED_FACT`).

## 4. Required traversal queries (implemented in Phase 5)

1. **Expand neighborhood** — `MATCH (n) -[r]- (m) ...` with optional confidence/date filters,
   up to depth 2, bounded node count (default 250) to keep the UI responsive.
2. **Evidence chain for an edge** — reconstruct `Actor →(USES)→ PGPKey` etc. facts backing a
   specific `POSSIBLY_SAME_AS` relationship.
3. **Migration path** — `Actor →(ACTIVE_DURING)→ TimelineEvent(kind:'migration')` and the
   handles/platforms involved.
4. **High-confidence relationships** — `POSSIBLY_SAME_AS` edges with `band >= 'high'`
   and `status='pending'` (Command Center alert feed).
5. **Path search with confidence filter** — candidate actor pairs for correlation
   (`WHERE r.confidence >= threshold`).
6. **Shared infrastructure cluster** — Domain/Infrastructure/Certificate co-membership
   analysis for the Infrastructure module.
## 5. Graph synchronizer behavior (`backend/app/graph/sync.py`)

1. After a Postgres transaction commits (ingest batch, relationship review, investigation
   update), enqueue a sync task per affected entity.
2. Sync task: `MERGE (n:Label {pgkey: ...}) SET n += properties`; then `MERGE` the relevant
   edges with `SET` of all inference-edge fields.
3. Edge writes are idempotent: same `(from_pgkey, type, to_pgkey)` merges, properties update.
4. On Neo4j failure, write `graph_sync_state` row (`failed`, `attempts+1`) and retry with
   backoff via Celery. UI shows "graph sync pending" state.
5. Consistent deletion: persona archive sets `status:'archived'`; does not cascade-delete
   nodes (soft semantics).

## 6. APOC & constraints

- Uses `apoc.merge.node` / `apoc.cypher.runFirstColumn` only if APOC is enabled in the image
  (optional; core sync uses plain Cypher `MERGE` so no APOC dependency is required).
- Indexes/constraints declared in `docs/schemas/neo4j_schema.cypher` — applied at container
  start by the `neo4j-init` service (idempotent `CREATE INDEX IF NOT EXISTS`).
- Bolt credentials come from `.env` (never hard-coded).

## 7. Consistency contract

| Question | Authoritative store |
|----------|---------------------|
| "Is this relationship reviewed?" | Postgres `relationships.status` (single source of truth) |
| "What is the evidence chain for this edge?" | Postgres `evidence` + `relationship_observations` |
| "What does the neighborhood look like for traversal/zoom?" | Neo4j (rendered instantly) |
| "When did X first get seen?" | Postgres (`first_seen`), mirrored to Neo4j for display |

The UI always dereferences display details from Postgres via `{postgres_uuid}`; Neo4j is
treated as a queryable index, never as a store of unverifiable state.

---

*See also: [`docs/schemas/neo4j_schema.cypher`](docs/schemas/neo4j_schema.cypher) for the
executable schema, [`DATABASE.md`](DATABASE.md) for the relational complement.*
