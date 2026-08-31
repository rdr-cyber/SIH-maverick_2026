/** Graph API client functions. */

const BASE = "/api/v1";

export interface GraphData {
  nodes: Array<{ data: Record<string, unknown> }>;
  edges: Array<{ data: Record<string, unknown> }>;
}

export interface GraphNodeDetail {
  [key: string]: unknown;
}

export interface EdgeEvidence {
  code: string;
  kind: string;
  title: string;
  description: string;
  strength: string;
  evidence_class: string;
  score_contribution: number;
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
  const res = await fetch(`${BASE}/graph${q ? `?${q}` : ""}`);
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchEdgeEvidence(
  source: string,
  target: string,
): Promise<EdgeEvidence[]> {
  const qs = new URLSearchParams({ source, target });
  const res = await fetch(`${BASE}/graph/edge/evidence?${qs}`);
  if (!res.ok) throw new Error(`Edge evidence fetch failed: ${res.status}`);
  return res.json();
}
