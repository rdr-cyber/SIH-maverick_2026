/**
 * Map view: geolocated actors as pins, relationship lines between them.
 *
 * Roles (victim / suspect / witness / person_of_interest) are visually
 * distinguished by pin color; edge styling reuses the graph page's band
 * vocabulary (dashed = hypothesis, solid = observed fact, band color+weight).
 */
import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { fetchMap } from "@/api/map";
import type { MapData, MapEdge, MapPin } from "@/api/map";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";

/** Role → pin color (victim stands out in sky blue against the warm suspect reds). */
const ROLE_COLORS: Record<string, string> = {
  victim: "#38bdf8",
  suspect: "#ef4444",
  witness: "#22c55e",
  person_of_interest: "#f59e0b",
};
const ROLE_FALLBACK = "#6b7280";
const ROLE_LABELS: Record<string, string> = {
  victim: "Victim",
  suspect: "Suspect",
  witness: "Witness",
  person_of_interest: "Person of interest",
};

/** Band → line style, mirroring the Graph page encoding (GRAPH_MODEL.md §3). */
const BAND_STYLE: Record<string, { color: string; weight: number }> = {
  weak: { color: "#64748b", weight: 1.5 },
  low: { color: "#f59e0b", weight: 2 },
  moderate: { color: "#f97316", weight: 2.5 },
  medium: { color: "#f97316", weight: 2.5 },
  high: { color: "#22c55e", weight: 3.5 },
  very_high: { color: "#059669", weight: 5 },
};

function bandStyle(band: string | null | undefined) {
  return BAND_STYLE[band ?? ""] ?? BAND_STYLE.low;
}

