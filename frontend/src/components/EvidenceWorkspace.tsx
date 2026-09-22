import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleHelp,
  Database,
  FileClock,
  XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import type { Evidence, Hypothesis, Investigation, Report } from '../api/types'
import { formatDate } from '../utils/date'
import { isActiveInvestigation } from '../utils/investigationState'
import { EmptyState, ErrorState, LoadingState } from './ApiState'
import { CopyIdentifier } from './CopyIdentifier'

const EVIDENCE_LIMIT = 100
const evidenceKinds = ['ALL', 'LOG', 'TRACE', 'METRIC', 'CHANGE'] as const
type EvidenceKindFilter = (typeof evidenceKinds)[number]

const knownLimitations: Record<string, string> = {
  NO_LOGS: 'No log evidence was available.',
  NO_REQUEST_RATE: 'No request-rate metric evidence was available.',
  NO_TRACES: 'No trace evidence was available.',
  CHANGE_FEED_NOT_CONFIGURED:
    'Change evidence is unavailable because the change feed is not configured.',
  NO_LOG_TRACE_OVERLAP: 'No shared trace identifier connected the available logs and traces.',
}

export function EvidenceWorkspace({ investigation }: { investigation: Investigation }) {
  const [kind, setKind] = useState<EvidenceKindFilter>('ALL')
  const active = isActiveInvestigation(investigation)
  const evidenceParams = { limit: EVIDENCE_LIMIT, offset: 0 }
  const evidenceQuery = useQuery({
    queryKey: [
      ...queryKeys.investigations.evidence(investigation.id, evidenceParams),
      investigation.status,
    ],
    queryFn: () => api.listEvidence(investigation.id, evidenceParams),
    retry: false,
    refetchInterval: active ? 4_000 : false,
    refetchIntervalInBackground: false,
  })
  const reportQuery = useQuery({
    queryKey: [...queryKeys.investigations.report(investigation.id), investigation.status],
    queryFn: () => api.getReport(investigation.id),
    retry: false,
    refetchInterval: active ? 4_000 : false,
    refetchIntervalInBackground: false,
  })
  const evidence = useMemo(() => evidenceQuery.data ?? [], [evidenceQuery.data])
  const visibleEvidence = useMemo(
    () => evidence.filter((item) => kind === 'ALL' || item.kind === kind),
    [evidence, kind],
  )
  const evidenceById = useMemo(() => new Map(evidence.map((item) => [item.id, item])), [evidence])
  const reportMissing = reportQuery.error instanceof ApiError && reportQuery.error.status === 404

  return (
    <div className="mt-8 space-y-6">
      <section className="surface-card p-6 sm:p-8" aria-labelledby="evidence-title">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Observed evidence</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-100" id="evidence-title">
              Chronological evidence timeline
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Normalized records and provenance from the bounded backend pipeline. Order reflects
              observation time, not inferred causality.
            </p>
          </div>
          <div className="flex flex-wrap gap-2" aria-label="Filter evidence by kind">
            {evidenceKinds.map((item) => (
              <button
                aria-pressed={kind === item}
                className={`filter-button ${kind === item ? 'filter-button-active' : ''}`}
                key={item}
                onClick={() => setKind(item)}
                type="button"
              >
                {item === 'ALL' ? 'All evidence' : item}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-7">
          {evidenceQuery.isPending ? <LoadingState label="Loading normalized evidence…" /> : null}
          {evidenceQuery.isError ? (
            <ErrorState
              error={evidenceQuery.error}
              onRetry={() => void evidenceQuery.refetch()}
              title="Evidence is unavailable"
            />
          ) : null}
          {evidenceQuery.isSuccess && evidence.length === 0 ? (
            <EmptyState
              title={active ? 'No evidence captured yet' : 'No evidence was captured'}
              detail={
                active
                  ? 'The active investigation will refresh this bounded timeline automatically.'
                  : 'The completed run returned no normalized evidence records.'
              }
            />
          ) : null}
          {evidenceQuery.isSuccess && evidence.length > 0 && visibleEvidence.length === 0 ? (
            <EmptyState
              title={`No ${kind.toLowerCase()} evidence`}
              detail="Choose another kind to inspect the available evidence."
            />
          ) : null}
          {visibleEvidence.length > 0 ? (
            <ol className="evidence-timeline" aria-label="Evidence timeline">
              {visibleEvidence.map((item) => (
                <EvidenceCard evidence={item} key={item.id} />
              ))}
            </ol>
          ) : null}
        </div>
      </section>

      <section className="surface-card p-6 sm:p-8" aria-labelledby="analysis-title">
        <div>
          <p className="eyebrow">Model analysis</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-100" id="analysis-title">
            Report and hypotheses
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Hypotheses remain uncertain claims. Confidence is qualitative and citations resolve only
            to the observed evidence above.
          </p>
        </div>

        <div className="mt-7">
          {reportQuery.isPending ? <LoadingState label="Loading analysis report…" /> : null}
          {reportMissing ? (
            <ReportUnavailable
              status={investigation.status}
              onRetry={() => void reportQuery.refetch()}
            />
          ) : null}
          {reportQuery.isError && !reportMissing ? (
            <ErrorState
              error={reportQuery.error}
              onRetry={() => void reportQuery.refetch()}
              title="Analysis report is unavailable"
            />
          ) : null}
          {reportQuery.data ? (
            <ReportContent
              evidenceById={evidenceById}
              evidenceLoaded={evidenceQuery.isSuccess}
              report={reportQuery.data}
            />
          ) : null}
        </div>
      </section>
    </div>
  )
}

function EvidenceCard({ evidence }: { evidence: Evidence }) {
  return (
    <li className="evidence-item">
      <div className="evidence-marker" aria-hidden="true">
        <Database size={15} />
      </div>
      <article className="min-w-0 rounded-xl border border-slate-800 bg-slate-950/35 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`badge evidence-${evidence.kind.toLowerCase()}`}>{evidence.kind}</span>
          <span className="text-xs text-slate-500">{formatDate(evidence.observed_at)}</span>
        </div>
        <p className="mt-3 text-sm font-medium leading-6 text-slate-200">{evidence.summary}</p>
        <dl className="mt-4 grid gap-4 border-t border-slate-800 pt-4 sm:grid-cols-2">
          <div>
            <dt className="metadata-label">Service</dt>
            <dd className="mt-1 text-sm text-slate-400">{evidence.service}</dd>
          </div>
          <div>
            <dt className="metadata-label">Source backend</dt>
            <dd className="mt-1 text-sm text-slate-400">{evidence.source_backend}</dd>
          </div>
        </dl>
        <div className="mt-4 grid gap-4">
          <CopyIdentifier label="Source reference" value={evidence.source_ref} />
          {evidence.trace_id ? <CopyIdentifier label="Trace ID" value={evidence.trace_id} /> : null}
        </div>
      </article>
    </li>
  )
}

function ReportUnavailable({ status, onRetry }: { status: string; onRetry: () => void }) {
  const active = ['QUEUED', 'RUNNING'].includes(status)
  return (
    <div className="state-panel items-start" role="status">
      <FileClock aria-hidden="true" className="mt-0.5 shrink-0 text-amber-300" size={20} />
      <div className="flex-1">
        <p className="font-semibold text-slate-200">
          {active ? 'Analysis is not available yet' : 'No analysis report is available'}
        </p>
        <p className="mt-1 text-sm text-slate-500">
          {active
            ? 'The investigation is still active. This section refreshes without inventing interim conclusions.'
            : 'The backend did not return a report for this investigation state.'}
        </p>
      </div>
      <button className="secondary-button shrink-0" onClick={onRetry} type="button">
        Retry
      </button>
    </div>
  )
}

function ReportContent({
  report,
  evidenceById,
  evidenceLoaded,
}: {
  report: Report
  evidenceById: Map<string, Evidence>
  evidenceLoaded: boolean
}) {
  const limitations = collectLimitations(report)
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-5">
          <p className="metadata-label">Report summary</p>
          <p className="mt-3 text-sm leading-6 text-slate-200">{report.summary}</p>
        </div>
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-5">
          <div className="flex items-center gap-2 text-amber-200">
            <AlertTriangle aria-hidden="true" size={17} />
            <p className="metadata-label !text-amber-200">Uncertainty</p>
          </div>
          <p className="mt-3 text-sm leading-6 text-amber-100/80">{report.uncertainty}</p>
        </div>
      </div>

      {limitations.length > 0 ? (
        <section
          className="rounded-xl border border-amber-400/20 bg-amber-400/[0.03] p-5"
          aria-labelledby="limitations-title"
        >
          <h3
            className="flex items-center gap-2 font-semibold text-amber-100"
            id="limitations-title"
          >
            <Ban aria-hidden="true" size={17} /> Evidence limitations
          </h3>
          <ul className="mt-3 space-y-2 text-sm text-amber-100/75">
            {limitations.map((limitation) => (
              <li key={limitation.code}>
                <span className="font-mono text-xs text-amber-200">{limitation.code}</span>
                <span className="ml-2">{limitation.message}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="hypotheses-title">
        <h3 className="text-lg font-semibold text-slate-100" id="hypotheses-title">
          Hypotheses
        </h3>
        {report.hypotheses.length === 0 ? (
          <div className="mt-4 state-panel items-start" role="status">
            <CircleHelp aria-hidden="true" className="mt-0.5 text-cyan-300" size={20} />
            <div>
              <p className="font-semibold text-slate-200">No supported hypothesis</p>
              <p className="mt-1 text-sm text-slate-500">
                The analysis abstained because the available evidence did not support a hypothesis.
              </p>
            </div>
          </div>
        ) : (
          <ol className="mt-4 space-y-5">
            {report.hypotheses.map((hypothesis, index) => (
              <HypothesisCard
                evidenceById={evidenceById}
                evidenceLoaded={evidenceLoaded}
                hypothesis={hypothesis}
                index={index}
                key={hypothesis.id}
              />
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}

function HypothesisCard({
  hypothesis,
  index,
  evidenceById,
  evidenceLoaded,
}: {
  hypothesis: Hypothesis
  index: number
  evidenceById: Map<string, Evidence>
  evidenceLoaded: boolean
}) {
  return (
    <li className="rounded-xl border border-slate-800 bg-slate-950/35 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Hypothesis {index + 1}
        </p>
        <span className={`badge confidence-${hypothesis.confidence.toLowerCase()}`}>
          {hypothesis.confidence} confidence
        </span>
      </div>
      <p className="mt-4 text-sm font-medium leading-6 text-slate-100">{hypothesis.explanation}</p>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <CitationList
          evidenceById={evidenceById}
          evidenceLoaded={evidenceLoaded}
          hypothesis={hypothesis}
          relation="SUPPORTS"
        />
        <CitationList
          evidenceById={evidenceById}
          evidenceLoaded={evidenceLoaded}
          hypothesis={hypothesis}
          relation="CONTRADICTS"
        />
      </div>

      <div className="mt-5 border-t border-slate-800 pt-5">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <CircleHelp aria-hidden="true" size={16} /> Missing evidence
        </h4>
        {hypothesis.missing_evidence.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2">
            {hypothesis.missing_evidence.map((item) => (
              <li
                className="rounded-lg border border-amber-400/20 bg-amber-400/[0.05] px-3 py-2 font-mono text-xs text-amber-200"
                key={item}
              >
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            No missing evidence was listed for this hypothesis.
          </p>
        )}
      </div>
    </li>
  )
}

function CitationList({
  hypothesis,
  relation,
  evidenceById,
  evidenceLoaded,
}: {
  hypothesis: Hypothesis
  relation: 'SUPPORTS' | 'CONTRADICTS'
  evidenceById: Map<string, Evidence>
  evidenceLoaded: boolean
}) {
  const links = hypothesis.evidence.filter((link) => link.relation === relation)
  const supports = relation === 'SUPPORTS'
  const Icon = supports ? CheckCircle2 : XCircle
  return (
    <section>
      <h4
        className={`flex items-center gap-2 text-sm font-semibold ${supports ? 'text-emerald-200' : 'text-red-200'}`}
      >
        <Icon aria-hidden="true" size={16} />{' '}
        {supports ? 'Supporting evidence' : 'Contradicting evidence'}
      </h4>
      {links.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None cited.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {links.map((link) => {
            const cited = evidenceById.get(link.evidence_id)
            return (
              <li
                className="rounded-lg border border-slate-800 p-3"
                key={`${relation}-${link.evidence_id}`}
              >
                {cited ? (
                  <>
                    <p className="text-xs font-semibold text-slate-300">
                      {cited.kind} · {cited.service}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">{cited.summary}</p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-semibold text-amber-200">
                      {evidenceLoaded
                        ? 'Evidence reference unavailable'
                        : 'Evidence reference not loaded'}
                    </p>
                    <p className="mt-1 break-all font-mono text-xs text-slate-500">
                      {link.evidence_id}
                    </p>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function collectLimitations(report: Report) {
  const codes = new Set<string>()
  for (const code of Object.keys(knownLimitations)) {
    if (report.uncertainty.includes(code)) codes.add(code)
  }
  for (const hypothesis of report.hypotheses) {
    for (const item of hypothesis.missing_evidence) {
      if (item in knownLimitations) codes.add(item)
    }
  }
  return [...codes].map((code) => ({
    code,
    message: knownLimitations[code] ?? 'Evidence is unavailable.',
  }))
}
