// ============================================================================
// TRILOK TRACE — Neo4j canonical schema (Phase 1 artifact)
// Problem Statement ID 26151 · NTRO · SIH 2026
// Idempotent: safe to run on every container start (neo4j-init service).
// Mirrors: GRAPH_MODEL.md
// ============================================================================
// Indexes & unique constraints (pgkey = canonical dedup key, mirrors Postgres normalized_key)
CREATE CONSTRAINT actor_pgkey        IF NOT EXISTS FOR (a:Actor)      REQUIRE a.pgkey IS UNIQUE;
CREATE CONSTRAINT handle_pgkey       IF NOT EXISTS FOR (h:Handle)     REQUIRE h.pgkey IS UNIQUE;
CREATE CONSTRAINT alias_pgkey        IF NOT EXISTS FOR (a:Alias)      REQUIRE a.pgkey IS UNIQUE;
CREATE CONSTRAINT pgp_pgkey          IF NOT EXISTS FOR (p:PGPKey)     REQUIRE p.pgkey IS UNIQUE;
CREATE CONSTRAINT wallet_pgkey       IF NOT EXISTS FOR (w:Wallet)     REQUIRE w.pgkey IS UNIQUE;
CREATE CONSTRAINT post_pgkey         IF NOT EXISTS FOR (p:Post)       REQUIRE p.pgkey IS UNIQUE;
CREATE CONSTRAINT domain_pgkey       IF NOT EXISTS FOR (d:Domain)     REQUIRE d.pgkey IS UNIQUE;
CREATE CONSTRAINT infra_pgkey        IF NOT EXISTS FOR (i:Infrastructure) REQUIRE i.pgkey IS UNIQUE;
CREATE CONSTRAINT cert_pgkey         IF NOT EXISTS FOR (c:Certificate) REQUIRE c.pgkey IS UNIQUE;
CREATE CONSTRAINT market_pgkey       IF NOT EXISTS FOR (m:Marketplace) REQUIRE m.pgkey IS UNIQUE;
CREATE CONSTRAINT forum_pgkey        IF NOT EXISTS FOR (f:Forum)      REQUIRE f.pgkey IS UNIQUE;
CREATE CONSTRAINT evidence_pgkey     IF NOT EXISTS FOR (e:Evidence)   REQUIRE e.pgkey IS UNIQUE;
CREATE CONSTRAINT timeline_pgkey     IF NOT EXISTS FOR (t:TimelineEvent) REQUIRE t.pgkey IS UNIQUE;
CREATE CONSTRAINT actor_uuid         IF NOT EXISTS FOR (a:Actor)      REQUIRE a.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT handle_uuid        IF NOT EXISTS FOR (h:Handle)     REQUIRE h.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT pgp_uuid           IF NOT EXISTS FOR (p:PGPKey)     REQUIRE p.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT wallet_uuid        IF NOT EXISTS FOR (w:Wallet)     REQUIRE w.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT domain_uuid        IF NOT EXISTS FOR (d:Domain)     REQUIRE d.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT infra_uuid         IF NOT EXISTS FOR (i:Infrastructure) REQUIRE i.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT cert_uuid          IF NOT EXISTS FOR (c:Certificate) REQUIRE c.postgres_uuid IS UNIQUE;
CREATE CONSTRAINT evidence_uuid      IF NOT EXISTS FOR (e:Evidence)   REQUIRE e.postgres_uuid IS UNIQUE;

// Lookup indexes for the hot traversal patterns
CREATE INDEX idx_handle_category   IF NOT EXISTS FOR (h:Handle)      ON (h.category);
CREATE INDEX idx_actor_status      IF NOT EXISTS FOR (a:Actor)       ON (a.status);
CREATE INDEX idx_domain_name       IF NOT EXISTS FOR (d:Domain)      ON (d.name);
CREATE INDEX idx_infra_kind        IF NOT EXISTS FOR (i:Infrastructure) ON (i.kind);
CREATE INDEX idx_market_status     IF NOT EXISTS FOR (m:Marketplace) ON (m.status);
CREATE INDEX idx_cert_cn           IF NOT EXISTS FOR (c:Certificate) ON (c.cn);
CREATE INDEX idx_posted       IF NOT EXISTS FOR (p:Post)        ON (p.posted_at);
CREATE INDEX idx_timeline_occurred IF NOT EXISTS FOR (t:TimelineEvent) ON (t.occurred_at);
CREATE INDEX idx_timeline_kind     IF NOT EXISTS FOR (t:TimelineEvent) ON (t.kind);

// ----------------------------------------------------------------------------
// Reference patterns (semantics contract — used by tests & generators)
// ----------------------------------------------------------------------------
// Identity edges:
//   (actor:Actor)-[:USES {first_seen,last_seen}]->(handle:Handle)
//   (actor:Actor)-[:USES]->(alias:Alias)
//   (actor:Actor)-[:USES]->(pgp:PGPKey)
//   (actor:Actor)-[:ASSOCIATED_WITH]->(wallet:Wallet)
//   (actor:Actor)-[:ASSOCIATED_WITH]->(infra:Infrastructure)
//   (actor:Actor)-[:HAS_EVIDENCE]->(e:Evidence)
//
// Content & behavior:
//   (handle:Handle)-[:APPEARS_ON {first_seen,last_seen}]->(m:Marketplace|f:Forum)
//   (handle:Handle)-[:AUTHORED {posted_at}]->(post:Post)
//   (actor:Actor)-[:ACTIVE_DURING]->(t:TimelineEvent)
//
// Infrastructure:
//   (domain:Domain)-[:RESOLVES_TO {record_kind:'A'|'NS'|'MX'}]->(infra:Infrastructure)
//   (domain:Domain)-[:HAS_CERTIFICATE {first_seen}]->(cert:Certificate)
//
// Inference (analyst-reviewable):
//   (actor1:Actor)-[:POSSIBLY_SAME_AS {
//       confidence: Float,         // 0..1
//       band: 'weak'|'low'|'moderate'|'high'|'very_high',
//       status: 'pending'|'accepted'|'rejected'|'uncertain',
//       evidence_ids: [String], scoring_factors: [Map], explanation: String,
//       hypothesis_label: String, engine_ref: String,
//       reviewed_by: String?, reviewed_at: DateTime?,
//       created_at: DateTime, updated_at: DateTime
//   }]->(actor2:Actor)

// Example query the platform guarantees:
// MATCH (a:Actor {code:'ACTOR_ALPHA'})-[:POSSIBLY_SAME_AS]->(b:Actor)
// RETURN b.code, r.confidence, r.band, r.evidence_ids, r.explanation;
