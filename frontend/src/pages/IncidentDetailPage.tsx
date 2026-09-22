import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, LoaderCircle } from 'lucide-react'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import { ErrorState, LoadingState } from '../components/ApiState'
import { IncidentWindow, SeverityBadge, StatusBadge } from '../components/IncidentMeta'
import { PageHeader } from '../components/PageHeader'
import { incidentEditFormSchema, type IncidentEditForm } from '../forms/incidentSchemas'

export function IncidentDetailPage() {
  const { incidentId } = useParams()
  const queryClient = useQueryClient()
  const incidentQuery = useQuery({
    queryKey: queryKeys.incidents.detail(incidentId ?? ''),
    queryFn: () => api.getIncident(incidentId ?? ''),
    enabled: Boolean(incidentId),
  })
  const {
    register,
    reset,
    setError,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<IncidentEditForm>()

  useEffect(() => {
    if (incidentQuery.data) {
      reset({
        title: incidentQuery.data.title,
        description: incidentQuery.data.description,
        severity: incidentQuery.data.severity as IncidentEditForm['severity'],
      })
    }
  }, [incidentQuery.data, reset])

  const updateMutation = useMutation({
    mutationFn: (values: IncidentEditForm) => api.updateIncident(incidentId ?? '', values),
    onSuccess: (incident) => {
      queryClient.setQueryData(queryKeys.incidents.detail(incident.id), incident)
      void queryClient.invalidateQueries({ queryKey: queryKeys.incidents.lists })
      reset({
        title: incident.title,
        description: incident.description,
        severity: incident.severity as IncidentEditForm['severity'],
      })
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return
      for (const issue of error.issues) {
        const field = issue.location.at(-1)
        if (typeof field === 'string' && ['title', 'description', 'severity'].includes(field)) {
          setError(field as keyof IncidentEditForm, { message: issue.message })
        }
      }
    },
  })

  const submit = handleSubmit(async (rawValues) => {
    const result = incidentEditFormSchema.safeParse(rawValues)
    if (!result.success) {
      for (const issue of result.error.issues) {
        const field = issue.path[0]
        if (typeof field === 'string' && field in rawValues) {
          setError(field as keyof IncidentEditForm, { message: issue.message })
        }
      }
      return
    }
    await updateMutation.mutateAsync(result.data).catch(() => undefined)
  })

  if (incidentQuery.isPending) return <LoadingState label="Loading incident…" />
  if (incidentQuery.isError) {
    return (
      <ErrorState
        error={incidentQuery.error}
        onRetry={() => void incidentQuery.refetch()}
        title="Unable to load incident"
      />
    )
  }

  const incident = incidentQuery.data

  return (
    <>
      <Link className="back-link" to="/incidents">
        <ArrowLeft aria-hidden="true" size={16} />
        Incidents
      </Link>
      <div className="mt-6">
        <PageHeader
          description={`${incident.service} · Immutable incident window shown in your local timezone.`}
          eyebrow="Incident detail"
          title={incident.title}
        />
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        <SeverityBadge severity={incident.severity} />
        <StatusBadge status={incident.status} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <form className="surface-card p-6 sm:p-8" noValidate onSubmit={submit}>
          <h2 className="text-lg font-semibold text-slate-100">Incident metadata</h2>
          <p className="mt-2 text-sm text-slate-500">
            Only title, description, and severity can be edited. Service, status, and time window
            are immutable.
          </p>
          <div className="mt-6 grid gap-5">
            <label className="field-label">
              Title
              <input {...register('title')} maxLength={200} />
              {errors.title ? <span className="field-error">{errors.title.message}</span> : null}
            </label>
            <label className="field-label">
              Severity
              <select {...register('severity')}>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </label>
            <label className="field-label">
              Description
              <textarea {...register('description')} maxLength={5000} rows={5} />
              {errors.description ? (
                <span className="field-error">{errors.description.message}</span>
              ) : null}
            </label>
          </div>
          {updateMutation.isError ? (
            <div className="mt-5 error-banner" role="alert">
              {updateMutation.error instanceof ApiError
                ? updateMutation.error.message
                : 'The incident could not be updated.'}
            </div>
          ) : null}
          <div className="mt-6 flex justify-end">
            <button
              className="primary-button"
              disabled={!isDirty || updateMutation.isPending}
              type="submit"
            >
              {updateMutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
              ) : null}
              {updateMutation.isPending ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>

        <aside className="space-y-5">
          <section className="surface-card p-6" aria-labelledby="window-title">
            <h2 className="text-sm font-semibold text-slate-200" id="window-title">
              Incident window
            </h2>
            <div className="mt-5">
              <IncidentWindow incident={incident} />
            </div>
          </section>
          <section className="surface-card p-6" aria-labelledby="identity-title">
            <h2 className="text-sm font-semibold text-slate-200" id="identity-title">
              Identity
            </h2>
            <dl className="mt-4 space-y-4 text-sm">
              <div>
                <dt className="metadata-label">Service</dt>
                <dd className="mt-1 text-slate-300">{incident.service}</dd>
              </div>
              <div>
                <dt className="metadata-label">Incident ID</dt>
                <dd className="mt-1 break-all font-mono text-xs text-slate-400">{incident.id}</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>

      <section className="mt-6 surface-card p-6" aria-labelledby="investigations-title">
        <h2 className="text-lg font-semibold text-slate-100" id="investigations-title">
          Investigations
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Investigation history and start controls are intentionally introduced in Phase 06.5.
        </p>
      </section>
    </>
  )
}
