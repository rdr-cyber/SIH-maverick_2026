/** Map API client functions. */

import { authFetch, sessionExpired } from "./auth";

export interface MapPin {
  code: string;
  display_name: string;
  lat: number;
  lng: number;
  label: string | null;
  role: string | null;
  risk_level: string;
  category: string;
  status: string;
  confidence: number;
}

export interface MapEdge {
  code: string;
  kind: string;
  from_code: string;
  to_code: string;
  confidence: number;
  band: string;
  status: string;
  hypothesis_label: string;
}

export interface MapData {
  pins: MapPin[];
  edges: MapEdge[];
  roles: Record<string, number>;
  unlocated: string[];
}

export async function fetchMap(): Promise<MapData> {
  const res = await authFetch("/map");
  if (res.status === 401) sessionExpired();
  if (!res.ok) throw new Error(`Map fetch failed: ${res.status}`);
  return res.json();
}
