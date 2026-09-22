import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, FileClock, Fingerprint } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import { ErrorState, LoadingState } from '../components/ApiState'
import { InvestigationStatusBadge, InvestigationTimes } from '../components/InvestigationMeta'
import { PageHeader } from '../components/PageHeader'
import { investigationFailureMessage, investigationPollInterval } from '../utils/investigationState'

export function InvestigationDetailPage() {
  const { investigationId } = useParams()
  const investigationQuery = useQuery({
    queryKey: queryKeys.investigations.detail(investigationId ?? ''),
    queryFn: () => api.getInvestigation(investigationId ?? ''),
    enabled: Boolean(investigationId),
    refetchInterval: (query) => investigationPollInterval(query.state.data),
    refetchIntervalInBackground: false,
  })

  if (investigationQuery.isPending) return <LoadingState label="Loading investigation…" />
  if (investigationQuery.isError) {
    return (
      <ErrorState
        error={investigationQuery.error}
        onRetry={() => void investigationQuery.refetch()}
        title="Unable to load investigation"
      />
    )
  }

  const investigation = investigationQuery.data

  return (
    <>
      <Link
        className="back-link"
        to={`/incidents/${encodeURIComponent(investigation.incident_id)}`}
      >
        <ArrowLeft aria-hidden="true" size={16} />
        Incident
      </Link>
      <div className="mt-6">
        <PageHeader
          description="Durable worker state is authoritative. Evidence and analysis are added in Phase 06.6."
          eyebrow="Investigation"
          title={investigation.focus || 'General incident investigation'}
        />
      </div>

      <section className="mt-6 surface-card p-5 sm:p-6" aria-label="Investigation state">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <InvestigationStatusBadge status={investigation.status} />
            <span className="text-sm text-slate-400">
              Job: {investigation.job.status.replaceAll('_', ' ')}
            </span>
          </div>
          <p className="text-sm text-slate-400">
            Worker attempts{' '}
            <span className="font-semibold text-slate-200">{investigation.job.attempts}</span> / 3
          </p>
        </div>
        <div className="mt-5 border-t border-slate-800 pt-5">
          <InvestigationTimes investigation={investigation} />
        </div>
      </section>

      {investigation.status === 'FAILED' ? (
        <section className="mt-6 error-banner" aria-labelledby="failure-title">
          <div className="flex items-start gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
            <div>
              <h2 className="font-semibold" id="failure-title">
                Investigation failed
              </h2>
              <p className="mt-1 text-sm">{investigationFailureMessage(investigation.error)}</p>
              {investigation.error ? (
                <p className="mt-2 font-mono text-xs text-red-200/60">{investigation.error}</p>
              ) : null}
              <p className="mt-3 text-xs text-red-200/60">
                No browser retry control exists. Worker retries are governed by the backend.
              </p>
            </div>
          </div>
        </section>
      ) : null}

      <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="surface-card p-6" aria-labelledby="evidence-foundation-title">
          <span className="feature-icon" aria-hidden="true">
            <FileClock size={21} />
          </span>
          <h2 className="mt-5 text-lg font-semibold text-slate-100" id="evidence-foundation-title">
            Evidence view not connected
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Status and job metadata are live. This route intentionally shows no generated cause,
            confidence, timeline, or dependency relationship before evidence/report integration.
          </p>
        </section>

        <aside className="surface-card p-6" aria-label="Requested investigation identifier">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            <Fingerprint aria-hidden="true" size={15} />
            Investigation ID
          </div>
          <p className="mt-3 break-all font-mono text-xs leading-5 text-slate-300">
            {investigation.id}
          </p>
          {investigation.parent_id ? (
            <div className="mt-6 border-t border-slate-800 pt-5">
              <p className="metadata-label">Parent investigation</p>
              <Link
                className="mt-2 block break-all font-mono text-xs text-cyan-300 hover:text-cyan-200"
                to={`/investigations/${encodeURIComponent(investigation.parent_id)}`}
              >
                {investigation.parent_id}
              </Link>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                This is a linked new run. The parent report remains unchanged.
              </p>
            </div>
          ) : null}
        </aside>
      </div>
    </>
  )
}
