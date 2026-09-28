import { useEffect, useRef, useState, useCallback } from "react";
import cytoscape from "cytoscape";
import { fetchGraph, fetchEdgeWhy } from "@/api/graph";
import type {
  EdgeEvidence,
  EdgeWhyPayload,
  GraphData,
  RelationshipMeta,
} from "@/api/graph";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { RiskBadge } from "@/components/RiskBadge";

const NODE_COLORS: Record<string, string> = {
  actor: "#3d7a8c",
  persona: "#6b7280",
  handle: "#8b5cf6",
  pgpkey: "#a855f7",
  wallet: "#f59e0b",
  onionservice: "#ef4444",
  alias: "#6366f1",
  email: "#3b82f6",
  jabber: "#06b6d4",
  domain: "#10b981",
  relationship: "#ef4444",
  evidence: "#22c55e",
};

const NODE_SHAPES: Record<string, string> = {
  actor: "round-rectangle",
  relationship: "diamond",
  evidence: "hexagon",
  persona: "rectangle",
};

/** Observed-fact edge colors. Inference edges (POSSIBLY_SAME_AS) use band colors. */
const EDGE_COLORS: Record<string, string> = {
  HAS_EVIDENCE: "#22c55e",
  USES: "#6b7280",
  HAS: "#8b5cf6",
  APPEARS_ON: "#3b82f6",
};

/**
 * Confidence-band visual encoding (GRAPH_MODEL.md §3: 0–100 score → band).
 * Color AND line weight scale with band; `medium` is accepted as a legacy
 * alias of `moderate` (the seed catalog uses it).
 */
const BAND_STYLE: Record<string, { color: string; width: number; label: string }> = {
  weak: { color: "#64748b", width: 1.5, label: "WEAK" },
  low: { color: "#f59e0b", width: 2, label: "LOW" },
  moderate: { color: "#f97316", width: 2.5, label: "MODERATE" },
  medium: { color: "#f97316", width: 2.5, label: "MODERATE" },
  high: { color: "#22c55e", width: 3.5, label: "HIGH" },
  very_high: { color: "#059669", width: 5, label: "VERY HIGH" },
};

/** Human-in-the-loop review status, visible at a glance on the edge label. */
const STATUS_GLYPHS: Record<string, string> = {
  pending: "…",
  accepted: "✓",
  rejected: "✗",
  uncertain: "?",
};

const BAND_KEYS = ["weak", "low", "moderate", "high", "very_high"] as const;

const GROUP_FILTERS = [
  "actor",
  "persona",
  "handle",
  "pgpkey",
  "wallet",
  "onionservice",
  "relationship",
  "evidence",
];

interface WhyState {
  label: string;
  loading: boolean;
  error: string | null;
  data: EdgeWhyPayload | null;
}

const IDLE_WHY: WhyState = { label: "", loading: false, error: null, data: null };

function bandStyle(band: unknown) {
  const key = typeof band === "string" ? band : "low";
  return BAND_STYLE[key] ?? BAND_STYLE.low;
}

function shortId(id: unknown): string {
  const s = typeof id === "string" ? id : "";
  return s.split(":", 2)[1] ?? s;
}

/** Small entity swatch matching the cytoscape shape/color encoding. */
function EntitySwatch({ group }: { group: string }) {
  const color = NODE_COLORS[group] ?? "#6b7280";
  const shape = NODE_SHAPES[group] ?? "ellipse";
  if (shape === "diamond")
    return <span className="inline-block h-2 w-2 rotate-45" style={{ backgroundColor: color }} />;
  if (shape === "hexagon")
    return (
      <span
        className="inline-block h-2 w-2.5"
        style={{
          backgroundColor: color,
          clipPath: "polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)",
        }}
      />
    );
  if (shape === "rectangle")
    return <span className="inline-block h-2 w-3" style={{ backgroundColor: color }} />;
  if (shape === "round-rectangle")
    return <span className="inline-block h-2 w-3 rounded-[2px]" style={{ backgroundColor: color }} />;
  return <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />;
}

