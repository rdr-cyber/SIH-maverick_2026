import { useEffect, useState, useCallback } from "react";
import { fetchRelationships, fetchRelationshipDetail, fetchConfidence } from "@/api/client";
import type { ConfidenceResult, RelationshipDetail, RelationshipSummary } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

const CLASS_LABELS: Record<string, { label: string; color: string }> = {
  OBSERVED_FACT: { label: "Observed Fact", color: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  DERIVED_SIGNAL: { label: "Derived Signal", color: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
  CORRELATION: { label: "Correlation", color: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  ANALYST_HYPOTHESIS: { label: "Analyst Hypothesis", color: "bg-teal-500/15 text-teal-400 border-teal-500/30" },
};

const STRENGTH_COLORS: Record<string, string> = {
  strong: "text-green-400",
  moderate: "text-yellow-400",
  weak: "text-slate-400",
};



export default function Evidence() {
  const [relationships, setRelationships] = useState<RelationshipSummary[]>([]);
  const [selected, setSelected] = useState<RelationshipDetail | null>(null);
  const [confidence, setConfidence] = useState<ConfidenceResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRelationships = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRelationships(await fetchRelationships());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRelationships(); }, [loadRelationships]);

  const selectRelationship = async (code: string) => {
    setDetailLoading(true);
    setConfidence(null);
    try {
      const detail = await fetchRelationshipDetail(code);
      setSelected(detail);
      // Fetch confidence explanation for this pair
      try {
        const conf = await fetchConfidence(detail.from_name, detail.to_name);
        setConfidence(conf);
      } catch {
        // Confidence endpoint may fail for some pairs — that's OK
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) return <Loading />;
  if (error && !relationships.length) return <ErrorState message={error} onRetry={loadRelationships} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Evidence Explorer</h1>
        <p className="mt-1 text-xs text-slate-500">
          Trace the supporting facts behind every inference · Never presented as confirmed identity
        </p>
      </div>

      <div className="flex gap-4">
        {/* Relationship list */}
        <div className="w-80 shrink-0">
          <div className="mp-panel divide-y divide-line overflow-hidden">
            {relationships.map((rel) => (
              <button
                key={rel.code}
                onClick={() => selectRelationship(rel.code)}
                className={`w-full px-4 py-3 text-left transition-colors ${
                  selected?.code === rel.code
                    ? "bg-teal-700/15 border-l-2 border-l-teal-500"
                    : "hover:bg-panel2/50 border-l-2 border-l-transparent"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-200">
                    {rel.from_name} → {rel.to_name}
                  </span>
                  <RiskBadge value={rel.band} variant="band" />
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">
                    RCS {rel.confidence}
                  </span>
                  <RiskBadge value={rel.status} variant="status" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* WHY panel */}
        <div className="flex-1">
          {detailLoading ? (
            <Loading label="Loading evidence…" />
          ) : selected ? (
            <WhyPanel detail={selected} confidence={confidence} />
          ) : (
            <div className="mp-panel flex flex-col items-center justify-center py-16">
              <p className="text-sm text-slate-400">Select a relationship to see WHY</p>
              <p className="mt-1 text-xs text-slate-600">
                Every edge carries evidence, scoring factors, and a human-readable explanation
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** The WHY panel: shows evidence chain and confidence breakdown for a selected relationship. */
function WhyPanel({ detail, confidence }: { detail: RelationshipDetail; confidence: ConfidenceResult | null }) {
  const eq = confidence?.evidence_quality;

  return (
    <div className="space-y-4">
      {/* Header with raw vs final score */}
      <div className="mp-panel p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-medium text-slate-200">
              {detail.from_name} ↔ {detail.to_name}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {detail.kind.replace(/_/g, " ")} · {detail.code}
            </p>
            {detail.hypothesis_label && (
              <p className="mt-1 text-xs text-slate-400 italic">
                "{detail.hypothesis_label}"
              </p>
            )}
          </div>
          <div className="text-right">
            {confidence && (
              <div className="mb-2">
                <p className="text-[10px] text-slate-600 uppercase tracking-wider">Raw Correlation</p>
                <p className="font-mono text-lg text-slate-500">{confidence.raw_score}</p>
              </div>
            )}
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider">Attribution Confidence</p>
              <p className="font-mono text-3xl text-teal-400">{detail.confidence}</p>
              <p className="text-[10px] text-slate-500">RCS · <RiskBadge value={detail.band} variant="band" /></p>
            </div>
          </div>
        </div>

        {/* Score explanation */}
        {confidence && confidence.raw_score !== confidence.weighted_score && (
          <div className="mt-3 rounded border border-slate-700 bg-slate-800/30 px-3 py-2">
            <p className="text-xs text-slate-400">
              Raw correlation measures signal strength ({confidence.raw_score}).
              Final attribution confidence ({confidence.weighted_score}) incorporates source reliability
              and temporal decay. The stored RCS ({detail.confidence}) is the authoritative value.
            </p>
          </div>
        )}

        {/* Status */}
        <div className="mt-3 flex items-center gap-3">
          <RiskBadge value={detail.status} variant="status" />
          {detail.reviewed_by && (
            <span className="text-xs text-slate-500">
              Reviewed by {detail.reviewed_by}
            </span>
          )}
        </div>
        {detail.review_note && (
          <div className="mt-2 rounded border border-yellow-500/20 bg-yellow-500/5 px-3 py-2">
            <p className="text-xs text-yellow-400">{detail.review_note}</p>
          </div>
        )}
      </div>

      {/* Evidence Quality Summary */}
      {eq && (
        <div className="mp-panel p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Evidence Quality</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Source Reliability</p>
              <p className="font-mono text-sm text-slate-300">{eq.source_reliability_avg}%</p>
            </div>
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Temporal Consistency</p>
              <p className={`text-sm font-medium ${
                eq.temporal_consistency === "High" ? "text-green-400" :
                eq.temporal_consistency === "Moderate" ? "text-yellow-400" : "text-red-400"
              }`}>{eq.temporal_consistency}</p>
            </div>
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Identifier Strength</p>
              <p className={`text-sm font-medium ${
                eq.identifier_strength === "High" ? "text-green-400" :
                eq.identifier_strength === "Moderate" ? "text-yellow-400" : "text-red-400"
              }`}>{eq.identifier_strength}</p>
            </div>
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Signal Families</p>
              <p className="font-mono text-sm text-slate-300">{eq.signal_families}</p>
            </div>
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Cryptographic</p>
              <p className="font-mono text-sm text-green-400">{eq.cryptographic_signals}</p>
            </div>
            <div className="rounded border border-line bg-panel2 p-2">
              <p className="text-[10px] text-slate-600 uppercase">Behavioral</p>
              <p className="font-mono text-sm text-purple-400">{eq.behavioral_signals}</p>
            </div>
          </div>
          <div className="mt-2 flex gap-4">
            <span className="text-[10px] text-green-500">● {eq.supporting_count} supporting</span>
            <span className="text-[10px] text-red-500">● {eq.contradicting_count} contradicting</span>
            <span className="text-[10px] text-slate-500">● {eq.neutral_count} neutral</span>
          </div>
        </div>
      )}

      {/* Confidence Breakdown (from confidence engine) */}
      {confidence && confidence.signals.length > 0 && (
        <div className="mp-panel p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Confidence Breakdown</h3>
          <div className="space-y-1">
            {confidence.signals
              .filter((s) => s.evidence_direction === "SUPPORTING")
              .map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-28 text-xs text-slate-500 truncate">{s.signal_type}</span>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-teal-600"
                        style={{ width: `${Math.min(100, (s.weighted_score / 30) * 100)}%` }}
                      />
                    </div>
                  </div>
                  <span className="font-mono text-xs text-slate-400">
                    +{s.weighted_score.toFixed(1)}
                  </span>
                </div>
              ))}
            {confidence.signals
              .filter((s) => s.evidence_direction === "CONTRADICTING")
              .map((s, i) => (
                <div key={`neg-${i}`} className="flex items-center gap-3">
                  <span className="w-28 text-xs text-red-400 truncate">{s.signal_type}</span>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-slate-800">
                      <div className="h-full rounded-full bg-red-600" style={{ width: "20%" }} />
                    </div>
                  </div>
                  <span className="font-mono text-xs text-red-400">
                    CONTRADICTING
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Scoring factors */}
      <div className="mp-panel p-4">
        <h3 className="mb-3 text-sm font-medium text-slate-300">Scoring Factors</h3>
        <div className="space-y-2">
          {detail.scoring_factors.map((f, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="w-24 text-xs text-slate-500">{f.signal}</span>
              <div className="flex-1">
                <div className="h-2 rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-teal-600"
                    style={{ width: `${Math.min(100, (f.score / Math.max(f.weight, 1)) * 100)}%` }}
                  />
                </div>
              </div>
              <span className="font-mono text-xs text-slate-400">
                +{f.score}/{f.weight}
              </span>
              <span className="text-[11px] text-slate-600">{f.note}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Evidence Chain (expandable) */}
      <div className="mp-panel p-4">
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Evidence Chain ({detail.evidence.length} items)
        </h3>
        <div className="space-y-3">
          {detail.evidence.map((ev) => {
            const cls = CLASS_LABELS[ev.evidence_class] ?? { label: ev.evidence_class, color: "bg-slate-500/15 text-slate-400" };
            return (
              <EvidenceCard key={ev.code} evidence={ev} cls={cls} />
            );
          })}
        </div>
      </div>

      {/* Explanation */}
      {detail.explanation && (
        <div className="mp-panel p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-300">Explanation</h3>
          <p className="text-sm text-slate-400 leading-relaxed">{detail.explanation}</p>
        </div>
      )}

      {/* Safety disclaimer */}
      <div className="rounded border border-yellow-500/20 bg-yellow-500/5 px-4 py-3">
        <p className="text-xs text-yellow-400">
          ⚠ This is a Relationship Confidence Score — a decision heuristic for analysts,
          NOT a probability of identity. Every inference requires human review.
        </p>
      </div>
    </div>
  );
}

/** Expandable evidence card with details chain */
function EvidenceCard({
  evidence: ev,
  cls,
}: {
  evidence: { code: string; kind: string; title: string; description: string; strength: string; evidence_class: string; score_contribution: number; details: Record<string, unknown>; status: string };
  cls: { label: string; color: string };
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border border-line bg-panel2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 text-left"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-200">{ev.title}</span>
              <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${cls.color}`}>
                {cls.label}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">{ev.description}</p>
          </div>
          <div className="text-right shrink-0 ml-4">
            <p className={`font-mono text-sm ${STRENGTH_COLORS[ev.strength] ?? "text-slate-400"}`}>
              +{ev.score_contribution}
            </p>
            <p className="text-[10px] text-slate-600">{ev.strength}</p>
          </div>
        </div>
        {expanded && (
          <div className="mt-3 border-t border-line pt-3 space-y-2">
            {/* Evidence metadata */}
            <div className="flex flex-wrap gap-2">
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
                code: {ev.code}
              </span>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
                kind: {ev.kind}
              </span>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
                status: {ev.status}
              </span>
            </div>
            {/* Details */}
            {Object.keys(ev.details).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(ev.details).map(([k, v]) => (
                  <span key={k} className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
                    {k}: {String(v).length > 60 ? `${String(v).slice(0, 50)}…` : String(v)}
                  </span>
                ))}
              </div>
            )}
            {/* Evidence provenance chain */}
            <div className="text-[10px] text-slate-600">
              Evidence → Source → Observation → Extracted Entity → Resolved Actor → Relationship → Confidence Signal
            </div>
          </div>
        )}
      </button>
    </div>
  );
}
