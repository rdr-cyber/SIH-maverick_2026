/**
 * TRILOK TRACE API client.
 *
 * All data comes from the real backend.  No mock data, no fake success states.
 * If the backend is unreachable the caller receives an error — the UI renders
 * an error state, not a placeholder.
 */

import { authFetch } from "./auth";
import type {
  ActorDetail,
  ActorStats,
  ActorSummary,
  AuditEvent,
  ConfidenceResult,
  CorrelationResult,
  Evidence,
  HealthResponse,
  InvestigationDetail,
  InvestigationSummary,
  MonitoringOverview,
  MonitoringRelationships,
  MonitoringSource,
  MonitoringTimeline,
  Page,
  RelationshipDetail,
  RelationshipSummary,
} from "./types";

const BASE = "/api/v1";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  // authFetch silently rotates an expired access token via /auth/refresh and
  // retries once, so 401 here means the refresh path also failed — session over.
  const res = await authFetch(path, init);
  if (res.status === 401) {
    // Token expired or invalid — clear and return to Sign In
    const { sessionExpired } = await import("./auth");
    sessionExpired();
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function fetchHealth(): Promise<HealthResponse> {
  return api<HealthResponse>("/health");
}

// ---------------------------------------------------------------------------
// Actors
// ---------------------------------------------------------------------------

export interface ActorListParams {
  q?: string;
  risk_level?: string;
  category?: string;
  status?: string;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export function fetchActors(params: ActorListParams = {}): Promise<Page<ActorSummary>> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const q = qs.toString();
  return api<Page<ActorSummary>>(`/actors${q ? `?${q}` : ""}`);
}

export function fetchActor(ref: string): Promise<ActorDetail> {
  return api<ActorDetail>(`/actors/${encodeURIComponent(ref)}`);
}

export function fetchActorStats(): Promise<ActorStats> {
  return api<ActorStats>("/actors/stats");
}

// ---------------------------------------------------------------------------
// Evidence & Relationships
// ---------------------------------------------------------------------------

export function fetchRelationships(params: {
  kind?: string;
  status?: string;
  min_confidence?: number;
  limit?: number;
  offset?: number;
} = {}): Promise<RelationshipSummary[]> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const q = qs.toString();
  return api<RelationshipSummary[]>(`/evidence/relationships${q ? `?${q}` : ""}`);
}

export function fetchRelationshipDetail(code: string): Promise<RelationshipDetail> {
  return api<RelationshipDetail>(`/evidence/relationships/${encodeURIComponent(code)}`);
}

export function fetchEvidenceItems(params: {
  relationship_id?: string;
  kind?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<Evidence[]> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const q = qs.toString();
  return api<Evidence[]>(`/evidence/items${q ? `?${q}` : ""}`);
}

// ---------------------------------------------------------------------------
// Investigations
// ---------------------------------------------------------------------------

export function fetchInvestigations(params: { status?: string } = {}): Promise<InvestigationSummary[]> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  const q = qs.toString();
  return api<InvestigationSummary[]>(`/investigations${q ? `?${q}` : ""}`);
}

export function fetchInvestigation(code: string): Promise<InvestigationDetail> {
  return api<InvestigationDetail>(`/investigations/${encodeURIComponent(code)}`);
}