function Legend() {
  return (
    <div className="mp-panel flex flex-col gap-1.5 p-3">
      {/* Entity shape + color legend (APEX LINK principle: encoding must be readable) */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-[10px] uppercase tracking-wide text-slate-600">Entities</span>
        {Object.keys(NODE_COLORS).map((g) => (
          <span key={g} className="flex items-center gap-1 text-[10px] text-slate-500">
            <EntitySwatch group={g} />
            {g}
          </span>
        ))}
      </div>
      {/* Edge encoding legend: fact vs hypothesis, band scale, review status */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-[10px] uppercase tracking-wide text-slate-600">Edges</span>
        <span className="flex items-center gap-1 text-[10px] text-slate-500">
          <span className="inline-block w-4 border-t-2 border-slate-400" /> observed fact
        </span>
        <span className="flex items-center gap-1 text-[10px] text-slate-500">
          <span className="inline-block w-4 border-t-2 border-dashed border-slate-400" /> inferred hypothesis
        </span>
        {BAND_KEYS.map((b) => (
          <span key={b} className="flex items-center gap-1 text-[10px]" style={{ color: BAND_STYLE[b].color }}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: BAND_STYLE[b].color }} />
            {BAND_STYLE[b].label}
          </span>
        ))}
        {Object.entries(STATUS_GLYPHS).map(([s, glyph]) => (
          <span key={s} className="text-[10px] text-slate-500">
            {glyph} {s}
          </span>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const glyph = STATUS_GLYPHS[status] ?? "";
  const tone =
    status === "accepted"
      ? "border-emerald-500/40 text-emerald-400"
      : status === "rejected"
        ? "border-red-500/40 text-red-400"
        : "border-amber-500/40 text-amber-400";
  return (
    <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${tone}`}>
      {glyph} {status}
    </span>
  );
}

function EvidenceCard({ ev }: { ev: EdgeEvidence }) {
  return (
    <div className="rounded border border-line bg-panel2 p-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-slate-300">{ev.title}</span>
        <span className="shrink-0 font-mono text-xs text-teal-400">+{ev.score_contribution}</span>
      </div>
      <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{ev.description}</p>
      <div className="mt-1 flex items-center gap-2">
        <RiskBadge value={ev.evidence_class} variant="status" />
        <span className="text-[10px] text-slate-600">{ev.strength}</span>
      </div>
    </div>
  );
}

/** Full WHY? breakdown for an inference edge (GRAPH_MODEL.md §3: hypothesis, not verdict). */
function RelationshipWhy({ rel, evidence }: { rel: RelationshipMeta; evidence: EdgeEvidence[] }) {
  const band = bandStyle(rel.band);
  const conf = typeof rel.confidence === "number" ? rel.confidence : Number(rel.confidence) || 0;
  const factors = rel.scoring_factors ?? [];
  return (
    <div className="mt-3 space-y-4">
      {rel.hypothesis_label && (
        <p className="border-l-2 border-slate-700 pl-2 text-xs italic leading-relaxed text-slate-300">
          “{rel.hypothesis_label}”
        </p>
      )}

      {/* Confidence + band */}
      <div>
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-wide text-slate-500">Confidence</span>
          <span className="font-mono text-sm text-teal-400">
            {conf.toFixed(1)}
            <span className="ml-1 text-[10px] text-slate-500">/100 · {band.label}</span>
          </span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded bg-slate-800">
          <div
            className="h-full rounded"
            style={{ width: `${Math.min(100, Math.max(0, conf))}%`, backgroundColor: band.color }}
          />
        </div>
      </div>

      {/* Explanation */}
      {rel.explanation && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wide text-slate-500">Explanation</h4>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">{rel.explanation}</p>
        </div>
      )}

      {/* Scoring factors: signal / weight / score / note */}
      {factors.length > 0 && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wide text-slate-500">Scoring factors</h4>
          <table className="mt-1 w-full text-[11px]">
            <thead>
              <tr className="text-left text-[10px] text-slate-600">
                <th className="pb-1 font-medium">Signal</th>
                <th className="pb-1 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {factors.map((f, i) => (
                <tr key={`${f.signal}-${i}`} className="border-t border-line/60 align-top">
                  <td className="py-1 pr-2">
                    <span className="font-mono text-slate-300">{f.signal}</span>
                    <span className="ml-1 text-[10px] text-slate-600">×{f.weight}</span>
                    {f.note && <p className="text-[10px] leading-snug text-slate-500">{f.note}</p>}
                  </td>
                  <td className="py-1 text-right font-mono text-teal-400">+{f.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Evidence chain */}
      <div>
        <h4 className="text-[10px] uppercase tracking-wide text-slate-500">
          Evidence chain ({evidence.length})
        </h4>
        {evidence.length === 0 ? (
          <p className="mt-1 text-[11px] text-slate-600">No evidence items linked to this relationship.</p>
        ) : (
          <div className="mt-1 space-y-2">
            {evidence.map((ev) => (
              <EvidenceCard key={ev.code} ev={ev} />
            ))}
          </div>
        )}
      </div>

      {/* Ruled out */}
      {rel.ruled_out_summary && (
        <div>
          <h4 className="text-[10px] uppercase tracking-wide text-slate-500">Ruled out</h4>
          <p className="mt-1 text-[11px] italic leading-relaxed text-slate-500">{rel.ruled_out_summary}</p>
        </div>
      )}
    </div>
  );
}

/** Observed-fact edges carry no inference scoring — say so explicitly. */
function ObservedEdgeNote({ evidence }: { evidence: EdgeEvidence[] }) {
  return (
    <div className="mt-3 space-y-3">
      <p className="text-xs leading-relaxed text-slate-400">
        Observed fact — recorded directly from source data, not an inference. No scoring factors
        apply.
      </p>
      {evidence.length > 0 && (
        <div className="space-y-2">
          {evidence.map((ev) => (
            <EvidenceCard key={ev.code} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [search, setSearch] = useState("");
  const [why, setWhy] = useState<WhyState>(IDLE_WHY);
  const [activeGroups, setActiveGroups] = useState<Set<string>>(
    new Set(GROUP_FILTERS),
  );

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    setWhy(IDLE_WHY);
    try {
      const data = await fetchGraph({
        focus: focus || undefined,
        depth: 2,
        max_nodes: 250,
      });
      renderGraph(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [focus]);

  useEffect(() => {
    loadGraph();
    return () => {
      cyRef.current?.destroy();
    };
  }, [loadGraph]);

  const renderGraph = (data: GraphData) => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...data.nodes, ...data.edges],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": (_el: cytoscape.NodeSingular) => {
              const group = (_el.data("group") as string) ?? "actor";
              return NODE_COLORS[group] ?? "#6b7280";
            },
            shape: (_el: cytoscape.NodeSingular) => {
              const group = (_el.data("group") as string) ?? "actor";
              return ((NODE_SHAPES[group] ?? "ellipse") as cytoscape.Css.NodeShape);
            },
            color: "#e2e8f0",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: (_el: cytoscape.NodeSingular) => {
              return (_el.data("group") as string) === "actor" ? 30 : 16;
            },
            height: (_el: cytoscape.NodeSingular) => {
              return (_el.data("group") as string) === "actor" ? 30 : 16;
            },
            "border-width": 1,
            "border-color": "#1c2230",
          }},
        {
          selector: "edge",
          style: {
            // Band → line weight (inference edges only; observed facts stay thin)
            width: (el: cytoscape.EdgeSingular) => {
              return (el.data("rel_type") as string) === "POSSIBLY_SAME_AS"
                ? bandStyle(el.data("band")).width
                : 1;
            },
            // Band → color for hypotheses; rel_type color for observed facts
            "line-color": (el: cytoscape.EdgeSingular) => {
              const rt = el.data("rel_type") as string;
              return rt === "POSSIBLY_SAME_AS"
                ? bandStyle(el.data("band")).color
                : EDGE_COLORS[rt] ?? "#374151";
            },
            "target-arrow-color": (el: cytoscape.EdgeSingular) => {
              const rt = el.data("rel_type") as string;
              return rt === "POSSIBLY_SAME_AS"
                ? bandStyle(el.data("band")).color
                : EDGE_COLORS[rt] ?? "#374151";
            },
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            // Hypothesis vs fact: dashed = inference, solid = observed
            "line-style": (el: cytoscape.EdgeSingular) => {
              return (((el.data("rel_type") as string) === "POSSIBLY_SAME_AS"
                ? "dashed"
                : "solid") as cytoscape.Css.LineStyle);
            },
            // Review status at a glance: rejected fades, uncertain dims
            opacity: (el: cytoscape.EdgeSingular) => {
              const status = el.data("status") as string | undefined;
              if (status === "rejected") return 0.35;
              if (status === "uncertain") return 0.7;
              return 1;
            },
            label: (el: cytoscape.EdgeSingular) => {
              if ((el.data("rel_type") as string) !== "POSSIBLY_SAME_AS") return "";
              const glyph = STATUS_GLYPHS[(el.data("status") as string) ?? ""] ?? "";
              return `${glyph} ${el.data("confidence") ?? ""}`.trim();
            },
            "font-size": "9px",
            color: "#cbd5e1",
            "text-background-color": "#090c10",
            "text-background-opacity": 0.8,
            "text-background-padding": "2px",
          }},
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#7dd3c7",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 4,
            "line-color": "#7dd3c7",
          },
        },
        {
          selector: ".highlighted",
          style: {
            "background-color": "#fbbf24",
            "border-color": "#fbbf24",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        nodeRepulsion: 8000,
        idealEdgeLength: 120,
        gravity: 0.3,
      } as cytoscape.LayoutOptions,
      minZoom: 0.1,
      maxZoom: 5,
      boxSelectionEnabled: false,
    });

    // Edge click → WHY? panel (relationship inference + evidence chain)
    cy.on("tap", "edge", async (evt) => {
      const edge = evt.target;
      const source = edge.data("source") as string;
      const target = edge.data("target") as string;
      const relType = edge.data("rel_type") as string;
      const label = `${relType}: ${shortId(source)} → ${shortId(target)}`;
      setWhy({ label, loading: true, error: null, data: null });
      try {
        const payload = await fetchEdgeWhy(source, target);
        setWhy({ label, loading: false, error: null, data: payload });
      } catch (e: unknown) {
        setWhy({
          label,
          loading: false,
          error: e instanceof Error ? e.message : "Failed to load edge details",
          data: null,
        });
      }
    });

    // Node click → focus neighbors
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      const group = node.data("group") as string;
      if (group === "actor") {
        setFocus(node.data("pgkey") as string);
      }
      setWhy(IDLE_WHY);
    });

    // Background click → clear selection
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setWhy(IDLE_WHY);
      }
    });

    cyRef.current = cy;
    // Dev-only handle for debugging/testing the canvas-rendered graph.
    if (import.meta.env.DEV) {
      (window as unknown as { __cy?: cytoscape.Core }).__cy = cy;
    }
  };

  // Apply group filter
  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.nodes().forEach((node) => {
      const group = node.data("group") as string;
      if (activeGroups.has(group)) {
        node.removeClass("filtered-out");
        node.style("opacity", "1");
      } else {
        node.addClass("filtered-out");
        node.style("opacity", "0.1");
      }
    });
  }, [activeGroups]);

  // Search highlight
  useEffect(() => {
    if (!cyRef.current || !search) {
      cyRef.current?.nodes().removeClass("highlighted");
      return;
    }
    cyRef.current.nodes().removeClass("highlighted");
    const term = search.toLowerCase();
    cyRef.current.nodes().forEach((node) => {
      const label = (node.data("label") as string) ?? "";
      const pgkey = (node.data("pgkey") as string) ?? "";
      if (label.toLowerCase().includes(term) || pgkey.toLowerCase().includes(term)) {
        node.addClass("highlighted");
        node.style("opacity", "1");
      }
    });
  }, [search]);

  const toggleGroup = (group: string) => {
    setActiveGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  return (
    <div className="flex h-full flex-col space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-200">Evidence Graph</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Interactive visualization of actor relationships and evidence chains
          </p>
        </div>
        <button
          onClick={() => { setFocus(""); loadGraph(); }}
          className="rounded border border-line px-3 py-1.5 text-xs text-slate-400 hover:bg-panel2"
        >
          Reset view
        </button>
      </div>

      {/* Controls */}
      <div className="mp-panel flex items-center gap-3 p-3">
        <input
          type="text"
          placeholder="Search nodes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mp-input max-w-xs"
        />
        <div className="flex flex-wrap gap-1.5">
          {GROUP_FILTERS.map((g) => (
            <button
              key={g}
              onClick={() => toggleGroup(g)}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                activeGroups.has(g)
                  ? "bg-slate-700 text-slate-300"
                  : "bg-slate-800/50 text-slate-600"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
        {focus && (
          <span className="ml-auto text-xs text-slate-500">
            Focused on: <span className="text-teal-400">{focus}</span>
          </span>
        )}
      </div>

      {/* Legend */}
      <Legend />

      {/* Graph + WHY? panel */}
      <div className="flex flex-1 gap-3 overflow-hidden">
        {/* Graph container */}
        <div className="mp-panel relative flex-1 overflow-hidden">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-panel/80">
              <Loading label="Loading graph…" />
            </div>
          )}
          {error && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <ErrorState message={error} onRetry={loadGraph} />
            </div>
          )}
          <div ref={containerRef} className="h-full w-full" />
        </div>

        {/* WHY? panel */}
        {why.label && (
          <div className="w-96 shrink-0 overflow-y-auto">
            <div className="mp-panel p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-200">WHY?</h3>
                {why.data?.relationship && <StatusBadge status={why.data.relationship.status} />}
              </div>
              <p className="mt-0.5 font-mono text-[11px] text-slate-500">{why.label}</p>
              {why.loading && (
                <div className="mt-3">
                  <Loading label="Loading edge detail…" />
                </div>
              )}
              {why.error && <p className="mt-3 text-xs text-red-400">{why.error}</p>}
              {why.data &&
                (why.data.relationship ? (
                  <RelationshipWhy
                    rel={why.data.relationship}
                    evidence={why.data.evidence}
                  />
                ) : (
                  <ObservedEdgeNote evidence={why.data.evidence} />
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
