/** Investigation Workspace — analyst-curated investigation views.

Workflow:
  Create → Activate → Explore Evidence → Review → Decide → Close

Decisions are NEVER automatic. The correlation engine proposes,
the analyst disposes.
*/
import { useEffect, useState, useCallback } from "react";
import {
  fetchInvestigations,
  fetchInvestigation,
  activateInvestigation,
  pauseInvestigation,
  closeInvestigation,
  addInvestigationNote,
  decideRelationship,
  fetchAuditLog,
} from "@/api/client";
import type {
  InvestigationSummary,
  InvestigationDetail,
  InvestigationRelationship,
  AuditEvent,
} from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-500/15 text-slate-400 border-slate-500/30",
  active: "bg-green-500/15 text-green-400 border-green-500/30",
  paused: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  closed: "bg-slate-600/15 text-slate-500 border-slate-600/30",
};


export default function InvestigationWorkspace() {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [selected, setSelected] = useState<InvestigationDetail | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noteText, setNoteText] = useState("");
  const [noteLoading, setNoteLoading] = useState(false);
  const [decisionLoading, setDecisionLoading] = useState<string | null>(null);

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

  const loadAudit = useCallback(async () => {
    try {
      setAuditLog(await fetchAuditLog({ limit: 20 }));
    } catch {
      /* best effort */
    }
  }, []);

  useEffect(() => {
    loadList();
    loadAudit();
  }, [loadList, loadAudit]);

  const selectInvestigation = async (code: string) => {
    setDetailLoading(true);
    try {
      setSelected(await fetchInvestigation(code));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusChange = async (code: string, action: "activate" | "pause" | "close") => {
    try {
      const analyst = selected?.lead_analyst ?? "jmartinez";
      let result: InvestigationDetail;
      if (action === "activate") result = await activateInvestigation(code, analyst);
      else if (action === "pause") result = await pauseInvestigation(code, analyst);
      else result = await closeInvestigation(code, analyst);
      setSelected(result);
      setInvestigations((prev) =>
        prev.map((inv) => (inv.code === code ? { ...inv, status: result.status } : inv)),
      );
      loadAudit();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  const handleAddNote = async () => {
    if (!selected || !noteText.trim()) return;
    setNoteLoading(true);
    try {
      await addInvestigationNote(selected.code, {
        analyst: selected.lead_analyst,
        note: noteText.trim(),
      });
      setNoteText("");
      loadAudit();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add note");
    } finally {
      setNoteLoading(false);
    }
  };

  const handleDecision = async (
    rel: InvestigationRelationship,
    decision: "accepted" | "rejected" | "uncertain",
  ) => {
    setDecisionLoading(rel.code);
    try {
      await decideRelationship({
        relationship_id: rel.code,
        decision,
        analyst: selected?.lead_analyst ?? "jmartinez",
        review_note: `${decision} by analyst review`,
      });
      // Refresh the detail
      if (selected) {
        const updated = await fetchInvestigation(selected.code);
        setSelected(updated);
      }
      loadAudit();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to decide");
    } finally {
      setDecisionLoading(null);
    }
  };

  if (loading) return <Loading />;
  if (error && !investigations.length)
    return <ErrorState message={error} onRetry={loadList} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Investigation Workspace</h1>
        <p className="mt-1 text-xs text-slate-500">
          Analyst-curated workspaces · Every decision requires human review
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="flex gap-4">
        {/* Investigation list */}
        <div className="w-80 shrink-0 space-y-3">
          <div className="mp-panel divide-y divide-line overflow-hidden">
            {investigations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">No investigations yet</div>
            ) : (
              investigations.map((inv) => (
                <button
                  key={inv.code}
                  onClick={() => selectInvestigation(inv.code)}
                  className={`w-full px-4 py-3 text-left transition-colors ${
                    selected?.code === inv.code
                      ? "bg-teal-700/15 border-l-2 border-l-teal-500"
                      : "hover:bg-panel2/50 border-l-2 border-l-transparent"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-200">{inv.title}</span>
                    <StatusBadge status={inv.status} />
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-500">{inv.code}</span>
                    <span className="text-[10px] text-slate-600">
                      {inv.targets.join(", ")}
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-slate-600">
                    Lead: {inv.lead_analyst}
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Audit log */}
          <div className="mp-panel p-3">
            <h3 className="mb-2 text-xs font-medium text-slate-400">Recent Audit Trail</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {auditLog.length === 0 ? (
                <p className="text-[10px] text-slate-600">No audit events</p>
              ) : (
                auditLog.map((e) => (
                  <div key={e.id} className="text-[10px] text-slate-500">
                    <span className="text-slate-400">{e.analyst}</span>{" "}
                    <span className="text-slate-300">{e.action.replace(/_/g, " ")}</span>
                    <span className="ml-1 text-slate-600">
                      {e.occurred_at.slice(11, 16)}
                    </span>
                    {e.before && (
                      <div className="ml-2 mt-0.5 text-slate-600">
                        {JSON.stringify(e.before)} → {JSON.stringify(e.after)}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1">
          {detailLoading ? (
            <Loading label="Loading investigation…" />
          ) : selected ? (
            <InvestigationDetailPanel
              detail={selected}
              onStatusChange={handleStatusChange}
              onAddNote={handleAddNote}
              noteText={noteText}
              setNoteText={setNoteText}
              noteLoading={noteLoading}
              onDecision={handleDecision}
              decisionLoading={decisionLoading}
            />
          ) : (
            <div className="mp-panel flex flex-col items-center justify-center py-16">
              <p className="text-sm text-slate-400">Select an investigation</p>
              <p className="mt-1 text-xs text-slate-600">
                Each workspace groups relationships, evidence, and analyst decisions
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
        STATUS_COLORS[status] ?? STATUS_COLORS.draft
      }`}
    >
      {status}
    </span>
  );
}

function InvestigationDetailPanel({
  detail,
  onStatusChange,
  onAddNote,
  noteText,
  setNoteText,
  noteLoading,
  onDecision,
  decisionLoading,
}: {
  detail: InvestigationDetail;
  onStatusChange: (code: string, action: "activate" | "pause" | "close") => void;
  onAddNote: () => void;
  noteText: string;
  setNoteText: (v: string) => void;
  noteLoading: boolean;
  onDecision: (rel: InvestigationRelationship, decision: "accepted" | "rejected" | "uncertain") => void;
  decisionLoading: string | null;
}) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="mp-panel p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-medium text-slate-200">{detail.title}</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {detail.code} · Lead: {detail.lead_analyst}
            </p>
            {detail.description && (
              <p className="mt-1 text-xs text-slate-400">{detail.description}</p>
            )}
          </div>
          <StatusBadge status={detail.status} />
        </div>

        {/* Targets */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {detail.targets.map((t) => (
            <span
              key={t}
              className="rounded bg-teal-500/10 px-2 py-0.5 text-[10px] text-teal-400 border border-teal-500/20"
            >
              {t}
            </span>
          ))}
        </div>

        {/* Status actions */}
        <div className="mt-3 flex gap-2">
          {detail.status === "draft" && (
            <button
              onClick={() => onStatusChange(detail.code, "activate")}
              className="rounded bg-green-600 px-3 py-1 text-[11px] text-white hover:bg-green-500"
            >
              Activate
            </button>
          )}
          {detail.status === "active" && (
            <>
              <button
                onClick={() => onStatusChange(detail.code, "pause")}
                className="rounded bg-yellow-600 px-3 py-1 text-[11px] text-white hover:bg-yellow-500"
              >
                Pause
              </button>
              <button
                onClick={() => onStatusChange(detail.code, "close")}
                className="rounded bg-slate-600 px-3 py-1 text-[11px] text-white hover:bg-slate-500"
              >
                Close
              </button>
            </>
          )}
          {detail.status === "paused" && (
            <>
              <button
                onClick={() => onStatusChange(detail.code, "activate")}
                className="rounded bg-green-600 px-3 py-1 text-[11px] text-white hover:bg-green-500"
              >
                Resume
              </button>
              <button
                onClick={() => onStatusChange(detail.code, "close")}
                className="rounded bg-slate-600 px-3 py-1 text-[11px] text-white hover:bg-slate-500"
              >
                Close
              </button>
            </>
          )}
        </div>
      </div>

      {/* Relationships under review */}
      <div className="mp-panel p-4">
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Relationships ({detail.relationships.length})
        </h3>
        {detail.relationships.length === 0 ? (
          <p className="text-xs text-slate-500">No relationships involving these targets</p>
        ) : (
          <div className="space-y-3">
            {detail.relationships.map((rel) => (
              <div
                key={rel.code}
                className="rounded-md border border-line bg-panel2 p-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">
                        {rel.from_actor} ↔ {rel.to_actor}
                      </span>
                      <RiskBadge value={rel.band} variant="band" />
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {rel.kind} · RCS {rel.confidence} · {rel.code}
                    </p>
                    {rel.hypothesis_label && (
                      <p className="mt-1 text-[11px] text-slate-400 italic">
                        "{rel.hypothesis_label}"
                      </p>
                    )}
                  </div>
                  <StatusBadge status={rel.status} />
                </div>

                {rel.review_note && (
                  <div className="mt-2 rounded border border-yellow-500/20 bg-yellow-500/5 px-2 py-1">
                    <p className="text-[10px] text-yellow-400">{rel.review_note}</p>
                  </div>
                )}

                {/* Decision buttons — only for pending relationships */}
                {rel.status === "pending" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      disabled={decisionLoading === rel.code}
                      onClick={() => onDecision(rel, "accepted")}
                      className="rounded bg-green-600 px-3 py-1 text-[11px] text-white hover:bg-green-500 disabled:opacity-50"
                    >
                      {decisionLoading === rel.code ? "…" : "Accept"}
                    </button>
                    <button
                      disabled={decisionLoading === rel.code}
                      onClick={() => onDecision(rel, "rejected")}
                      className="rounded bg-red-600 px-3 py-1 text-[11px] text-white hover:bg-red-500 disabled:opacity-50"
                    >
                      {decisionLoading === rel.code ? "…" : "Reject"}
                    </button>
                    <button
                      disabled={decisionLoading === rel.code}
                      onClick={() => onDecision(rel, "uncertain")}
                      className="rounded bg-yellow-600 px-3 py-1 text-[11px] text-white hover:bg-yellow-500 disabled:opacity-50"
                    >
                      {decisionLoading === rel.code ? "…" : "Uncertain"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analyst note */}
      <div className="mp-panel p-4">
        <h3 className="mb-2 text-sm font-medium text-slate-300">Add Analyst Note</h3>
        <div className="flex gap-2">
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Add a note to this investigation…"
            className="flex-1 rounded border border-line bg-panel2 px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
            rows={2}
          />
          <button
            onClick={onAddNote}
            disabled={noteLoading || !noteText.trim()}
            className="self-end rounded bg-teal-600 px-3 py-1.5 text-[11px] text-white hover:bg-teal-500 disabled:opacity-50"
          >
            {noteLoading ? "…" : "Add"}
          </button>
        </div>
      </div>

      {/* Safety disclaimer */}
      <div className="rounded border border-yellow-500/20 bg-yellow-500/5 px-4 py-3">
        <p className="text-xs text-yellow-400">
          ⚠ Decisions are analyst-curated. The correlation engine proposes relationships;
          only a human analyst can accept, reject, or mark them uncertain.
          Every decision is recorded in the audit trail.
        </p>
      </div>
    </div>
  );
}
