import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchActors } from "@/api/client";
import { authHeaders } from "@/api/auth";

const BASE = "/api/v1";

interface TimelineEvent {
  id: string;
  occurred_at: string;
  kind: string;
  actor_id: string | null;
  actor_code: string | null;
  entity_type: string | null;
  entity_id: string | null;
  title: string;
  detail: string | null;
  confidence_delta: number | null;
  metadata: Record<string, unknown>;
}

interface TimelineResponse {
  items: TimelineEvent[];
  total: number;
}

const EVENT_KINDS = [
  "appearance", "pgp_seen", "wallet_associated", "activity",
  "disappearance", "relationship_added", "confidence_changed",
  "alert", "analyst_note",
];

const KIND_ICONS: Record<string, string> = {
  appearance: "👁",
  pgp_seen: "🔑",
  wallet_associated: "💰",
  activity: "📝",
  disappearance: "🚫",
  relationship_added: "🔗",
  confidence_changed: "📊",
  alert: "⚠️",
  analyst_note: "📋",
};

const KIND_COLORS: Record<string, string> = {
  appearance: "border-green-500/40 bg-green-500/5",
  pgp_seen: "border-purple-500/40 bg-purple-500/5",
  wallet_associated: "border-amber-500/40 bg-amber-500/5",
  activity: "border-blue-500/40 bg-blue-500/5",
  disappearance: "border-red-500/40 bg-red-500/5",
  relationship_added: "border-teal-500/40 bg-teal-500/5",
  confidence_changed: "border-yellow-500/40 bg-yellow-500/5",
  alert: "border-orange-500/40 bg-orange-500/5",
  analyst_note: "border-slate-500/40 bg-slate-500/5",
};

export default function Timeline() {
  const [params] = useSearchParams();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);
  const [actorFilter, setActorFilter] = useState(params.get("actor") ?? "");
  const [kindFilter, setKindFilter] = useState("");
  const [actorOptions, setActorOptions] = useState<string[]>([]);

  // Load actor options
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
      if (actorFilter) qs.set("actor", actorFilter);
      if (kindFilter) qs.set("kind", kindFilter);
      qs.set("limit", "100");
      const res = await fetch(`${BASE}/timeline?${qs}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Timeline fetch failed: ${res.status}`);
      const data: TimelineResponse = await res.json();
      setEvents(data.items);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [actorFilter, kindFilter]);

  useEffect(() => { load(); }, [load]);

  // Group events by year
  const byYear: Record<string, TimelineEvent[]> = {};
  for (const ev of events) {
    const year = ev.occurred_at?.slice(0, 4) ?? "Unknown";
    if (!byYear[year]) byYear[year] = [];
    byYear[year].push(ev);
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Timeline</h1>
        <p className="mt-1 text-xs text-slate-500">
          {total} event{total !== 1 ? "s" : ""} · Chronological intelligence view
        </p>
      </div>

      {/* Filters */}
      <div className="mp-panel flex items-center gap-3 p-3">
        <select
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          className="mp-input max-w-[180px]"
        >
          <option value="">All actors</option>
          {actorOptions.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          className="mp-input max-w-[180px]"
        >
          <option value="">All event types</option>
          {EVENT_KINDS.map((k) => (
            <option key={k} value={k}>{k.replace(/_/g, " ")}</option>
          ))}
        </select>
        {(actorFilter || kindFilter) && (
          <button
            onClick={() => { setActorFilter(""); setKindFilter(""); }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Timeline + detail panel */}
      <div className="flex gap-4">
        {/* Timeline list */}
        <div className="flex-1 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-sm text-slate-500">Loading…</div>
          ) : error ? (
            <div className="py-20 text-center text-sm text-red-400">{error}</div>
          ) : events.length === 0 ? (
            <div className="py-20 text-center text-sm text-slate-500">No events found</div>
          ) : (
            Object.entries(byYear).map(([year, yearEvents]) => (
              <div key={year}>
                <div className="mb-2 flex items-center gap-3">
                  <span className="font-mono text-lg font-bold text-slate-400">{year}</span>
                  <div className="h-px flex-1 bg-line" />
                </div>
                <div className="space-y-2 pl-4">
                  {yearEvents.map((ev) => (
                    <button
                      key={ev.id}
                      onClick={() => setSelected(ev)}
                      className={`w-full rounded-md border-l-2 px-4 py-2.5 text-left transition-colors ${
                        selected?.id === ev.id
                          ? "border-l-teal-400 bg-teal-700/10"
                          : `border-l-transparent hover:bg-panel2/50 ${KIND_COLORS[ev.kind] ?? "border-l-slate-600"}`
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 text-sm">{KIND_ICONS[ev.kind] ?? "📌"}</span>
                          <div>
                            <p className="text-sm text-slate-200">{ev.title}</p>
                            {ev.detail && (
                              <p className="mt-0.5 text-xs text-slate-500">{ev.detail}</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {ev.actor_code && (
                            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                              {ev.actor_code}
                            </span>
                          )}
                          <span className="font-mono text-[11px] text-slate-600">
                            {ev.occurred_at?.slice(0, 10)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-80 shrink-0">
            <div className="mp-panel p-4">
              <h3 className="mb-2 text-sm font-medium text-slate-300">Event Detail</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] text-slate-500">Title</p>
                  <p className="text-sm text-slate-200">{selected.title}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Type</p>
                  <p className="text-sm text-slate-300">{KIND_ICONS[selected.kind]} {selected.kind.replace(/_/g, " ")}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Date</p>
                  <p className="font-mono text-sm text-slate-300">{selected.occurred_at?.slice(0, 10)}</p>
                </div>
                {selected.actor_code && (
                  <div>
                    <p className="text-[11px] text-slate-500">Actor</p>
                    <p className="text-sm text-teal-400">{selected.actor_code}</p>
                  </div>
                )}
                {selected.detail && (
                  <div>
                    <p className="text-[11px] text-slate-500">Detail</p>
                    <p className="text-sm text-slate-400">{selected.detail}</p>
                  </div>
                )}
                {selected.confidence_delta != null && (
                  <div>
                    <p className="text-[11px] text-slate-500">Confidence Delta</p>
                    <p className="font-mono text-sm text-yellow-400">{selected.confidence_delta > 0 ? "+" : ""}{selected.confidence_delta}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