export function createInvestigation(body: {
  title: string;
  description: string;
  lead_analyst: string;
  targets?: string[];
  parameters?: Record<string, unknown>;
}): Promise<InvestigationDetail> {
  return api<InvestigationDetail>("/investigations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function activateInvestigation(code: string, analyst: string): Promise<InvestigationDetail> {
  return api<InvestigationDetail>(`/investigations/${encodeURIComponent(code)}/activate?analyst=${analyst}`, {
    method: "POST",
  });
}

export function pauseInvestigation(code: string, analyst: string): Promise<InvestigationDetail> {
  return api<InvestigationDetail>(`/investigations/${encodeURIComponent(code)}/pause?analyst=${analyst}`, {
    method: "POST",
  });
}

export function closeInvestigation(code: string, analyst: string): Promise<InvestigationDetail> {
  return api<InvestigationDetail>(`/investigations/${encodeURIComponent(code)}/close?analyst=${analyst}`, {
    method: "POST",
  });
}

export function addInvestigationNote(code: string, body: { analyst: string; note: string }): Promise<{ ok: boolean }> {
  return api<{ ok: boolean }>(`/investigations/${encodeURIComponent(code)}/notes`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function decideRelationship(body: {
  relationship_id: string;
  decision: "accepted" | "rejected" | "uncertain";
  analyst: string;
  review_note?: string;
}): Promise<{ decision: string; audit_id: number } & Record<string, unknown>> {
  return api(`/investigations/decide`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchAuditLog(params: { resource_type?: string; limit?: number } = {}): Promise<AuditEvent[]> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const q = qs.toString();
  return api<AuditEvent[]>(`/investigations/audit/log${q ? `?${q}` : ""}`);
}

// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

export function fetchMonitoringOverview(): Promise<MonitoringOverview> {
  return api<MonitoringOverview>("/monitoring/overview");
}

export function fetchMonitoringSources(): Promise<MonitoringSource[]> {
  return api<MonitoringSource[]>("/monitoring/sources");
}

export function fetchMonitoringRelationships(): Promise<MonitoringRelationships> {
  return api<MonitoringRelationships>("/monitoring/relationships");
}

export function fetchMonitoringTimeline(): Promise<MonitoringTimeline> {
  return api<MonitoringTimeline>("/monitoring/timeline");
}

// ---------------------------------------------------------------------------
// Correlation & Confidence

export function fetchCorrelation(actorA: string, actorB: string): Promise<CorrelationResult> {
  return api<CorrelationResult>(`/correlation/evaluate?actor_a=${encodeURIComponent(actorA)}&actor_b=${encodeURIComponent(actorB)}`);
}

export function fetchConfidence(actorA: string, actorB: string): Promise<ConfidenceResult> {
  return api<ConfidenceResult>(`/confidence/evaluate?actor_a=${encodeURIComponent(actorA)}&actor_b=${encodeURIComponent(actorB)}`);
}

// ---------------------------------------------------------------------------
// Ingestion
// ---------------------------------------------------------------------------

export interface IngestionResult {
  task_id: string;
  source: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  observations_processed: number;
  entities_extracted: number;
  entities_resolved: number;
  relationships_created: number;
  timeline_events_created: number;
  errors: string[];
  scenario?: string;
}

export interface IngestionProvenance {
  relationship_code: string;
  kind: string;
  from_actor: string;
  to_actor: string;
  confidence: number;
  band: string;
  source: string;
  source_kind: string;
  first_seen: string | null;
  explanation: string | null;
  scoring_factors: Array<{ signal: string; weight: number; score: number; note: string }>;
}

export function runIngestionScan(scenario: string = "all"): Promise<IngestionResult> {
  return api<IngestionResult>(`/ingestion/scan?scenario=${encodeURIComponent(scenario)}`);
}

export function fetchIngestionStatus(limit: number = 10): Promise<IngestionResult[]> {
  return api<IngestionResult[]>(`/ingestion/status?limit=${limit}`);
}

export function fetchIngestionProvenance(params: {
  actor_code?: string;
  limit?: number;
} = {}): Promise<IngestionProvenance[]> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const q = qs.toString();
  return api<IngestionProvenance[]>(`/ingestion/provenance${q ? `?${q}` : ""}`);
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export function fetchReport(code: string): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/reports/${encodeURIComponent(code)}`);
}

export function getReportExportUrl(code: string, format: "json" | "csv" | "pdf"): string {
  return `${BASE}/reports/${encodeURIComponent(code)}/export?format=${format}`;
}
