/** Full-panel loading spinner. */
export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-1 items-center justify-center py-20">
      <div className="flex items-center gap-2.5 text-slate-600">
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path className="opacity-60" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-xs">{label}</span>
      </div>
    </div>
  );
}
