import type { Incident } from '../api/types'
import { formatDate } from '../utils/date'

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge severity-${severity.toLowerCase()}`}>{severity}</span>
}

export function StatusBadge({ status }: { status: string }) {
  return <span className="badge border-slate-700 bg-slate-800 text-slate-300">{status}</span>
}

export function IncidentWindow({ incident }: { incident: Incident }) {
  return (
    <dl className="grid gap-4 text-sm sm:grid-cols-2">
      <div>
        <dt className="metadata-label">Window start</dt>
        <dd className="mt-1 text-slate-300">{formatDate(incident.window_start)}</dd>
      </div>
      <div>
        <dt className="metadata-label">Window end</dt>
        <dd className="mt-1 text-slate-300">{formatDate(incident.window_end)}</dd>
      </div>
    </dl>
  )
}
