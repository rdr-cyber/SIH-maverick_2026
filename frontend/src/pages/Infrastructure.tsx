import { useEffect, useState, useCallback } from "react";
import { fetchActors } from "@/api/client";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

interface InfraItem {
  id: string;
  kind: string;
  value: string;
  normalized_value: string;
  label: string | null;
  attributes: Record<string, unknown>;
  first_seen: string | null;
  last_seen: string | null;
  actor_code: string;
  source_name: string | null;
  source_kind: string | null;
  source_reliability: number | null;
}

interface InfraCluster {
  value: string;
  kind: string;
  actor_count: number;
  actors: string[];
}

const KIND_ICONS: Record<string, string> = {
  domain: "🌐",
  onion_service: "🧅",
};

const KIND_COLORS: Record<string, string> = {
  domain: "border-green-500/40 bg-green-500/5",
  onion_service: "border-purple-500/40 bg-purple-500/5",
};

export default function Infrastructure() {
  const [items, setItems] = useState<InfraItem[]>([]);
  const [clusters, setClusters] = useState<InfraCluster[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kindFilter, setKindFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [actorOptions, setActorOptions] = useState<string[]>([]);
  const [selected, setSelected] = useState<InfraItem | null>(null);

  useEffect(() => {
    fetchActors({ limit: 50 }).then((res) => {
      setActorOptions(res.items.map((a) => a.code));
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (kindFilter) qs.set("kind", kindFilter);
      if (actorFilter) qs.set("actor", actorFilter);
      qs.set("limit", "100");

      const [infraRes, clusterRes] = await Promise.all([
        fetch(`${BASE}/infrastructure?${qs}`),
        fetch(`${BASE}/infrastructure/clusters`),
      ]);

      if (!infraRes.ok) throw new Error(`Infrastructure fetch failed: ${infraRes.status}`);
      const infraData = await infraRes.json();
      setItems(infraData.items);
      setTotal(infraData.total);

      if (clusterRes.ok) {
        setClusters(await clusterRes.json());
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [kindFilter, actorFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Infrastructure Intelligence</h1>
        <p className="mt-1 text-xs text-slate-500">
          {total} observation{total !== 1 ? "s" : ""} · Domains, onion services, and shared infrastructure
        </p>
      </div>

      {/* Filters */}
      <div className="sg-panel flex items-center gap-3 p-3">
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          className="sg-input max-w-[160px]"
        >
          <option value="">All types</option>
          <option value="domain">Domains</option>
          <option value="onion_service">Onion Services</option>
        </select>
        <select
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          className="sg-input max-w-[180px]"
        >
          <option value="">All actors</option>
          {actorOptions.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        {(kindFilter || actorFilter) && (
          <button
            onClick={() => { setKindFilter(""); setActorFilter(""); }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex gap-4">
        {/* Infrastructure list */}
        <div className="flex-1">
          {loading ? (
            <div className="py-20 text-center text-sm text-slate-500">Loading…</div>
          ) : error ? (
            <div className="py-20 text-center text-sm text-red-400">{error}</div>
          ) : items.length === 0 ? (
            <div className="py-20 text-center text-sm text-slate-500">No infrastructure observations found</div>
          ) : (
            <div className="sg-panel divide-y divide-line overflow-hidden">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelected(item)}
                  className={`w-full px-4 py-3 text-left transition-colors ${
                    selected?.id === item.id
                      ? "bg-teal-700/10 border-l-2 border-l-teal-400"
                      : `hover:bg-panel2/50 border-l-2 border-l-transparent ${KIND_COLORS[item.kind] ?? ""}`
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-2">
                      <span className="mt-0.5 text-sm">{KIND_ICONS[item.kind] ?? "📌"}</span>
                      <div>
                        <p className="font-mono-tech text-sm text-slate-200">{item.value}</p>
                        {item.label && (
                          <p className="mt-0.5 text-xs text-slate-500">{item.label}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                        {item.actor_code}
                      </span>
                      <span className="text-[10px] text-slate-600">{item.source_name}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-80 shrink-0">
            <div className="sg-panel p-4">
              <h3 className="mb-2 text-sm font-medium text-slate-300">Observation Detail</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] text-slate-500">Value</p>
                  <p className="font-mono-tech text-sm text-slate-200">{selected.value}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Type</p>
                  <p className="text-sm text-slate-300">{KIND_ICONS[selected.kind]} {selected.kind.replace(/_/g, " ")}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Actor</p>
                  <p className="text-sm text-teal-400">{selected.actor_code}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Source</p>
                  <p className="text-sm text-slate-300">{selected.source_name}</p>
                  <p className="text-[10px] text-slate-600">
                    Reliability: {selected.source_reliability}/100 · {selected.source_kind}
                  </p>
                </div>
                {selected.first_seen && (
                  <div>
                    <p className="text-[11px] text-slate-500">First Seen</p>
                    <p className="font-mono-tech text-sm text-slate-300">{selected.first_seen.slice(0, 10)}</p>
                  </div>
                )}
                {selected.last_seen && (
                  <div>
                    <p className="text-[11px] text-slate-500">Last Seen</p>
                    <p className="font-mono-tech text-sm text-slate-300">{selected.last_seen.slice(0, 10)}</p>
                  </div>
                )}
                {Object.keys(selected.attributes).length > 0 && (
                  <div>
                    <p className="text-[11px] text-slate-500">Attributes</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(selected.attributes).map(([k, v]) => (
                        <span key={k} className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Shared infrastructure clusters */}
      {clusters.length > 0 && (
        <div className="sg-panel p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Shared Infrastructure</h2>
          <p className="mb-3 text-xs text-slate-500">
            Infrastructure shared by multiple actors — key intelligence signal
          </p>
          <div className="space-y-2">
            {clusters.map((cl, i) => (
              <div key={i} className="rounded-md border border-line bg-panel2 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono-tech text-sm text-slate-200">{cl.value}</span>
                  <span className="text-xs text-slate-500">
                    {cl.actor_count} actors: {cl.actors.join(", ")}
                  </span>
                </div>
                <span className="text-[10px] text-slate-600">{cl.kind.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
