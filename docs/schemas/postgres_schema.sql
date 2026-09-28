-- ============================================================================
-- TRILOK TRACE — PostgreSQL canonical schema (Phase 1 artifact)
-- Problem Statement ID 26151 · NTRO · SIH 2026
-- System of record for all intelligence facts, evidence, and review state.
-- Mirrors: DATABASE.md · Consumed by: SQLAlchemy models (Phase 2)
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS citext;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- 1. Sources (provenance root)
-- ----------------------------------------------------------------------------
CREATE TABLE sources (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL, -- marketplace | forum | certificate_archive | dns_archive | blockchain_indexer
    access_method TEXT NOT NULL CHECK (
        access_method IN ('synthetic', 'authorized', 'public')
    ),
    trust_level SMALLINT NOT NULL DEFAULT 50 CHECK (trust_level BETWEEN 0 AND 100),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

-- ----------------------------------------------------------------------------
-- 2. Core identity entities
-- ----------------------------------------------------------------------------
CREATE TABLE actors (
    id UUID PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- ACTOR_ALPHA
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'tracked' CHECK (status IN ('tracked', 'archived', 'merged_into')),
    merged_into_id UUID REFERENCES actors (id) ON DELETE SET NULL,
    risk_level TEXT NOT NULL DEFAULT 'moderate' CHECK (
        risk_level IN ('low', 'moderate', 'high', 'critical')
    ),
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    source_id UUID REFERENCES sources (id),
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

CREATE TABLE handles (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES sources (id) ON DELETE RESTRICT,
    value TEXT NOT NULL,
    normalized TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    platform_id UUID, -- resolved at ingest (forum/marketplace)
    platform_type TEXT CHECK (platform_type IN ('marketplace', 'forum', NULL)),
    category TEXT NOT NULL DEFAULT 'other' CHECK (
        category IN ('marketplace', 'forum', 'paste', 'other')
    ),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

CREATE UNIQUE INDEX uq_handles_key ON handles (normalized_key);

CREATE INDEX idx_handles_platform ON handles (platform_id);

CREATE TABLE aliases (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES sources (id) ON DELETE RESTRICT,
    value TEXT NOT NULL,
    normalized TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'nickname',
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

CREATE UNIQUE INDEX uq_aliases_key ON aliases (normalized_key);

CREATE TABLE pgp_keys (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES sources (id) ON DELETE RESTRICT,
    fingerprint TEXT NOT NULL, -- 40 hex chars
    normalized_key TEXT NOT NULL, -- UPPER(fingerprint)
    key_id TEXT,
    user_id TEXT,
    algorithm TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

CREATE UNIQUE INDEX uq_pgp_keys_key ON pgp_keys (normalized_key);

CREATE TABLE wallets (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES sources (id) ON DELETE RESTRICT,
    address TEXT NOT NULL,
    normalized_key TEXT NOT NULL, -- chain+':'+checksummed
    chain TEXT NOT NULL CHECK (chain IN ('btc', 'xmr', 'eth')),
    address_type TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now ()
);

CREATE UNIQUE INDEX uq_wallets_key ON wallets (normalized_key);-- ----------------------------------------------------------------------------
-- 3. Infrastructure entities (synthetic / authorized metadata only)
-- ----------------------------------------------------------------------------
CREATE TABLE domains (
    id                UUID PRIMARY KEY,
    source_id         UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    name              TEXT NOT NULL,             -- normalized: punycode, no trailing dot
    normalized_key    TEXT NOT NULL,
    registrar         TEXT,
    registration_date TIMESTAMPTZ,
    expiration_date   TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','parked','expired')),
    first_seen        TIMESTAMPTZ,
    last_seen         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_domains_key ON domains (normalized_key);

CREATE TABLE infrastructure (
    id            UUID PRIMARY KEY,
    source_id     UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    kind          TEXT NOT NULL CHECK (kind IN ('ip','asn','server','shared_host','netblock')),
    value         TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    organization  TEXT,
    country       TEXT,
    first_seen    TIMESTAMPTZ,
    last_seen     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_infrastructure_key ON infrastructure (normalized_key);

CREATE TABLE certificate_metadata (
    id               UUID PRIMARY KEY,
    source_id        UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    serial           TEXT NOT NULL,
    normalized_key   TEXT NOT NULL,              -- sha256(serial|issuer)
    cn               TEXT,
    san              JSONB NOT NULL DEFAULT '[]',
    issuer           TEXT,
    not_before       TIMESTAMPTZ,
    not_after        TIMESTAMPTZ,
    fingerprint_sha256 TEXT,
    first_seen       TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_certificate_key ON certificate_metadata (normalized_key);

-- ----------------------------------------------------------------------------
-- 4. Platforms & content
-- ----------------------------------------------------------------------------
CREATE TABLE marketplaces (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    codename    TEXT,
    status      TEXT NOT NULL DEFAULT 'operating' CHECK (status IN ('operating','seized','offline')),
    domain_id   UUID REFERENCES domains(id),
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE forums (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    codename    TEXT,
    status      TEXT NOT NULL DEFAULT 'operating' CHECK (status IN ('operating','seized','offline')),
    category    TEXT,
    domain_id   UUID REFERENCES domains(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE posts (
    id             UUID PRIMARY KEY,
    external_id    TEXT NOT NULL,
    platform_id    UUID NOT NULL,                -- forums.id or marketplaces.id
    platform_type  TEXT NOT NULL CHECK (platform_type IN ('marketplace','forum')),
    author_handle_id UUID REFERENCES handles(id) ON DELETE SET NULL,
    author_raw     TEXT,
    title          TEXT,
    body           TEXT,
    posted_at      TIMESTAMPTZ NOT NULL,
    language       TEXT NOT NULL DEFAULT 'en',
    source_id      UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    first_seen     TIMESTAMPTZ,
    last_seen      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_posts_external ON posts (source_id, platform_id, external_id);
CREATE        INDEX idx_posts_handle   ON posts (author_handle_id);
CREATE        INDEX idx_posts_posted   ON posts (posted_at);
-- ----------------------------------------------------------------------------
-- 5. Observations, evidence, relationships
-- ----------------------------------------------------------------------------
CREATE TABLE observations (
    id           UUID PRIMARY KEY,
    source_id    UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    kind         TEXT NOT NULL,         -- handle_seen | pgp_seen | wallet_transfer | post_created | cert_observed | dns_observed | domain_registered | infra_seen | persona_migration | custom
    subject_type TEXT NOT NULL,
    subject_id   UUID NOT NULL,
    occurred_at  TIMESTAMPTZ NOT NULL,
    details      JSONB NOT NULL DEFAULT '{}',
    raw          TEXT,
    first_seen   TIMESTAMPTZ,
    last_seen    TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_observation UNIQUE (source_id, kind, subject_id, occurred_at)
);
CREATE INDEX idx_observations_subject   ON observations (subject_type, subject_id);
CREATE INDEX idx_observations_occurred  ON observations (occurred_at);

CREATE TABLE evidence (
    id                 UUID PRIMARY KEY,
    code               TEXT NOT NULL UNIQUE,     -- EVID-0001
    kind               TEXT NOT NULL,            -- pgp_match | wallet_match | handle_match | stylometric_similarity | behavior_similarity | infrastructure_reuse | temporal_proximity | analyst_observation
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    strength           TEXT NOT NULL CHECK (strength IN ('weak','moderate','strong')),
    class              TEXT NOT NULL CHECK (class IN ('OBSERVED_FACT','DERIVED_SIGNAL','CORRELATION','ANALYST_HYPOTHESIS')),
    score_contribution NUMERIC(5,2) NOT NULL DEFAULT 0,
    source_id          UUID REFERENCES sources(id),
    observation_ids    UUID[] NOT NULL DEFAULT '{}',
    relationship_id    UUID,
    status             TEXT NOT NULL DEFAULT 'valid' CHECK (status IN ('valid','superseded','contested')),
    details            JSONB NOT NULL DEFAULT '{}',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_relationship ON evidence (relationship_id);
CREATE INDEX idx_evidence_kind         ON evidence (kind);

CREATE TABLE relationships (
    id               UUID PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,       -- REL-0001
    kind             TEXT NOT NULL,              -- POSSIBLY_SAME_AS | USES | ASSOCIATED_WITH | APPEARS_ON | AUTHORED | RESOLVES_TO | HAS_CERTIFICATE | HAS_EVIDENCE | ACTIVE_DURING
    source_id        UUID REFERENCES sources(id),
    engine_ref       TEXT,                       -- correlation_engine | analyst | ingestion
    from_type        TEXT NOT NULL,
    from_id          UUID NOT NULL,
    to_type          TEXT NOT NULL,
    to_id            UUID NOT NULL,
    confidence       NUMERIC(5,2) NOT NULL DEFAULT 0,
    band             TEXT NOT NULL DEFAULT 'weak' CHECK (band IN ('weak','low','moderate','high','very_high')),
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected','uncertain')),
    hypothesis_label TEXT,
    evidence_ids     UUID[] NOT NULL DEFAULT '{}',
    scoring_factors  JSONB NOT NULL DEFAULT '[]', -- [{signal, weight, score, note}]
    explanation      TEXT,
    ruled_out_summary TEXT,
    created_by       UUID,
    reviewed_by      UUID,
    reviewed_at      TIMESTAMPTZ,
    review_note      TEXT,
    first_seen       TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_relationships_status_confidence ON relationships (status, confidence);
CREATE INDEX idx_relationships_from            ON relationships (from_type, from_id);
CREATE INDEX idx_relationships_to              ON relationships (to_type, to_id);

CREATE TABLE relationship_observations (
    relationship_id UUID NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    observation_id  UUID NOT NULL REFERENCES observations(id)  ON DELETE CASCADE,
    PRIMARY KEY (relationship_id, observation_id)
);

-- ----------------------------------------------------------------------------
-- 6. Timeline
-- ----------------------------------------------------------------------------
CREATE TABLE timeline_events (
    id              UUID PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL,
    kind            TEXT NOT NULL,      -- appearance | pgp_seen | wallet_associated | activity | migration | disappearance | relationship_added | confidence_changed | alert | analyst_note
    actor_id        UUID REFERENCES actors(id) ON DELETE SET NULL,
    entity_type     TEXT,
    entity_id       UUID,
    title           TEXT NOT NULL,
    detail          TEXT,
    confidence_delta NUMERIC(5,2),
    source_id       UUID REFERENCES sources(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_timeline_actor  ON timeline_events (actor_id, occurred_at);
CREATE INDEX idx_timeline_occurred ON timeline_events (occurred_at);
-- ----------------------------------------------------------------------------
-- 7. Profiles (behavior & stylometry)
-- ----------------------------------------------------------------------------
CREATE TABLE behavior_profiles (
    id             UUID PRIMARY KEY,
    actor_id       UUID NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    handle_id      UUID REFERENCES handles(id) ON DELETE SET NULL,
    frequency_mean NUMERIC(10,4),
    interval_mean  INTERVAL,
    hour_histogram NUMERIC[] NOT NULL DEFAULT '{}',
    weekday_histogram NUMERIC[] NOT NULL DEFAULT '{}',
    lifecycle      JSONB NOT NULL DEFAULT '{}',   -- {first_seen, last_seen, active_days, gaps}
    migrations     JSONB NOT NULL DEFAULT '[]',
    raw_vector     JSONB NOT NULL DEFAULT '{}',
    source_id      UUID REFERENCES sources(id),
    computed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_behavior_actor ON behavior_profiles (actor_id);

CREATE TABLE stylometric_profiles (
    id                 UUID PRIMARY KEY,
    actor_id           UUID NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    handle_id          UUID REFERENCES handles(id) ON DELETE SET NULL,
    corpus_size        INT NOT NULL DEFAULT 0,
    avg_sentence_len   NUMERIC(8,3),
    ttr                NUMERIC(8,5),
    char_ngram_vector  JSONB NOT NULL DEFAULT '{}',
    word_ngram_vector  JSONB NOT NULL DEFAULT '{}',
    function_word_rates JSONB NOT NULL DEFAULT '{}',
    punctuation_rates  JSONB NOT NULL DEFAULT '{}',
    repeated_phrases   JSONB NOT NULL DEFAULT '[]',
    top_features       JSONB NOT NULL DEFAULT '[]',
    source_id          UUID REFERENCES sources(id),
    computed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stylo_actor ON stylometric_profiles (actor_id);

-- ----------------------------------------------------------------------------
-- 8. Investigations & analysts
-- ----------------------------------------------------------------------------
CREATE TABLE analysts (
    id                 UUID PRIMARY KEY,
    username           CITEXT NOT NULL UNIQUE,
    full_name          TEXT NOT NULL,
    email              CITEXT NOT NULL UNIQUE,
    password_hash      TEXT NOT NULL,
    role               TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst','senior_analyst','admin')),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investigations (
    id            UUID PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,          -- INV-0001
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused','closed')),
    lead_analyst_id UUID NOT NULL REFERENCES analysts(id),
    participants  UUID[] NOT NULL DEFAULT '{}',
    targets       JSONB NOT NULL DEFAULT '[]',
    parameters    JSONB NOT NULL DEFAULT '{}',   -- correlation weights overlay
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_investigations_status ON investigations (status);

CREATE TABLE investigation_notes (
    id              UUID PRIMARY KEY,
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    analyst_id      UUID NOT NULL REFERENCES analysts(id),
    body            TEXT NOT NULL,
    visibility      TEXT NOT NULL DEFAULT 'team' CHECK (visibility IN ('team','private')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 9. Graph sync bookkeeping
-- ----------------------------------------------------------------------------
CREATE TABLE graph_sync_state (
    entity_type TEXT NOT NULL,
    entity_id   UUID NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending' CHECK (sync_status IN ('pending','synced','failed')),
    last_error  TEXT,
    attempts    INT NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_type, entity_id)
);

-- ----------------------------------------------------------------------------
-- 10. Operations: scans, alerts, reports
-- ----------------------------------------------------------------------------
CREATE TABLE scan_jobs (
    id                       UUID PRIMARY KEY,
    code                     TEXT NOT NULL UNIQUE,
    kind                     TEXT NOT NULL DEFAULT 'autonomous' CHECK (kind IN ('autonomous','demo_run','manual')),
    status                   TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed')),
    started_at               TIMESTAMPTZ,
    finished_at              TIMESTAMPTZ,
    sources_processed        INT NOT NULL DEFAULT 0,
    new_artifacts            INT NOT NULL DEFAULT 0,
    new_identifiers          INT NOT NULL DEFAULT 0,
    new_relationships        INT NOT NULL DEFAULT 0,
    high_confidence_relationships INT NOT NULL DEFAULT 0,
    errors                   JSONB NOT NULL DEFAULT '[]',
    batch_id                 UUID,
    trigger                  TEXT NOT NULL DEFAULT 'beat' CHECK (trigger IN ('beat','api','demo')),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_scan_jobs_status ON scan_jobs (status, created_at);

CREATE TABLE alerts (
    id               UUID PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    kind             TEXT NOT NULL,              -- new_high_confidence | new_handle_seen | persona_migration | new_evidence | system
    severity         TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','low','medium','high')),
    title            TEXT NOT NULL,
    body             TEXT,
    actor_id         UUID REFERENCES actors(id),
    relationship_id  UUID REFERENCES relationships(id),
    source_id        UUID REFERENCES sources(id),
    acknowledged_by  UUID,
    acknowledged_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_created ON alerts (created_at);

CREATE TABLE reports (
    id               UUID PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL CHECK (kind IN ('pdf','csv','json')),
    status           TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','generating','ready','failed')),
    storage_key      TEXT,                        -- e.g. reports/INV-0001/RPT-001.json
    filters          JSONB NOT NULL DEFAULT '{}',
    generated_by     UUID NOT NULL REFERENCES analysts(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 11. Audit log (append-only by convention)
-- ----------------------------------------------------------------------------
CREATE TABLE audit_events (
    id            BIGSERIAL PRIMARY KEY,
    analyst_id    UUID,
    is_system     BOOLEAN NOT NULL DEFAULT FALSE,
    action        TEXT NOT NULL,                  -- auth.login | rel.accept | investigation.create | scan.tick ...
    resource_type TEXT,
    resource_id   UUID,
    before        JSONB,
    after         JSONB,
    ip            TEXT,
    user_agent    TEXT,
    note          TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_occurred  ON audit_events (occurred_at);
CREATE INDEX idx_audit_analyst   ON audit_events (analyst_id);
CREATE INDEX idx_audit_resource  ON audit_events (resource_type, resource_id);

-- ----------------------------------------------------------------------------
-- 12. updated_at trigger helper
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['sources','actors','handles','aliases','pgp_keys','wallets',
        'domains','infrastructure','certificate_metadata','marketplaces','forums','posts',
        'observations','evidence','relationships','behavior_profiles','stylometric_profiles',
        'analysts','investigations','investigation_notes','reports']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                        FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;
