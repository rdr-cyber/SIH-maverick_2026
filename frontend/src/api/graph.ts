/** Graph API client functions. */

import { authFetch, sessionExpired } from "./auth";

export interface GraphData {
  nodes: Array<{ data: Record<string, unknown> }>;
  edges: Array<{ data: Record<string, unknown> }>;
}

export interface GraphNodeDetail {
  [key: string]: unknown;
}

export interface EdgeEvidence {
  id: string;
  code: string;
  kind: string;
  title: string;
  description: string;
  strength: string;
  evidence_class: string;
  score_contribution: number;
}

/** One weighted signal from the correlation engine (GRAPH_MODEL.md §3). */
export interface ScoringFactor {
  signal: string;
  weight: number;
  score: number;
  note: string;
}

/** Inference-edge metadata (GRAPH_MODEL.md §3: hypothesis, not verdict). */
export interface RelationshipMeta {
  code: string;
  kind: string;
  confidence: number;
  band: string;
  status: string;
  hypothesis_label: string;
  explanation: string;
  scoring_factors: ScoringFactor[];
  evidence_ids: string[];
  ruled_out_summary: string;
  from_code: string;
  to_code: string;
}

/** WHY? payload: relationship inference metadata + its evidence chain. */
export interface EdgeWhyPayload {
  relationship: RelationshipMeta | null;
  evidence: EdgeEvidence[];
}

export async function fetchGraph(params: {
  focus?: string;
  depth?: number;
  max_nodes?: number;
} = {}): Promise<GraphData> {
  const qs = new URLSearchParams();
  if (params.focus) qs.set("focus", params.focus);
  if (params.depth) qs.set("depth", String(params.depth));
  if (params.max_nodes) qs.set("max_nodes", String(params.max_nodes));
  const q = qs.toString();
  const res = await authFetch(`/graph${q ? `?${q}` : ""}`);
  if (res.status === 401) sessionExpired();
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchEdgeWhy(
  source: string,
  target: string,
): Promise<EdgeWhyPayload> {
  const qs = new URLSearchParams({ source, target });
  const res = await authFetch(`/graph/edge/evidence?${qs}`);
  if (res.status === 401) sessionExpired();
  if (!res.ok) throw new Error(`Edge evidence fetch failed: ${res.status}`);
  return res.json();
}
