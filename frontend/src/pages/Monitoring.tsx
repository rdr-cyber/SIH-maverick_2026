/** Monitoring — system status, source scan status, and metrics.

Reports database-derived metrics. Does NOT claim live autonomous collection.
*/
import { useEffect, useState, useCallback } from "react";
import {
  fetchMonitoringOverview,
  fetchMonitoringSources,
  fetchMonitoringRelationships,
  runIngestionScan,
  fetchIngestionStatus,
  type IngestionResult,
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
  const [ingestionResults, setIngestionResults] = useState<IngestionResult[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanScenario, setScanScenario] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, src, rel, ing] = await Promise.all([
        fetchMonitoringOverview(),
        fetchMonitoringSources(),
        fetchMonitoringRelationships(),
        fetchIngestionStatus(5),
      ]);
      setOverview(ov);
      setSources(src);
      setRelationships(rel);
      setIngestionResults(ing);
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
        <div className="mp-panel p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Entity Counts</h3>
          <div className="grid grid-cols-7 gap-2">
            {Object.entries(overview.entities).map(([key, val]) => (
              <div key={key} className="text-center">
                <p className="font-mono text-lg text-teal-400">{val}</p>
                <p className="text-[10px] text-slate-500">{key.replace(/_/g, " ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Source status */}
      <div className="mp-panel p-4">
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
                  <span className="text-[10px] text-slate-500">Trust level</span>
                  <div className="h-2 flex-1 rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-teal-600"
                      style={{ width: `${src.trust_level}%` }}
                    />
                  </div>
                  <span className={`font-mono text-xs ${RELIABILITY_COLOR(src.trust_level)}`}>
                    {src.trust_level}
                  </span>
                </div>
              </div>
              <div className="flex gap-4 text-center">
                <div>
                  <p className="font-mono text-xs text-slate-300">{src.actors}</p>
                  <p className="text-[9px] text-slate-600">actors</p>
                </div>
                <div>
                  <p className="font-mono text-xs text-slate-300">{src.personas}</p>
                  <p className="text-[9px] text-slate-600">personas</p>
                </div>
                <div>
                  <p className="font-mono text-xs text-slate-300">{src.identifiers}</p>
                  <p className="text-[9px] text-slate-600">ids</p>
                </div>
              </div>
              <div className="w-32 text-right">
                <p className="text-[10px] text-slate-500">Last scan</p>
                <p className="font-mono text-[11px] text-slate-400">
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
          <div className="mp-panel p-4">
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
                  <span className="font-mono text-xs text-slate-400">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mp-panel p-4">
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
                  <span className="font-mono text-xs text-slate-400">{count}</span>
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

      {/* Ingestion Pipeline */}
      <div className="mp-panel p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-slate-300">Data Ingestion Pipeline</h3>
            <p className="text-[10px] text-slate-500">
              Run synthetic fixtures through the real extraction → resolution → correlation pipeline
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={scanScenario}
              onChange={(e) => setScanScenario(e.target.value)}
              className="rounded border border-line bg-panel2 px-2 py-1 text-xs text-slate-300"
              disabled={scanning}
            >
              <option value="all">All Scenarios</option>
              <option value="darkmerchant">DarkMerchant</option>
              <option value="launderpipe">LaunderPipe</option>
              <option value="pharmakon">Pharmakon</option>
            </select>
            <button
              onClick={async () => {
                setScanning(true);
                try {
                  const result = await runIngestionScan(scanScenario);
                  setIngestionResults((prev) => [result, ...prev].slice(0, 10));
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Scan failed");
                } finally {
                  setScanning(false);
                }
              }}
              disabled={scanning}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                scanning
                  ? "cursor-not-allowed border border-slate-600/30 bg-slate-600/15 text-slate-500"
                  : "border border-teal-500/30 bg-teal-500/15 text-teal-400 hover:bg-teal-500/25"
              }`}
            >
              {scanning ? "⏳ Scanning…" : "▶ Run Synthetic Scan"}
            </button>
          </div>
        </div>

        {/* Recent scan results */}
        {ingestionResults.length > 0 && (
          <div className="space-y-2">
            {ingestionResults.map((result, idx) => (
              <div
                key={`${result.task_id}-${idx}`}
                className="rounded border border-line bg-panel2 px-3 py-2"
              >
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
                          result.status === "completed"
                            ? "border-green-500/30 bg-green-500/15 text-green-400"
                            : result.status === "failed"
                              ? "border-red-500/30 bg-red-500/15 text-red-400"
                              : "border-yellow-500/30 bg-yellow-500/15 text-yellow-400"
                        }`}
                      >
                        {result.status}
                      </span>
                      <span className="text-xs text-slate-300">{result.source}</span>
                      {result.scenario && (
                        <span className="text-[10px] text-slate-500">({result.scenario})</span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-4 text-center">
                    <div>
                      <p className="font-mono text-xs text-slate-300">{result.observations_processed}</p>
                      <p className="text-[9px] text-slate-600">obs</p>
                    </div>
                    <div>
                      <p className="font-mono text-xs text-slate-300">{result.entities_extracted}</p>
                      <p className="text-[9px] text-slate-600">extracted</p>
                    </div>
                    <div>
                      <p className="font-mono text-xs text-slate-300">{result.entities_resolved}</p>
                      <p className="text-[9px] text-slate-600">resolved</p>
                    </div>
                    <div>
                      <p className="font-mono text-xs text-teal-400">{result.relationships_created}</p>
                      <p className="text-[9px] text-slate-600">rels</p>
                    </div>
                  </div>
                  {result.completed_at && (
                    <div className="w-32 text-right">
                      <p className="text-[10px] text-slate-500">Completed</p>
                      <p className="font-mono text-[11px] text-slate-400">
                        {new Date(result.completed_at).toLocaleTimeString()}
                      </p>
                    </div>
                  )}
                </div>
                {result.errors.length > 0 && (
                  <div className="mt-1">
                    {result.errors.map((err, i) => (
                      <p key={i} className="text-[10px] text-red-400">⚠ {err}</p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

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
    <div className="mp-panel p-3">
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className={`mt-0.5 font-mono text-sm ${color ?? "text-slate-200"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[10px] text-slate-600">{sub}</p>}
    </div>
  );
}
