import type { Investigation } from '../api/types'
import { formatDate } from '../utils/date'

export function InvestigationStatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge investigation-${status.toLowerCase()}`}>
      {status.replaceAll('_', ' ')}
    </span>
  )
}

export function InvestigationTimes({ investigation }: { investigation: Investigation }) {
  return (
    <dl className="grid gap-4 text-sm sm:grid-cols-3">
      <div>
        <dt className="metadata-label">Queued</dt>
        <dd className="mt-1 text-slate-300">{formatDate(investigation.created_at)}</dd>
      </div>
      <div>
        <dt className="metadata-label">Started</dt>
        <dd className="mt-1 text-slate-300">
          {investigation.started_at ? formatDate(investigation.started_at) : 'Not started'}
        </dd>
      </div>
      <div>
        <dt className="metadata-label">Finished</dt>
        <dd className="mt-1 text-slate-300">
          {investigation.finished_at ? formatDate(investigation.finished_at) : 'Not finished'}
        </dd>
      </div>
    </dl>
  )
}
