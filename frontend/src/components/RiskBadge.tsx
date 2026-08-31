/** Colored badge for risk levels, confidence bands, and status. */

const RISK_COLORS: Record<string, string> = {
  critical: "border-red-500/30 bg-red-500/10 text-red-400",
  high: "border-orange-500/30 bg-orange-500/10 text-orange-400",
  moderate: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  low: "border-green-500/30 bg-green-500/10 text-green-400",
  very_high: "border-red-500/30 bg-red-500/10 text-red-400",
  weak: "border-slate-500/30 bg-slate-500/10 text-slate-400",
};

const BAND_COLORS: Record<string, string> = {
  high: "border-green-500/30 bg-green-500/10 text-green-400",
  medium: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  low: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  weak: "border-slate-500/30 bg-slate-500/10 text-slate-400",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "border-blue-500/30 bg-blue-500/10 text-blue-400",
  accepted: "border-green-500/30 bg-green-500/10 text-green-400",
  rejected: "border-red-500/30 bg-red-500/10 text-red-400",
  uncertain: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  tracked: "border-accent/30 bg-accent/10 text-accentLight",
  dormant: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  archived: "border-slate-600/20 bg-slate-600/10 text-slate-500",
  active: "border-green-500/30 bg-green-500/10 text-green-400",
  inactive: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  draft: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  paused: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  closed: "border-slate-600/20 bg-slate-600/10 text-slate-500",
};

export function RiskBadge({
  value,
  variant = "risk",
}: {
  value: string;
  variant?: "risk" | "status" | "band";
}) {
  const palette =
    variant === "band" ? BAND_COLORS : variant === "status" ? STATUS_COLORS : RISK_COLORS;
  const cls = palette[value] ?? "border-slate-500/30 bg-slate-500/10 text-slate-400";
  return (
    <span className={`mp-badge ${cls}`}>
      {value}
    </span>
  );
}
