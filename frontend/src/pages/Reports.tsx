/** Reports — investigation report generation and export.

All exported data comes from the actual investigation record.
No fabricated content.
*/
import { useEffect, useState, useCallback } from "react";
import { fetchInvestigations, fetchReport, getReportExportUrl } from "@/api/client";
import type { InvestigationSummary } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";

const SECTION_LABELS: Record<string, string> = {
  investigation: "Investigation",
  targets: "Targets",
  summary: "Summary",
  identifiers: "Identifiers",
  relationships: "Relationships",
  evidence: "Evidence",
  timeline: "Timeline",
  infrastructure: "Infrastructure",
  signals: "Signals",
  confidence: "Confidence",
  analyst_decision: "Analyst Decisions",
  analyst_notes: "Analyst Notes",
  sources: "Sources",
  audit: "Audit Trail",
};

export default function Reports() {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInvestigations(await fetchInvestigations());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  const selectReport = async (code: string) => {
    setSelectedCode(code);
    setReportLoading(true);
    try {
      setReport(await fetchReport(code));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setReportLoading(false);
    }
  };

  if (loading) return <Loading />;
  if (error && !investigations.length)
    return <ErrorState message={error} onRetry={loadList} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Reports & Export</h1>
        <p className="mt-1 text-xs text-slate-500">
          Generate investigation reports from real data · Export as JSON, CSV, or PDF
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="flex gap-4">
        {/* Investigation list */}
        <div className="w-72 shrink-0">
          <div className="sg-panel divide-y divide-line overflow-hidden">
            {investigations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">No investigations</div>
            ) : (
              investigations.map((inv) => (
                <button
                  key={inv.code}
                  onClick={() => selectReport(inv.code)}
                  className={`w-full px-4 py-3 text-left transition-colors ${
                    selectedCode === inv.code
                      ? "bg-teal-700/15 border-l-2 border-l-teal-500"
                      : "hover:bg-panel2/50 border-l-2 border-l-transparent"
                  }`}
                >
                  <span className="text-sm font-medium text-slate-200">{inv.title}</span>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="font-mono-tech text-[10px] text-slate-500">{inv.code}</span>
                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
                      inv.status === "active"
                        ? "border-green-500/30 bg-green-500/15 text-green-400"
                        : "border-slate-500/30 bg-slate-500/15 text-slate-400"
                    }`}>
                      {inv.status}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Report preview */}
        <div className="flex-1">
          {reportLoading ? (
            <Loading label="Generating report…" />
          ) : report ? (
            <ReportPreview report={report} />
          ) : (
            <div className="sg-panel flex flex-col items-center justify-center py-16">
              <p className="text-sm text-slate-400">Select an investigation to generate a report</p>
              <p className="mt-1 text-xs text-slate-600">
                Reports include all sections: targets, relationships, evidence, timeline, confidence, and audit
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportPreview({ report }: { report: Record<string, unknown> }) {
  const inv = report.investigation as Record<string, string> | undefined;
  const targets = (report.targets as Array<Record<string, unknown>>) ?? [];
  const relationships = (report.relationships as Array<Record<string, unknown>>) ?? [];
  const audit = (report.audit as Array<Record<string, unknown>>) ?? [];
  const code = inv?.code ?? "";

  const sections = Object.keys(report).filter(
    (k) => !["report_type", "generated_at", "disclaimer"].includes(k),
  );

  return (
    <div className="space-y-4">
      {/* Header + exports */}
      <div className="sg-panel p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-medium text-slate-200">
              {inv?.title ?? "Report"}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {inv?.code} · Status: {inv?.status} · Lead: {inv?.lead_analyst}
            </p>
            {typeof report.summary === "string" && report.summary && (
              <p className="mt-2 text-xs text-slate-400">{String(report.summary)}</p>
            )}
          </div>
          <div className="flex gap-2">
            {(["json", "csv", "pdf"] as const).map((fmt) => (
              <a
                key={fmt}
                href={getReportExportUrl(code, fmt)}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded bg-teal-600 px-3 py-1.5 text-[11px] text-white hover:bg-teal-500 uppercase"
              >
                {fmt}
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Section overview */}
      <div className="sg-panel p-4">
        <h3 className="mb-2 text-sm font-medium text-slate-300">Report Sections</h3>
        <div className="grid grid-cols-4 gap-2">
          {sections.map((k) => {
            const val = report[k];
            const count = Array.isArray(val) ? val.length : typeof val === "object" && val !== null ? 1 : 0;
            return (
              <div key={k} className="rounded border border-line bg-panel2 px-3 py-2">
                <p className="text-[10px] text-slate-500">{SECTION_LABELS[k] ?? k}</p>
                <p className="font-mono-tech text-xs text-slate-300">
                  {count > 0 ? `${count} item${count !== 1 ? "s" : ""}` : "empty"}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Targets preview */}
      {targets.length > 0 && (
        <div className="sg-panel p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-300">Targets</h3>
          <div className="space-y-2">
            {targets.map((t, i) => (
              <div key={i} className="flex items-center gap-3 rounded border border-line bg-panel2 px-3 py-2">
                <span className="text-sm font-medium text-slate-200">{String(t.code)}</span>
                <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
                  t.risk_level === "critical"
                    ? "border-red-500/30 bg-red-500/15 text-red-400"
                    : t.risk_level === "high"
                    ? "border-orange-500/30 bg-orange-500/15 text-orange-400"
                    : "border-slate-500/30 bg-slate-500/15 text-slate-400"
                }`}>
                  {String(t.risk_level)}
                </span>
                <span className="text-[10px] text-slate-500">{String(t.category)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relationships preview */}
      {relationships.length > 0 && (
        <div className="sg-panel p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-300">Relationships</h3>
          <div className="space-y-2">
            {relationships.map((r, i) => (
              <div key={i} className="rounded border border-line bg-panel2 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">
                    {String(r.from_actor)} ↔ {String(r.to_actor)}
                  </span>
                  <span className="font-mono-tech text-xs text-teal-400">RCS {String(r.confidence)}</span>
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
                    r.status === "accepted"
                      ? "border-green-500/30 bg-green-500/15 text-green-400"
                      : r.status === "rejected"
                      ? "border-red-500/30 bg-red-500/15 text-red-400"
                      : "border-slate-500/30 bg-slate-500/15 text-slate-400"
                  }`}>
                    {String(r.status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Audit trail */}
      {audit.length > 0 && (
        <div className="sg-panel p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-300">Audit Trail</h3>
          <div className="space-y-1">
            {audit.map((a, i) => (
              <div key={i} className="text-[11px] text-slate-500">
                <span className="text-slate-400">{String(a.analyst)}</span>{" "}
                <span className="text-slate-300">{String(a.action).replace(/_/g, " ")}</span>
                <span className="ml-1 text-slate-600">{String(a.occurred_at).slice(11, 19)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      {typeof report.disclaimer === "string" && report.disclaimer && (
        <div className="rounded border border-yellow-500/20 bg-yellow-500/5 px-4 py-3">
          <p className="text-xs text-yellow-400">⚠ {String(report.disclaimer)}</p>
        </div>
      )}
    </div>
  );
}