function pinIcon(pin: MapPin) {
  const color = ROLE_COLORS[pin.role ?? ""] ?? ROLE_FALLBACK;
  const ring =
    pin.risk_level === "critical"
      ? "ring-2 ring-red-400/70"
      : pin.risk_level === "high"
        ? "ring-2 ring-amber-400/60"
        : "";
  return L.divIcon({
    className: "",
    html: `<span title="${pin.display_name}" data-code="${pin.code}" style="display:block;width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #0b0e13;box-shadow:0 0 0 1px ${color}66, 0 0 10px ${color}55" class="${ring}"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

/** Fit the viewport to whatever pins exist. */
function FitBounds({ pins }: { pins: MapPin[] }) {
  const map = useMap();
  useEffect(() => {
    if (pins.length === 0) return;
    if (pins.length === 1) {
      map.setView([pins[0].lat, pins[0].lng], 5);
      return;
    }
    map.fitBounds(
      L.latLngBounds(pins.map((p) => [p.lat, p.lng] as [number, number])),
      { padding: [40, 40] },
    );
  }, [map, pins]);
  return null;
}

export default function MapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPin, setSelectedPin] = useState<MapPin | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<MapEdge | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchMap()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Unknown error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const byCode = useMemo(() => {
    const m = new Map<string, MapPin>();
    data?.pins.forEach((p) => m.set(p.code, p));
    return m;
  }, [data]);

  const lines = useMemo(
    () =>
      (data?.edges ?? [])
        .map((e) => {
          const from = byCode.get(e.from_code);
          const to = byCode.get(e.to_code);
          if (!from || !to) return null;
          return { edge: e, positions: [[from.lat, from.lng], [to.lat, to.lng]] as [number, number][] };
        })
        .filter((x): x is { edge: MapEdge; positions: [number, number][] } => x !== null),
    [data, byCode],
  );

  const roleEntries = Object.entries(data?.roles ?? {});

  return (
    <div className="flex h-full flex-col space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-200">Geospatial View</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Actor locations and relationship lines (same relationship data as the network graph)
          </p>
        </div>
        <button
          onClick={load}
          className="rounded border border-line px-3 py-1.5 text-xs text-slate-400 hover:bg-panel2"
        >
          Refresh
        </button>
      </div>

      {/* Legend */}
      <div className="mp-panel flex flex-wrap items-center gap-x-4 gap-y-1 p-3">
        <span className="text-[10px] uppercase tracking-wide text-slate-600">Roles</span>
        {roleEntries.map(([role, count]) => (
          <span key={role} className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: ROLE_COLORS[role] ?? ROLE_FALLBACK }}
            />
            {ROLE_LABELS[role] ?? role} ({count})
          </span>
        ))}
        <span className="ml-2 text-[10px] uppercase tracking-wide text-slate-600">Edges</span>
        <span className="flex items-center gap-1 text-[11px] text-slate-500">
          <span className="inline-block w-5 border-t-2 border-dashed border-slate-400" /> hypothesis
        </span>
        <span className="flex items-center gap-1 text-[11px] text-slate-500">
          <span className="inline-block w-5 border-t-2 border-slate-400" /> observed fact
        </span>
      </div>

      {/* Map + detail panel */}
      <div className="flex flex-1 gap-3 overflow-hidden">
        <div className="mp-panel relative flex-1 overflow-hidden">
          {loading && (
            <div className="absolute inset-0 z-[500] flex items-center justify-center bg-panel/80">
              <Loading label="Loading map…" />
            </div>
          )}
          {error && (
            <div className="absolute inset-0 z-[500] flex items-center justify-center">
              <ErrorState message={error} onRetry={load} />
            </div>
          )}
          {data && (
            <MapContainer
              center={[30, 10]}
              zoom={2}
              className="h-full w-full"
              style={{ background: "#0b0e13" }}
            >
              <TileLayer
                attribution="Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics"
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
              />
              <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
              />
              <FitBounds pins={data.pins} />
              {lines.map(({ edge, positions }) => {
                const s = bandStyle(edge.band);
                const dashed = edge.kind === "POSSIBLY_SAME_AS";
                const dimmed = edge.status === "rejected";
                const active = selectedEdge?.code === edge.code;
                return (
                  <Polyline
                    key={edge.code}
                    positions={positions}
                    pathOptions={{
                      color: active ? "#7dd3c7" : s.color,
                      weight: active ? s.weight + 2 : s.weight,
                      opacity: dimmed ? 0.3 : 0.85,
                      dashArray: dashed ? "6 6" : undefined,
                    }}
                    eventHandlers={{ click: () => { setSelectedEdge(edge); setSelectedPin(null); } }}
                  >
                    <Tooltip sticky>
                      <span className="font-mono text-[10px]">
                        {edge.kind}: {edge.from_code} → {edge.to_code} · {edge.confidence.toFixed(1)} ·{" "}
                        {edge.status}
                      </span>
                    </Tooltip>
                  </Polyline>
                );
              })}
              {data.pins.map((pin) => (
                <Marker
                  key={pin.code}
                  position={[pin.lat, pin.lng]}
                  icon={pinIcon(pin)}
                  eventHandlers={{ click: () => { setSelectedPin(pin); setSelectedEdge(null); } }}
                >
                  <Tooltip>
                    <span className="text-[11px]">
                      {pin.display_name}
                      {pin.role ? ` — ${ROLE_LABELS[pin.role] ?? pin.role}` : ""}
                    </span>
                  </Tooltip>
                </Marker>
              ))}
            </MapContainer>
          )}
        </div>

        {/* Detail panel */}
        {(selectedPin || selectedEdge) && (
          <div className="w-80 shrink-0 overflow-y-auto">
            <div className="mp-panel p-4">
              {selectedPin && (
                <>
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-200">{selectedPin.display_name}</h3>
                    {selectedPin.role && (
                      <span
                        className="rounded border px-1.5 py-0.5 text-[10px] font-medium"
                        style={{
                          color: ROLE_COLORS[selectedPin.role] ?? ROLE_FALLBACK,
                          borderColor: `${ROLE_COLORS[selectedPin.role] ?? ROLE_FALLBACK}55`,
                        }}
                      >
                        {ROLE_LABELS[selectedPin.role] ?? selectedPin.role}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{selectedPin.label}</p>
                  <dl className="mt-3 space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Actor code</dt>
                      <dd className="font-mono text-slate-300">{selectedPin.code}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Risk level</dt>
                      <dd className="text-slate-300">{selectedPin.risk_level}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Category</dt>
                      <dd className="text-slate-300">{selectedPin.category}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Status</dt>
                      <dd className="text-slate-300">{selectedPin.status}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Attribution conf.</dt>
                      <dd className="font-mono text-teal-400">{selectedPin.confidence.toFixed(1)}/100</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Coordinates</dt>
                      <dd className="font-mono text-slate-400">
                        {selectedPin.lat.toFixed(4)}, {selectedPin.lng.toFixed(4)}
                      </dd>
                    </div>
                  </dl>
                </>
              )}
              {selectedEdge && (
                <>
                  <h3 className="text-sm font-semibold text-slate-200">Relationship</h3>
                  <p className="mt-1 font-mono text-[11px] text-slate-500">
                    {selectedEdge.kind}: {selectedEdge.from_code} → {selectedEdge.to_code}
                  </p>
                  {selectedEdge.hypothesis_label && (
                    <p className="mt-2 border-l-2 border-slate-700 pl-2 text-xs italic text-slate-300">
                      “{selectedEdge.hypothesis_label}”
                    </p>
                  )}
                  <dl className="mt-3 space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Confidence</dt>
                      <dd className="font-mono text-teal-400">{selectedEdge.confidence.toFixed(1)}/100</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Band</dt>
                      <dd style={{ color: bandStyle(selectedEdge.band).color }}>{selectedEdge.band}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Status</dt>
                      <dd className="text-slate-300">{selectedEdge.status}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Code</dt>
                      <dd className="font-mono text-slate-400">{selectedEdge.code}</dd>
                    </div>
                  </dl>
                  <p className="mt-3 text-[11px] text-slate-600">
                    Full scoring breakdown is available on the Graph page (click the same edge).
                  </p>
                </>
              )}
              <button
                onClick={() => { setSelectedPin(null); setSelectedEdge(null); }}
                className="mt-4 w-full rounded border border-line px-2 py-1 text-2xs text-slate-500 hover:text-slate-300"
              >
                Clear selection
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Sparsity transparency */}
      {data && data.unlocated.length > 0 && (
        <p className="text-[11px] text-slate-600">
          {data.unlocated.length} actor{data.unlocated.length === 1 ? "" : "s"} not geolocated and
          hidden from the map: {data.unlocated.join(", ")}
        </p>
      )}
    </div>
  );
}
