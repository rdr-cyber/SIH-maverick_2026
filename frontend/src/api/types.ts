/** TypeScript types mirroring backend Pydantic response schemas. */

export interface Source {
  id: string;
  name: string;
  kind: string;
  access_method: string;
  trust_level: number;
  last_scanned_at: string | null;
}

export interface Identifier {
  id: string;
  kind: string;
  value: string;
  label: string | null;
  persona_id: string | null;
  attributes: Record<string, unknown>;
  first_seen: string | null;
  last_seen: string | null;
  source: Source | null;
}

export interface Persona {
  id: string;
  name: string;
  platform: string;
  platform_type: string;
  status: string;
  is_primary: boolean;
  reputation: string | null;
  attributes: Record<string, unknown>;
  first_seen: string | null;
  last_seen: string | null;
  source: Source | null;
  identifiers: Identifier[];
}

export interface ActorSummary {
  id: string;
  code: string;
  display_name: string;
  status: string;
  risk_level: string;
  category: string;
  attribution_confidence: number;
  persona_count: number;
  identifier_count: number;
  primary_source: Source | null;
  first_seen: string | null;
  last_seen: string | null;
  last_scan_at: string | null;
}

export interface ActorDetail extends ActorSummary {
  summary: string | null;
  attributes: Record<string, unknown>;
  personas: Persona[];
  identifiers: Identifier[];
}

export interface ActorStats {
  total_actors: number;
  total_personas: number;
  total_identifiers: number;
  total_sources: number;
  by_risk_level: Record<string, number>;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  identifiers_by_kind: Record<string, number>;
  last_scan_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app: string;
  version: string;
  time: string;
  adapters: {
    app_mode: string;
    database: string;
    graph_backend: string;
    task_backend: string;
  };
  checks: Record<string, string>;
}

export interface ScoringFactor {
  signal: string;
  weight: number;
  score: number;
  note: string;
}

export interface CorrelationSignal {
  signal_id: string;
  signal_type: string;
  source_entity: string;
  target_entity: string;
  raw_value: string | number;
  normalized_value: string | number;
  strength: string;
  source: string;
  timestamp: string;
  explanation: string;
  weight: number;
  raw_score: number;
  weighted_score: number;
  evidence_direction: string;
  temporal_decay_factor: number;
  source_reliability: number;
  details: Record<string, unknown>;
}

export interface ConfidenceSignal {
  signal_type: string;
  raw_score: number;
  weight: number;
  source_reliability: number;
  weighted_score: number;
  explanation: string;
  source_name: string;
  evidence_direction: string;
  temporal_decay_factor: number;
  matched_values: Record<string, unknown>;
}

export interface EvidenceQuality {
  source_reliability_avg: number;
  temporal_consistency: string;
  identifier_strength: string;
  supporting_count: number;
  contradicting_count: number;
  neutral_count: number;
  signal_families: number;
  cryptographic_signals: number;
  behavioral_signals: number;
}

export interface CorrelationResult {
  actor_a: string;
  actor_b: string;
  signals: CorrelationSignal[];
  raw_score: number;
  weighted_score: number;
  total_score: number;
  band: string;
  explanation: string;
  hypothesis_label: string;
}

export interface ConfidenceResult {
  actor_a: string;
  actor_b: string;
  score: number;
  band: string;
  raw_score: number;
  weighted_score: number;
  signals: ConfidenceSignal[];
  derivation: string[];
  explanation: string;
  hypothesis_label: string;
  source_reliability_avg: number;
  evidence_quality: EvidenceQuality;
  disclaimer: string;
}

export interface RelationshipSummary {
  id: string;
  code: string;
  kind: string;
  from_type: string;
  from_id: string;
  to_type: string;
  to_id: string;
  from_name: string;
  to_name: string;
  confidence: number;
  band: string;
  status: string;
  explanation: string | null;
  hypothesis_label: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  engine_ref: string | null;
  first_seen: string | null;
  last_seen: string | null;
  scoring_factors: ScoringFactor[];
}

export interface RelationshipDetail extends RelationshipSummary {
  evidence: Evidence[];
  total_evidence_score: number;
}

export interface Evidence {
  id: string;
  code: string;
  kind: string;
  title: string;
  description: string;
  strength: string;
  evidence_class: string;
  score_contribution: number;
  relationship_id: string | null;
  details: Record<string, unknown>;
  status: string;
}

export interface TimelineEvent {
  id: string;
  occurred_at: string;
  kind: string;
  actor_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  title: string;
  detail: string | null;
  confidence_delta: number | null;
  source_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface InvestigationSummary {
  code: string;
  title: string;
  description: string | null;
  status: string;
  lead_analyst: string;
  targets: string[];
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface InvestigationDetail extends InvestigationSummary {
  relationships: InvestigationRelationship[];
}

export interface InvestigationRelationship {
  code: string;
  kind: string;
  from_actor: string;
  to_actor: string;
  confidence: number;
  band: string;
  status: string;
  hypothesis_label: string | null;
  review_note: string | null;
}

export interface AuditEvent {
  id: number;
  action: string;
  analyst: string;
  resource_type: string | null;
  resource_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  note: string | null;
  occurred_at: string;
}

export interface MonitoringOverview {
  app_mode: string;
  entities: {
    sources: number;
    actors: number;
    personas: number;
    identifiers: number;
    relationships: number;
    evidence: number;
    timeline_events: number;
  };
  last_scan_at: string | null;
  task_backend: {
    backend: string;
    available: boolean;
    error?: string;
  };
  disclaimer: string;
}

export interface MonitoringSource {
  id: string;
  name: string;
  kind: string;
  trust_level: number;
  enabled: boolean;
  last_scanned_at: string | null;
  actors: number;
  personas: number;
  identifiers: number;
}

export interface MonitoringRelationships {
  by_status: Record<string, number>;
  by_band: Record<string, number>;
  high_confidence_pending: number;
}

export interface MonitoringTimeline {
  total: number;
  by_kind: Record<string, number>;
  last_event_at: string | null;
}
