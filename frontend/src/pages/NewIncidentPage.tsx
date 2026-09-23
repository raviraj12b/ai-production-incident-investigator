import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import { PageHeader } from '../components/PageHeader'
import { incidentCreateFormSchema, type IncidentCreateForm } from '../forms/incidentSchemas'

interface SubmissionIntent {
  key: string
  payload: string
}

export function NewIncidentPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [intent, setIntent] = useState<SubmissionIntent | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<IncidentCreateForm>({
    defaultValues: { description: '', severity: 'HIGH' },
  })
  const createMutation = useMutation({
    mutationFn: ({
      values,
      idempotencyKey,
    }: {
      values: IncidentCreateForm
      idempotencyKey: string
    }) =>
      api.createIncident(
        {
          title: values.title.trim(),
          description: values.description,
          service: values.service.trim(),
          severity: values.severity,
          window_start: new Date(values.window_start).toISOString(),
          window_end: new Date(values.window_end).toISOString(),
        },
        idempotencyKey,
      ),
    onSuccess: async (incident) => {
      setIntent(null)
      await queryClient.invalidateQueries({ queryKey: queryKeys.incidents.lists })
      navigate(`/incidents/${encodeURIComponent(incident.id)}`)
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return
      for (const issue of error.issues) {
        const field = issue.location.at(-1)
        if (
          typeof field === 'string' &&
          ['title', 'description', 'service', 'severity', 'window_start', 'window_end'].includes(
            field,
          )
        ) {
          setError(field as keyof IncidentCreateForm, { message: issue.message })
        }
      }
    },
  })

  const submit = handleSubmit(async (rawValues) => {
    const result = incidentCreateFormSchema.safeParse(rawValues)
    if (!result.success) {
      for (const issue of result.error.issues) {
        const field = issue.path[0]
        if (typeof field === 'string' && field in rawValues) {
          setError(field as keyof IncidentCreateForm, { message: issue.message })
        }
      }
      return
    }

    const payload = JSON.stringify(result.data)
    const activeIntent =
      intent?.payload === payload ? intent : { key: crypto.randomUUID(), payload }
    if (activeIntent !== intent) setIntent(activeIntent)
    await createMutation
      .mutateAsync({
        values: result.data,
        idempotencyKey: activeIntent.key,
      })
      .catch(() => undefined)
  })

  return (
    <>
      <Link className="back-link" to="/incidents">
        <ArrowLeft aria-hidden="true" size={16} />
        Incidents
      </Link>
      <div className="mt-6">
        <PageHeader
          description="Manual incident intake is the defined starting point. Automatic anomaly detection is outside the current product boundary."
          eyebrow="Incident intake"
          title="Create incident"
        />
      </div>

      <form className="mt-8 surface-card p-6 sm:p-8" noValidate onSubmit={submit}>
        <div className="grid gap-6 lg:grid-cols-2">
          <Field label="Title" error={errors.title?.message} className="lg:col-span-2">
            <input {...register('title')} maxLength={200} autoFocus />
          </Field>
          <Field label="Service" error={errors.service?.message}>
            <input {...register('service')} maxLength={120} placeholder="checkout-api" />
          </Field>
          <Field label="Severity" error={errors.severity?.message}>
            <select {...register('severity')}>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </select>
          </Field>
          <Field label="Window start (your local timezone)" error={errors.window_start?.message}>
            <input {...register('window_start')} type="datetime-local" />
          </Field>
          <Field label="Window end (your local timezone)" error={errors.window_end?.message}>
            <input {...register('window_end')} type="datetime-local" />
          </Field>
          <Field
            label="Description (optional)"
            error={errors.description?.message}
            className="lg:col-span-2"
          >
            <textarea {...register('description')} maxLength={5000} rows={5} />
          </Field>
        </div>

        {createMutation.isError ? (
          <div className="mt-6 error-banner" role="alert">
            <p className="font-semibold">Incident was not created</p>
            <p className="mt-1 text-sm">
              {createMutation.error instanceof ApiError
                ? createMutation.error.message
                : 'An unexpected error occurred.'}
            </p>
            <p className="mt-2 text-xs text-red-200/60">
              Submit again without editing to safely retry the same request.
            </p>
          </div>
        ) : null}

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Link className="secondary-button" to="/incidents">
            Cancel
          </Link>
          <button className="primary-button" disabled={createMutation.isPending} type="submit">
            {createMutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : null}
            {createMutation.isPending ? 'Creating…' : 'Create incident'}
          </button>
        </div>
      </form>
    </>
  )
}

function Field({
  label,
  error,
  className = '',
  children,
}: {
  label: string
  error?: string | undefined
  className?: string
  children: React.ReactNode
}) {
  return (
    <label className={`field-label ${className}`}>
      {label}
      {children}
      {error ? (
        <span className="field-error" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  )
}
