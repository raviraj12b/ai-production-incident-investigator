import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, LoaderCircle, Play } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import type { Investigation } from '../api/types'
import { formatDate } from '../utils/date'
import { investigationListPollInterval } from '../utils/investigationState'
import { EmptyState, ErrorState, LoadingState } from './ApiState'
import { InvestigationStatusBadge } from './InvestigationMeta'

const focusSchema = z.object({
  focus: z.string().max(500, 'Focus must be 500 characters or less'),
})

const PAGE_SIZE = 20

type FocusForm = z.input<typeof focusSchema>

interface SubmissionIntent {
  key: string
  payload: string
}

export function IncidentInvestigations({
  incidentId,
  incidentStatus,
}: {
  incidentId: string
  incidentStatus: string
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [intent, setIntent] = useState<SubmissionIntent | null>(null)
  const [offset, setOffset] = useState(0)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<FocusForm>({ defaultValues: { focus: '' } })
  const listParams = { limit: PAGE_SIZE, offset }
  const investigationsQuery = useQuery({
    queryKey: queryKeys.incidents.investigations(incidentId, listParams),
    queryFn: () => api.listInvestigations(incidentId, listParams),
    refetchInterval: (query) =>
      investigationListPollInterval(query.state.data as Investigation[] | undefined),
    refetchIntervalInBackground: false,
  })
  const investigations = investigationsQuery.data ?? []
  const activeInvestigation = investigations.find((item) =>
    ['QUEUED', 'RUNNING'].includes(item.status),
  )

  const createMutation = useMutation({
    mutationFn: ({ focus, idempotencyKey }: { focus: string; idempotencyKey: string }) =>
      api.createInvestigation(incidentId, { focus: focus.trim() || null }, idempotencyKey),
    onSuccess: async (investigation) => {
      setIntent(null)
      await queryClient.invalidateQueries({
        queryKey: queryKeys.incidents.investigationLists(incidentId),
      })
      navigate(`/investigations/${encodeURIComponent(investigation.id)}`)
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.incidents.investigationLists(incidentId),
        })
      }
      if (error instanceof ApiError) {
        for (const issue of error.issues) {
          if (issue.location.at(-1) === 'focus') setError('focus', { message: issue.message })
        }
      }
    },
  })

  const submit = handleSubmit(async (rawValues) => {
    const result = focusSchema.safeParse(rawValues)
    if (!result.success) {
      setError('focus', { message: result.error.issues[0]?.message ?? 'Invalid focus' })
      return
    }
    const payload = JSON.stringify({ focus: result.data.focus.trim() || null })
    const activeIntent =
      intent?.payload === payload ? intent : { key: crypto.randomUUID(), payload }
    if (activeIntent !== intent) setIntent(activeIntent)
    await createMutation
      .mutateAsync({ focus: result.data.focus, idempotencyKey: activeIntent.key })
      .catch(() => undefined)
  })

  return (
    <section className="mt-6 surface-card p-6 sm:p-8" aria-labelledby="investigations-title">
      <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          <h2 className="text-lg font-semibold text-slate-100" id="investigations-title">
            Investigation history
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Runs are immutable. Active entries refresh automatically while this page is visible.
          </p>

          <div className="mt-6">
            {investigationsQuery.isPending ? (
              <LoadingState label="Loading investigations…" />
            ) : null}
            {investigationsQuery.isError ? (
              <ErrorState
                error={investigationsQuery.error}
                onRetry={() => void investigationsQuery.refetch()}
                title="Unable to load investigations"
              />
            ) : null}
            {investigationsQuery.isSuccess && investigations.length === 0 ? (
              <EmptyState
                title="No investigations yet"
                detail="Queue the first bounded investigation for this incident."
              />
            ) : null}
            {investigations.length > 0 ? (
              <ol className="divide-y divide-slate-800" aria-label="Investigation history">
                {investigations.map((investigation) => (
                  <li key={investigation.id}>
                    <Link
                      className="group flex items-start justify-between gap-4 py-5 focus-visible:rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
                      to={`/investigations/${encodeURIComponent(investigation.id)}`}
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <InvestigationStatusBadge status={investigation.status} />
                          <span className="text-xs text-slate-500">
                            Attempt {investigation.job.attempts}
                          </span>
                        </div>
                        <p className="mt-3 text-sm font-medium text-slate-200">
                          {investigation.focus || 'General incident investigation'}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Queued {formatDate(investigation.created_at)}
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
              </ol>
            ) : null}
            {investigationsQuery.isSuccess ? (
              <nav
                aria-label="Investigation history pages"
                className="mt-5 flex items-center justify-between border-t border-slate-800 pt-5"
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
                  disabled={investigations.length < PAGE_SIZE}
                  onClick={() => setOffset((current) => current + PAGE_SIZE)}
                  type="button"
                >
                  Next
                </button>
              </nav>
            ) : null}
          </div>
        </div>

        <form
          className="rounded-xl border border-slate-800 bg-slate-950/40 p-5"
          noValidate
          onSubmit={submit}
        >
          <span className="feature-icon" aria-hidden="true">
            <Play size={19} />
          </span>
          <h3 className="mt-4 font-semibold text-slate-100">Start investigation</h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            The backend collects and analyzes bounded telemetry. The browser does not perform RCA.
          </p>
          <label className="field-label mt-5">
            Focus (optional)
            <textarea
              {...register('focus')}
              disabled={Boolean(activeInvestigation) || incidentStatus !== 'OPEN'}
              maxLength={500}
              placeholder="For example: checkout latency after deployment"
              rows={4}
            />
            {errors.focus ? <span className="field-error">{errors.focus.message}</span> : null}
          </label>

          {activeInvestigation ? (
            <p className="mt-4 text-sm text-amber-200" role="status">
              An investigation is already {activeInvestigation.status.toLowerCase()} for this
              incident.
            </p>
          ) : null}
          {incidentStatus !== 'OPEN' ? (
            <p className="mt-4 text-sm text-amber-200" role="status">
              Closed incidents cannot start new investigations.
            </p>
          ) : null}
          {createMutation.isError ? (
            <div className="mt-4 error-banner" role="alert">
              <p className="font-semibold">
                {createMutation.error instanceof ApiError && createMutation.error.status === 409
                  ? 'Investigation conflict'
                  : 'Investigation was not queued'}
              </p>
              <p className="mt-1 text-sm">
                {createMutation.error instanceof ApiError
                  ? createMutation.error.message
                  : 'An unexpected error occurred.'}
              </p>
              <p className="mt-2 text-xs text-red-200/60">
                Submit unchanged values again only when retrying the same request.
              </p>
            </div>
          ) : null}

          <button
            className="primary-button mt-5 w-full"
            disabled={
              createMutation.isPending || Boolean(activeInvestigation) || incidentStatus !== 'OPEN'
            }
            type="submit"
          >
            {createMutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : (
              <Play aria-hidden="true" size={16} />
            )}
            {createMutation.isPending ? 'Queueing…' : 'Queue investigation'}
          </button>
        </form>
      </div>
    </section>
  )
}
