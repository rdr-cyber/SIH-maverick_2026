/** Colored badge for risk levels and confidence bands. */

const RISK_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  moderate: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/15 text-green-400 border-green-500/30",
  // Confidence bands
  very_high: "bg-red-500/15 text-red-400 border-red-500/30",
  weak: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  accepted: "bg-green-500/15 text-green-400 border-green-500/30",
  rejected: "bg-red-500/15 text-red-400 border-red-500/30",
  uncertain: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  tracked: "bg-teal-500/15 text-teal-400 border-teal-500/30",
  dormant: "bg-slate-500/15 text-slate-400 border-slate-500/30",
  archived: "bg-slate-500/10 text-slate-500 border-slate-600/30",
  active: "bg-green-500/15 text-green-400 border-green-500/30",
  inactive: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

export function RiskBadge({
  value,
  variant = "risk",
}: {
  value: string;
  variant?: "risk" | "status" | "band";
}) {
  const palette =
    variant === "risk"
      ? RISK_COLORS
      : variant === "band"
        ? RISK_COLORS
        : STATUS_COLORS;
  const cls =
    palette[value] ?? "bg-slate-500/15 text-slate-400 border-slate-500/30";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {value}
    </span>
  );
}
