import { useEffect, useRef, useState, useCallback } from "react";
import cytoscape from "cytoscape";
import { fetchGraph, fetchEdgeEvidence } from "@/api/graph";
import type { EdgeEvidence, GraphData } from "@/api/graph";
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

const EDGE_COLORS: Record<string, string> = {
  POSSIBLY_SAME_AS: "#ef4444",
  HAS_EVIDENCE: "#22c55e",
  USES: "#6b7280",
  HAS: "#8b5cf6",
  APPEARS_ON: "#3b82f6",
};

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

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [search, setSearch] = useState("");
  const [selectedEdge, setSelectedEdge] = useState<EdgeEvidence[] | null>(null);
  const [selectedLabel, setSelectedLabel] = useState<string>("");
  const [activeGroups, setActiveGroups] = useState<Set<string>>(
    new Set(GROUP_FILTERS),
  );

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedEdge(null);
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
            width: (_el: cytoscape.EdgeSingular) => {
              const rt = _el.data("rel_type") as string;
              return rt === "POSSIBLY_SAME_AS" ? 3 : 1;
            },
            "line-color": (_el: cytoscape.EdgeSingular) => {
              const rt = _el.data("rel_type") as string;
              return EDGE_COLORS[rt] ?? "#374151";
            },
            "target-arrow-color": "#374151",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: (_el: cytoscape.EdgeSingular) => {
              const rt = _el.data("rel_type") as string;
              return rt === "POSSIBLY_SAME_AS" ? `RCS ${_el.data("confidence") ?? ""}` : "";
            },
            "font-size": "9px",
            color: "#9ca3af",
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

    // Edge click → show evidence
    cy.on("tap", "edge", async (evt) => {
      const edge = evt.target;
      const source = edge.data("source") as string;
      const target = edge.data("target") as string;
      const relType = edge.data("rel_type") as string;
      setSelectedLabel(`${relType}: ${source} → ${target}`);

      if (relType === "POSSIBLY_SAME_AS") {
        try {
          const evidence = await fetchEdgeEvidence(source, target);
          setSelectedEdge(evidence);
        } catch {
          setSelectedEdge([]);
        }
      } else {
        setSelectedEdge(null);
      }
    });

    // Node click → focus neighbors
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      const group = node.data("group") as string;
      if (group === "actor") {
        setFocus(node.data("pgkey") as string);
      }
      setSelectedEdge(null);
    });

    // Background click → clear selection
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setSelectedEdge(null);
        setSelectedLabel("");
      }
    });

    cyRef.current = cy;
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

      {/* Graph + Evidence panel */}
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

        {/* Evidence panel */}
        {selectedEdge && (
          <div className="w-80 shrink-0 overflow-y-auto">
            <div className="mp-panel p-4">
              <h3 className="mb-2 text-sm font-medium text-slate-300">Edge Evidence</h3>
              <p className="mb-3 text-xs text-slate-500">{selectedLabel}</p>
              {selectedEdge.length === 0 ? (
                <p className="text-xs text-slate-600">No evidence items for this edge.</p>
              ) : (
                <div className="space-y-2">
                  {selectedEdge.map((ev) => (
                    <div
                      key={ev.code}
                      className="rounded border border-line bg-panel2 p-2"
                    >
                      <div className="flex items-start justify-between">
                        <span className="text-xs font-medium text-slate-300">
                          {ev.title}
                        </span>
                        <span className="font-mono text-xs text-teal-400">
                          +{ev.score_contribution}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {ev.description}
                      </p>
                      <div className="mt-1 flex items-center gap-2">
                        <RiskBadge value={ev.evidence_class} variant="status" />
                        <span className="text-[10px] text-slate-600">{ev.strength}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
