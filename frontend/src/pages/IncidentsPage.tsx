import { ArrowRight, Plus } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import { EmptyState, ErrorState, LoadingState } from '../components/ApiState'
import { SeverityBadge, StatusBadge } from '../components/IncidentMeta'
import { PageHeader } from '../components/PageHeader'
import { formatDate } from '../utils/date'

const PAGE_SIZE = 20

export function IncidentsPage() {
  const [offset, setOffset] = useState(0)
  const [severity, setSeverity] = useState('ALL')
  const [status, setStatus] = useState('ALL')
  const params = { limit: PAGE_SIZE, offset }
  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents.list(params),
    queryFn: () => api.listIncidents(params),
  })
  const incidents = useMemo(() => incidentsQuery.data ?? [], [incidentsQuery.data])
  const visibleIncidents = useMemo(
    () =>
      incidents.filter(
        (incident) =>
          (severity === 'ALL' || incident.severity === severity) &&
          (status === 'ALL' || incident.status === status),
      ),
    [incidents, severity, status],
  )

  return (
    <>
      <PageHeader
        action={
          <Link className="primary-button" to="/incidents/new">
            <Plus aria-hidden="true" size={17} />
            New incident
          </Link>
        }
        description="Start from an operational incident, follow durable investigation progress, and review every conclusion against its evidence."
        eyebrow="Operations workspace"
        title="Incidents"
      />

      <section aria-labelledby="incident-list-title" className="mt-6 surface-card p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Incident queue</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-100" id="incident-list-title">
              Manual and externally reported incidents
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
              Filters apply only to this loaded page. The API does not expose server-side filters or
              a verified total count.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="field-label">
              Severity
              <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
                <option value="ALL">All</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </label>
            <label className="field-label">
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="ALL">All</option>
                <option value="OPEN">Open</option>
                <option value="CLOSED">Closed</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-6">
          {incidentsQuery.isPending ? <LoadingState label="Loading incidents…" /> : null}
          {incidentsQuery.isError ? (
            <ErrorState
              error={incidentsQuery.error}
              onRetry={() => void incidentsQuery.refetch()}
            />
          ) : null}
          {incidentsQuery.isSuccess && incidents.length === 0 ? (
            <EmptyState
              title="No incidents yet"
              detail="Create a manual incident to begin an evidence-backed investigation."
            />
          ) : null}
          {incidentsQuery.isSuccess && incidents.length > 0 && visibleIncidents.length === 0 ? (
            <EmptyState
              title="No incidents match these page filters"
              detail="Change the severity or status filter to inspect the loaded incidents."
            />
          ) : null}
          {visibleIncidents.length > 0 ? (
            <ul className="divide-y divide-slate-800" aria-label="Incidents">
              {visibleIncidents.map((incident) => (
                <li key={incident.id}>
                  <Link
                    className="group flex items-start justify-between gap-4 py-5 focus-visible:rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
                    to={`/incidents/${encodeURIComponent(incident.id)}`}
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <SeverityBadge severity={incident.severity} />
                        <StatusBadge status={incident.status} />
                      </div>
                      <h3 className="mt-3 font-semibold text-slate-100 group-hover:text-cyan-200">
                        {incident.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-500">
                        {incident.service} · Started {formatDate(incident.window_start)}
                      </p>
                    </div>
                    <ArrowRight
                      aria-hidden="true"
                      className="mt-2 shrink-0 text-slate-600"
                      size={18}
                    />
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {incidentsQuery.isSuccess ? (
          <nav
            aria-label="Incident pages"
            className="mt-6 flex items-center justify-between border-t border-slate-800 pt-5"
          >
            <button
              className="secondary-button"
              disabled={offset === 0}
              onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              type="button"
            >
              Previous
            </button>
            <span className="text-xs text-slate-500">Page {offset / PAGE_SIZE + 1}</span>
            <button
              className="secondary-button"
              disabled={incidents.length < PAGE_SIZE}
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
              type="button"
            >
              Next
            </button>
          </nav>
        ) : null}
      </section>
    </>
  )
}
