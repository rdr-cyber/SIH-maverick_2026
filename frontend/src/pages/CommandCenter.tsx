import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchActors, fetchActorStats } from "@/api/client";
import type { ActorStats, ActorSummary } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

export default function CommandCenter() {
  const [stats, setStats] = useState<ActorStats | null>(null);
  const [highRisk, setHighRisk] = useState<ActorSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, actors] = await Promise.all([
        fetchActorStats(),
        fetchActors({ risk_level: "critical", sort: "risk", order: "desc", limit: 5 }),
      ]);
      setStats(s);
      setHighRisk(actors.items);
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

  const cards = [
    { label: "Actors", value: stats.total_actors, color: "text-teal-400" },
    { label: "Personas", value: stats.total_personas, color: "text-blue-400" },
    { label: "Identifiers", value: stats.total_identifiers, color: "text-purple-400" },
    { label: "Sources", value: stats.total_sources, color: "text-green-400" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Command Center</h1>
        <p className="mt-1 text-xs text-slate-500">
          Overview of tracked intelligence · All data is synthetic
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="sg-panel p-4">
            <p className="text-xs text-slate-500">{c.label}</p>
            <p className={`mt-1 text-2xl font-bold ${c.color}`}>
              {c.value.toLocaleString()}
            </p>
          </div>
        ))}
      </div>

      {/* Risk breakdown */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="sg-panel p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">By Risk Level</h2>
          <div className="space-y-2">
            {Object.entries(stats.by_risk_level).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <RiskBadge value={k} variant="risk" />
                <span className="font-mono-tech text-xs text-slate-400">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="sg-panel p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">By Category</h2>
          <div className="space-y-2">
            {Object.entries(stats.by_category).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-xs text-slate-400">{k.replace(/_/g, " ")}</span>
                <span className="font-mono-tech text-xs text-slate-400">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* High-risk actors */}
      <div className="sg-panel p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-300">Critical Actors</h2>
          <Link
            to="/actors?risk_level=critical"
            className="text-xs text-teal-400 hover:text-teal-300"
          >
            View all →
          </Link>
        </div>
        <div className="space-y-2">
          {highRisk.map((a) => (
            <Link
              key={a.id}
              to={`/actors/${a.code}`}
              className="flex items-center justify-between rounded-md border border-line bg-panel2 px-3 py-2 hover:border-teal-700/50"
            >
              <div>
                <span className="text-sm text-slate-200">{a.display_name}</span>
                <span className="ml-2 text-xs text-slate-600">{a.category}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono-tech text-xs text-slate-500">
                  RCS {a.attribution_confidence}
                </span>
                <RiskBadge value={a.status} variant="status" />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
