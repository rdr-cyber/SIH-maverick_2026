/** Error state shown when an API call fails. */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-20 text-center">
      <div className="mb-3 rounded border border-danger/20 bg-danger/5 p-2">
        <svg className="h-5 w-5 text-danger/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p className="mb-1 text-xs font-medium text-slate-400">Something went wrong</p>
      <p className="mb-3 max-w-md text-2xs text-slate-600">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded border border-line bg-panel px-3 py-1 text-2xs text-slate-400 hover:bg-panel2 hover:text-slate-300"
        >
          Retry
        </button>
      )}
    </div>
  );
}
