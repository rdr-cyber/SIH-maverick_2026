import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchActors, fetchActorStats, fetchRelationships, fetchInvestigations } from "@/api/client";
import type { ActorStats, ActorSummary, InvestigationSummary, RelationshipSummary } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

export default function CommandCenter() {
  const [stats, setStats] = useState<ActorStats | null>(null);
  const [highRisk, setHighRisk] = useState<ActorSummary[]>([]);
  const [relationships, setRelationships] = useState<RelationshipSummary[]>([]);
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, actors, rels, invs] = await Promise.all([
        fetchActorStats(),
        fetchActors({ risk_level: "critical", sort: "risk", order: "desc", limit: 5 }),
        fetchRelationships({ limit: 5 }),
        fetchInvestigations(),
      ]);
      setStats(s);
      setHighRisk(actors.items);
      setRelationships(rels);
      setInvestigations(invs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!stats) return null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <svg className="h-4 w-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <h1 className="text-sm font-bold tracking-wide text-slate-200">TRILOK TRACE</h1>
          </div>
          <p className="text-xs text-slate-600">Investigative Intelligence Platform</p>
        </div>
        <div className="text-right">
          <p className="text-2xs text-slate-600 uppercase tracking-wider">System Status</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span>
            <span className="text-2xs text-slate-500">Operational</span>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: "Actors", value: stats.total_actors },
          { label: "Personas", value: stats.total_personas },
          { label: "Identifiers", value: stats.total_identifiers },
          { label: "Sources", value: stats.total_sources },
          { label: "Relationships", value: relationships.length },
        ].map((m) => (
          <div key={m.label} className="mp-panel px-3 py-2.5">
            <p className="mp-stat-label">{m.label}</p>
            <p className="mp-stat-value mt-0.5">{m.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {/* Risk breakdown */}
        <div className="mp-panel p-3">
          <h2 className="mp-section-title mb-2">Risk Distribution</h2>
          <div className="space-y-1.5">
            {Object.entries(stats.by_risk_level).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <RiskBadge value={k} variant="risk" />
                <span className="font-mono text-xs text-slate-400">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Investigations */}
        <div className="mp-panel p-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="mp-section-title">Investigations</h2>
            <Link to="/investigations" className="text-2xs text-accent hover:text-accentLight">View all</Link>
          </div>
          <div className="space-y-1.5">
            {investigations.length === 0 ? (
              <p className="text-2xs text-slate-600">No active investigations</p>
            ) : (
              investigations.map((inv) => (
                <Link
                  key={inv.code}
                  to="/investigations"
                  className="flex items-center justify-between rounded border border-line bg-panel2 px-2.5 py-1.5 hover:border-accent/30"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-slate-300 truncate">{inv.title}</p>
                    <p className="text-2xs text-slate-600 font-mono">{inv.code}</p>
                  </div>
                  <RiskBadge value={inv.status} variant="status" />
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Categories */}
        <div className="mp-panel p-3">
          <h2 className="mp-section-title mb-2">Categories</h2>
          <div className="space-y-1.5">
            {Object.entries(stats.by_category)
              .filter(([, v]) => v > 0)
              .sort(([, a], [, b]) => b - a)
              .map(([k, v]) => (
                <div key={k} className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono text-xs text-slate-400">{v}</span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Critical actors + recent evidence */}
      <div className="grid grid-cols-2 gap-3">
        {/* Critical actors */}
        <div className="mp-panel p-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="mp-section-title">Critical Actors</h2>
            <Link to="/actors?risk_level=critical" className="text-2xs text-accent hover:text-accentLight">View all</Link>
          </div>
          <div className="space-y-1.5">
            {highRisk.map((a) => (
              <Link
                key={a.id}
                to={`/actors/${a.code}`}
                className="flex items-center justify-between rounded border border-line bg-panel2 px-2.5 py-1.5 hover:border-accent/30"
              >
                <div className="min-w-0">
                  <span className="text-xs text-slate-300">{a.display_name}</span>
                  <span className="ml-2 text-2xs text-slate-600">{a.category.replace(/_/g, " ")}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xs text-slate-500">
                    RCS {a.attribution_confidence}
                  </span>
                  <RiskBadge value={a.status} variant="status" />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent evidence */}
        <div className="mp-panel p-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="mp-section-title">Recent Evidence</h2>
            <Link to="/evidence" className="text-2xs text-accent hover:text-accentLight">View all</Link>
          </div>
          <div className="space-y-1.5">
            {relationships.slice(0, 5).map((rel) => (
              <Link
                key={rel.code}
                to="/evidence"
                className="flex items-center justify-between rounded border border-line bg-panel2 px-2.5 py-1.5 hover:border-accent/30"
              >
                <div className="min-w-0">
                  <span className="text-xs text-slate-300">{rel.from_name} → {rel.to_name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xs text-slate-500">RCS {rel.confidence}</span>
                  <RiskBadge value={rel.band} variant="band" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Identifier breakdown */}
      <div className="mp-panel p-3">
        <h2 className="mp-section-title mb-2">Identifier Distribution</h2>
        <div className="flex flex-wrap gap-3">
          {Object.entries(stats.identifiers_by_kind).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-xs text-slate-500">{k.replace(/_/g, " ")}</span>
              <span className="font-mono text-xs text-slate-400">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
