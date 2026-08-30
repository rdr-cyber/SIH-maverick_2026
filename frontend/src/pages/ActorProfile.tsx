import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchActor } from "@/api/client";
import type { ActorDetail } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

export default function ActorProfile() {
  const { ref } = useParams<{ ref: string }>();
  const [actor, setActor] = useState<ActorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!ref) return;
    setLoading(true);
    setError(null);
    try {
      setActor(await fetchActor(ref));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [ref]);

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!actor) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/actors" className="text-xs text-slate-500 hover:text-slate-300">
            ← Back to search
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-slate-200">
            {actor.display_name}
          </h1>
          <div className="mt-1 flex items-center gap-2">
            <RiskBadge value={actor.risk_level} variant="risk" />
            <RiskBadge value={actor.status} variant="status" />
            <span className="text-xs text-slate-500">
              {actor.category.replace(/_/g, " ")}
            </span>
          </div>
        </div>
        <div className="text-right">
          <p className="font-mono-tech text-lg text-teal-400">
            {actor.attribution_confidence}
          </p>
          <p className="text-[10px] text-slate-500">RCS</p>
        </div>
      </div>

      {/* Summary */}
      {actor.summary && (
        <div className="sg-panel p-4">
          <p className="text-sm text-slate-300">{actor.summary}</p>
        </div>
      )}

      {/* Meta */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "First seen", value: actor.first_seen?.split("T")[0] ?? "—" },
          { label: "Last seen", value: actor.last_seen?.split("T")[0] ?? "—" },
          { label: "Personas", value: String(actor.persona_count) },
          { label: "Identifiers", value: String(actor.identifier_count) },
        ].map((m) => (
          <div key={m.label} className="sg-panel p-3">
            <p className="text-[11px] text-slate-500">{m.label}</p>
            <p className="mt-0.5 font-mono-tech text-sm text-slate-300">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Personas */}
      <div className="sg-panel p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Personas</h2>
        <div className="space-y-3">
          {actor.personas.map((p) => (
            <div key={p.id} className="rounded-md border border-line bg-panel2 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">{p.name}</span>
                  {p.is_primary && (
                    <span className="rounded bg-teal-700/20 px-1.5 py-0.5 text-[10px] text-teal-400">
                      primary
                    </span>
                  )}
                </div>
                <RiskBadge value={p.status} variant="status" />
              </div>
              <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
                <span>{p.platform}</span>
                <span>{p.platform_type}</span>
                {p.reputation && <span>{p.reputation}</span>}
              </div>
              {p.identifiers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {p.identifiers.map((i) => (
                    <span
                      key={i.id}
                      className="rounded bg-slate-800 px-2 py-0.5 font-mono-tech text-[11px] text-slate-400"
                      title={i.label ?? i.value}
                    >
                      {i.kind}: {i.value.length > 30 ? `${i.value.slice(0, 20)}…${i.value.slice(-8)}` : i.value}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
