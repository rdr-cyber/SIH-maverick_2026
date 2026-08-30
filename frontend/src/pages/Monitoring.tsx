/** Monitoring — system status, source scan status, and metrics.

Reports database-derived metrics. Does NOT claim live autonomous collection.
*/
import { useEffect, useState, useCallback } from "react";
import {
  fetchMonitoringOverview,
  fetchMonitoringSources,
  fetchMonitoringRelationships,
} from "@/api/client";
import type {
  MonitoringOverview,
  MonitoringSource,
  MonitoringRelationships,
} from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";

const RELIABILITY_COLOR = (r: number) =>
  r >= 80 ? "text-green-400" : r >= 60 ? "text-yellow-400" : "text-red-400";

const KIND_LABELS: Record<string, string> = {
  marketplace: "Marketplace",
  forum: "Forum",
  paste_site: "Paste Site",
  certificate_archive: "Cert Archive",
  blockchain_indexer: "Chain Indexer",
  dns_archive: "DNS Archive",
};

export default function Monitoring() {
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [sources, setSources] = useState<MonitoringSource[]>([]);
  const [relationships, setRelationships] = useState<MonitoringRelationships | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, src, rel] = await Promise.all([
        fetchMonitoringOverview(),
        fetchMonitoringSources(),
        fetchMonitoringRelationships(),
      ]);
      setOverview(ov);
      setSources(src);
      setRelationships(rel);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loading />;
  if (error && !overview) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">System Monitoring</h1>
        <p className="mt-1 text-xs text-slate-500">
          Database-derived metrics · Not live autonomous collection
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-4 gap-3">
          <MetricCard label="App Mode" value={overview.app_mode} />
          <MetricCard
            label="Last Scan"
            value={overview.last_scan_at ? new Date(overview.last_scan_at).toLocaleDateString() : "Never"}
          />
          <MetricCard
            label="Task Backend"
            value={overview.task_backend.backend}
            sub={overview.task_backend.available ? "Available" : "Unavailable"}
            color={overview.task_backend.available ? "text-green-400" : "text-red-400"}
          />
          <MetricCard
            label="Database"
            value={`${overview.entities.sources} sources`}
            sub={`${overview.entities.actors} actors, ${overview.entities.identifiers} identifiers`}
          />
        </div>
      )}

      {/* Entity counts */}
      {overview && (
        <div className="sg-panel p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Entity Counts</h3>
          <div className="grid grid-cols-7 gap-2">
            {Object.entries(overview.entities).map(([key, val]) => (
              <div key={key} className="text-center">
                <p className="font-mono-tech text-lg text-teal-400">{val}</p>
                <p className="text-[10px] text-slate-500">{key.replace(/_/g, " ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Source status */}
      <div className="sg-panel p-4">
        <h3 className="mb-3 text-sm font-medium text-slate-300">Source Scan Status</h3>
        <div className="space-y-2">
          {sources.map((src) => (
            <div
              key={src.id}
              className="flex items-center gap-4 rounded border border-line bg-panel2 px-3 py-2"
            >
              <div className="w-40">
                <p className="text-sm font-medium text-slate-200">{src.name}</p>
                <p className="text-[10px] text-slate-500">{KIND_LABELS[src.kind] ?? src.kind}</p>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-500">Reliability</span>
                  <div className="h-2 flex-1 rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-teal-600"
                      style={{ width: `${src.reliability}%` }}
                    />
                  </div>
                  <span className={`font-mono-tech text-xs ${RELIABILITY_COLOR(src.reliability)}`}>
                    {src.reliability}
                  </span>
                </div>
              </div>
              <div className="flex gap-4 text-center">
                <div>
                  <p className="font-mono-tech text-xs text-slate-300">{src.actors}</p>
                  <p className="text-[9px] text-slate-600">actors</p>
                </div>
                <div>
                  <p className="font-mono-tech text-xs text-slate-300">{src.personas}</p>
                  <p className="text-[9px] text-slate-600">personas</p>
                </div>
                <div>
                  <p className="font-mono-tech text-xs text-slate-300">{src.identifiers}</p>
                  <p className="text-[9px] text-slate-600">ids</p>
                </div>
              </div>
              <div className="w-32 text-right">
                <p className="text-[10px] text-slate-500">Last scan</p>
                <p className="font-mono-tech text-[11px] text-slate-400">
                  {src.last_scanned_at
                    ? new Date(src.last_scanned_at).toLocaleDateString()
                    : "Never"}
                </p>
              </div>
              <div className="w-16 text-right">
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
                    src.enabled
                      ? "border-green-500/30 bg-green-500/15 text-green-400"
                      : "border-slate-500/30 bg-slate-500/15 text-slate-400"
                  }`}
                >
                  {src.enabled ? "active" : "disabled"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Relationship breakdown */}
      {relationships && (
        <div className="grid grid-cols-2 gap-4">
          <div className="sg-panel p-4">
            <h3 className="mb-3 text-sm font-medium text-slate-300">Relationships by Status</h3>
            <div className="space-y-2">
              {Object.entries(relationships.by_status).map(([status, count]) => (
                <div key={status} className="flex items-center gap-3">
                  <span className="w-24 text-xs text-slate-400">{status}</span>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-teal-600"
                        style={{
                          width: `${(count / Math.max(1, Object.values(relationships.by_status).reduce((a, b) => a + b, 0))) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <span className="font-mono-tech text-xs text-slate-400">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="sg-panel p-4">
            <h3 className="mb-3 text-sm font-medium text-slate-300">Relationships by Band</h3>
            <div className="space-y-2">
              {Object.entries(relationships.by_band).map(([band, count]) => (
                <div key={band} className="flex items-center gap-3">
                  <span className="w-24 text-xs text-slate-400">{band}</span>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-teal-600"
                        style={{
                          width: `${(count / Math.max(1, Object.values(relationships.by_band).reduce((a, b) => a + b, 0))) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <span className="font-mono-tech text-xs text-slate-400">{count}</span>
                </div>
              ))}
            </div>
            {relationships.high_confidence_pending > 0 && (
              <div className="mt-3 rounded border border-yellow-500/20 bg-yellow-500/5 px-3 py-2">
                <p className="text-xs text-yellow-400">
                  {relationships.high_confidence_pending} high-confidence relationship(s) pending analyst review
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      {overview && (
        <div className="rounded border border-slate-600/20 bg-slate-600/5 px-4 py-3">
          <p className="text-xs text-slate-500">ℹ {overview.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="sg-panel p-3">
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className={`mt-0.5 font-mono-tech text-sm ${color ?? "text-slate-200"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[10px] text-slate-600">{sub}</p>}
    </div>
  );
}
