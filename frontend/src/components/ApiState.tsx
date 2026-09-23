import { AlertTriangle, Inbox, LoaderCircle, RefreshCw } from 'lucide-react'

import { ApiError } from '../api/client'

export function LoadingState({ label }: { label: string }) {
  return (
    <div aria-busy="true" aria-live="polite" className="state-panel" role="status">
      <LoaderCircle aria-hidden="true" className="animate-spin text-cyan-300" size={20} />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div aria-live="polite" className="state-panel flex-col items-start" role="status">
      <Inbox aria-hidden="true" className="text-slate-400" size={22} />
      <div>
        <p className="font-semibold text-slate-200">{title}</p>
        <p className="mt-1 text-sm text-slate-400">{detail}</p>
      </div>
    </div>
  )
}

export function ErrorState({
  error,
  onRetry,
  title = 'Unable to load data',
}: {
  error: unknown
  onRetry?: () => void
  title?: string
}) {
  const message = error instanceof ApiError ? error.message : 'An unexpected error occurred.'

  return (
    <div
      className="state-panel flex-col items-stretch border-red-400/20 bg-red-400/[0.04] sm:flex-row sm:items-start"
      role="alert"
    >
      <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0 text-red-300" size={20} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-red-100">{title}</p>
        <p className="mt-1 text-sm text-red-200/70">{message}</p>
        {error instanceof ApiError && error.requestId ? (
          <p className="mt-2 break-all font-mono text-xs text-slate-400">
            Request ID: {error.requestId}
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <button
          className="secondary-button w-full shrink-0 sm:w-auto"
          onClick={onRetry}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={15} />
          Retry
        </button>
      ) : null}
    </div>
  )
}
