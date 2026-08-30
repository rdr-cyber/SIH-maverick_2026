import { useEffect, useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchActors } from "@/api/client";
import type { ActorSummary } from "@/api/types";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { RiskBadge } from "@/components/RiskBadge";

const RISK_OPTIONS = ["", "critical", "high", "moderate", "low"];
const CATEGORY_OPTIONS = [
  "", "narcotics", "weapons", "stolen_data", "hacking_services",
  "money_laundering", "terror_financing", "fraud", "other",
];
const STATUS_OPTIONS = ["", "tracked", "dormant", "archived", "merged"];

export default function ActorSearch() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<ActorSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const q = params.get("q") ?? "";
  const risk = params.get("risk_level") ?? "";
  const cat = params.get("category") ?? "";
  const st = params.get("status") ?? "";
  const sort = params.get("sort") ?? "risk";
  const order = (params.get("order") ?? "desc") as "asc" | "desc";
  const limit = 25;
  const offset = Number(params.get("offset") ?? "0");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchActors({
        q: q || undefined,
        risk_level: risk || undefined,
        category: cat || undefined,
        status: st || undefined,
        sort,
        order,
        limit,
        offset,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [q, risk, cat, st, sort, order, offset]);

  useEffect(() => { load(); }, [load]);

  const set = (key: string, val: string) => {
    setParams((p) => {
      const next = new URLSearchParams(p);
      if (val) next.set(key, val);
      else next.delete(key);
      next.delete("offset");
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-200">Actor Search</h1>
        <p className="mt-1 text-xs text-slate-500">
          {total} actor{total !== 1 ? "s" : ""} in database
        </p>
      </div>

      {/* Filters */}
      <div className="sg-panel flex flex-wrap items-center gap-3 p-3">
        <input
          type="text"
          placeholder="Search handles, PGP, wallets…"
          value={q}
          onChange={(e) => set("q", e.target.value)}
          className="sg-input max-w-xs"
        />
        <select value={risk} onChange={(e) => set("risk_level", e.target.value)} className="sg-input max-w-[140px]">
          {RISK_OPTIONS.map((v) => (
            <option key={v} value={v}>{v || "All risk"}</option>
          ))}
        </select>
        <select value={cat} onChange={(e) => set("category", e.target.value)} className="sg-input max-w-[160px]">
          {CATEGORY_OPTIONS.map((v) => (
            <option key={v} value={v}>{v?.replace(/_/g, " ") || "All categories"}</option>
          ))}
        </select>
        <select value={st} onChange={(e) => set("status", e.target.value)} className="sg-input max-w-[140px]">
          {STATUS_OPTIONS.map((v) => (
            <option key={v} value={v}>{v || "All status"}</option>
          ))}
        </select>
        <select
          value={`${sort}:${order}`}
          onChange={(e) => {
            const [s, o] = e.target.value.split(":");
            set("sort", s);
            set("order", o);
          }}
          className="sg-input max-w-[180px]"
        >
          <option value="risk:desc">Risk ↓</option>
          <option value="risk:asc">Risk ↑</option>
          <option value="confidence:desc">Confidence ↓</option>
          <option value="confidence:asc">Confidence ↑</option>
          <option value="last_seen:desc">Last seen ↓</option>
        </select>
      </div>

      {/* Results */}
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState title="No actors found" description="Try adjusting your search filters." />
      ) : (
        <div className="sg-panel divide-y divide-line overflow-hidden">
          {items.map((a) => (
            <Link
              key={a.id}
              to={`/actors/${a.code}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-panel2/50"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">
                    {a.display_name}
                  </span>
                  <RiskBadge value={a.risk_level} variant="risk" />
                  <RiskBadge value={a.status} variant="status" />
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                  <span>{a.category.replace(/_/g, " ")}</span>
                  <span>{a.persona_count} persona{a.persona_count !== 1 ? "s" : ""}</span>
                  <span>{a.identifier_count} identifier{a.identifier_count !== 1 ? "s" : ""}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono-tech text-xs text-slate-500">
                  RCS {a.attribution_confidence}
                </span>
                {a.primary_source && (
                  <span className="text-[11px] text-slate-600">
                    {a.primary_source.name}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between">
          <button
            disabled={offset === 0}
            onClick={() => set("offset", String(Math.max(0, offset - limit)))}
            className="rounded border border-line px-3 py-1 text-xs text-slate-400 hover:bg-panel2 disabled:opacity-30"
          >
            ← Previous
          </button>
          <span className="text-xs text-slate-500">
            {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </span>
          <button
            disabled={offset + limit >= total}
            onClick={() => set("offset", String(offset + limit))}
            className="rounded border border-line px-3 py-1 text-xs text-slate-400 hover:bg-panel2 disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
