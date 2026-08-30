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
      <div className="mb-4 rounded-full bg-red-500/10 p-3">
        <svg className="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p className="mb-1 text-sm font-medium text-slate-300">Something went wrong</p>
      <p className="mb-4 max-w-md text-xs text-slate-500">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md bg-teal-700/20 px-4 py-1.5 text-xs font-medium text-teal-400 hover:bg-teal-700/30"
        >
          Retry
        </button>
      )}
    </div>
  );
}
