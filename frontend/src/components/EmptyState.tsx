/** Empty state shown when a list has no results. */
export function EmptyState({
  title = "No results",
  description,
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-20 text-center">
      <div className="mb-3 rounded border border-line bg-panel p-2">
        <svg className="h-5 w-5 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      </div>
      <p className="mb-1 text-xs font-medium text-slate-500">{title}</p>
      {description && <p className="max-w-md text-2xs text-slate-700">{description}</p>}
    </div>
  );
}
