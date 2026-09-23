import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, KeyRound, LoaderCircle, LockKeyhole, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'
import type { Investigation, Review, ReviewPut } from '../api/types'
import { formatDate } from '../utils/date'

type ReviewForm = ReviewPut

interface ReviewRequest {
  payload: ReviewPut
  token: string
}

export function ReviewPanel({ investigation }: { investigation: Investigation }) {
  const queryClient = useQueryClient()
  const [credential, setCredential] = useState('')
  const [pendingReview, setPendingReview] = useState<ReviewRequest | null>(null)
  const [review, setReview] = useState<Review | null>(
    () =>
      queryClient.getQueryData<Review>(queryKeys.investigations.review(investigation.id)) ?? null,
  )
  const [conflictResolved, setConflictResolved] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ReviewForm>({ defaultValues: { decision: 'INCONCLUSIVE', comment: '' } })

  const refreshInvestigation = () =>
    queryClient.refetchQueries({
      queryKey: queryKeys.investigations.detail(investigation.id),
      type: 'active',
    })

  const existingReviewMutation = useMutation({
    mutationFn: ({ token }: { token: string }) => api.getReview(investigation.id, token),
    onSuccess: async (existingReview) => {
      setReview(existingReview)
      queryClient.setQueryData(queryKeys.investigations.review(investigation.id), existingReview)
      await refreshInvestigation()
    },
  })

  const submitMutation = useMutation({
    mutationFn: ({ payload, token }: ReviewRequest) =>
      api.putReview(investigation.id, payload, token),
    onSuccess: async (savedReview) => {
      setReview(savedReview)
      setPendingReview(null)
      setConflictResolved(false)
      queryClient.setQueryData(queryKeys.investigations.review(investigation.id), savedReview)
      await refreshInvestigation()
    },
    onError: (error, request) => {
      if (error instanceof ApiError && error.status === 409) {
        setConflictResolved(true)
        existingReviewMutation.mutate({ token: request.token })
      }
    },
  })

  if (!['AWAITING_REVIEW', 'COMPLETED'].includes(investigation.status)) {
    return (
      <section className="mt-6 surface-card p-6 sm:p-8" aria-labelledby="review-title">
        <ReviewHeading />
        <div className="mt-5 state-panel">
          Human review becomes available after the investigation report is ready.
        </div>
      </section>
    )
  }

  const credentialError =
    (submitMutation.error instanceof ApiError && submitMutation.error.status === 401) ||
    (existingReviewMutation.error instanceof ApiError &&
      existingReviewMutation.error.status === 401)

  const loadExistingReview = () => {
    if (!credential.trim()) return
    setConflictResolved(false)
    existingReviewMutation.mutate({ token: credential })
  }

  const prepareReview = handleSubmit((values) => {
    if (!credential.trim()) return
    submitMutation.reset()
    existingReviewMutation.reset()
    setConflictResolved(false)
    setPendingReview({
      payload: { decision: values.decision, comment: values.comment.trim() },
      token: credential,
    })
  })

  return (
    <section className="mt-6 surface-card p-6 sm:p-8" aria-labelledby="review-title">
      <ReviewHeading />

      <div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-300/15 bg-amber-300/[0.04] p-4 text-sm text-amber-100/80">
        <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
        <p>
          Local and trusted development only. The reviewer credential stays in this page's memory
          until refresh and is sent only to review endpoints.
        </p>
      </div>

      {review ? (
        <CompletedReview review={review} conflictResolved={conflictResolved} />
      ) : (
        <>
          <label className="field-label mt-6">
            Reviewer credential
            <span className="relative">
              <KeyRound
                aria-hidden="true"
                className="pointer-events-none absolute left-3.5 top-3.5 text-slate-600"
                size={17}
              />
              <input
                aria-label="Reviewer credential"
                aria-describedby="credential-help"
                autoComplete="new-password"
                className="pl-11"
                disabled={pendingReview !== null}
                onChange={(event) => setCredential(event.target.value)}
                required
                spellCheck={false}
                type="password"
                value={credential}
              />
            </span>
            <span
              className="text-xs font-normal normal-case tracking-normal text-slate-500"
              id="credential-help"
            >
              Never placed in source, environment configuration, URLs, logs, or browser storage.
            </span>
          </label>

          {credentialError ? (
            <ReviewError title="Credential rejected">
              Select Back, correct the reviewer credential, and prepare the decision again.
            </ReviewError>
          ) : null}

          {existingReviewMutation.isError && !credentialError ? (
            <ReviewError title="Existing review could not be loaded">
              {apiErrorMessage(existingReviewMutation.error)}
            </ReviewError>
          ) : null}

          {investigation.status === 'COMPLETED' ? (
            <div className="mt-6">
              <p className="text-sm leading-6 text-slate-400">
                This investigation is complete. Authenticate to retrieve its immutable review.
              </p>
              <button
                className="secondary-button mt-4"
                disabled={!credential.trim() || existingReviewMutation.isPending}
                onClick={loadExistingReview}
                type="button"
              >
                {existingReviewMutation.isPending ? (
                  <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
                ) : null}
                {existingReviewMutation.isPending ? 'Loading…' : 'Load existing review'}
              </button>
            </div>
          ) : pendingReview ? (
            <Confirmation
              payload={pendingReview.payload}
              pending={submitMutation.isPending || existingReviewMutation.isPending}
              error={submitMutation.error}
              onBack={() => {
                setPendingReview(null)
                submitMutation.reset()
              }}
              onConfirm={() => submitMutation.mutate(pendingReview)}
            />
          ) : (
            <form className="mt-6" noValidate onSubmit={prepareReview}>
              <fieldset>
                <legend className="field-label">Decision</legend>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {(['ACCEPTED', 'REJECTED', 'INCONCLUSIVE'] as const).map((decision) => (
                    <label
                      className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-700 bg-slate-950/40 p-4 text-sm font-semibold text-slate-200 has-[:checked]:border-cyan-300/50 has-[:checked]:bg-cyan-300/[0.06]"
                      key={decision}
                    >
                      <input type="radio" value={decision} {...register('decision')} />
                      {decisionLabel(decision)}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="field-label mt-6">
                Comment (optional)
                <textarea
                  {...register('comment', {
                    maxLength: {
                      value: 5000,
                      message: 'Comment must be 5,000 characters or fewer.',
                    },
                  })}
                  maxLength={5000}
                  rows={5}
                />
                {errors.comment ? (
                  <span className="field-error">{errors.comment.message}</span>
                ) : null}
              </label>
              <div className="mt-6 flex justify-end">
                <button className="primary-button" disabled={!credential.trim()} type="submit">
                  Review decision
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </section>
  )
}

function ReviewHeading() {
  return (
    <div className="flex items-start gap-3">
      <span className="feature-icon">
        <LockKeyhole aria-hidden="true" size={20} />
      </span>
      <div>
        <p className="eyebrow">Human judgment</p>
        <h2 className="mt-1 text-xl font-semibold text-slate-100" id="review-title">
          Immutable review
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Record one auditable decision without changing the generated report.
        </p>
      </div>
    </div>
  )
}

function Confirmation({
  payload,
  pending,
  error,
  onBack,
  onConfirm,
}: {
  payload: ReviewPut
  pending: boolean
  error: Error | null
  onBack: () => void
  onConfirm: () => void
}) {
  return (
    <div className="mt-6 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.04] p-5">
      <p className="eyebrow">Confirm once</p>
      <h3 className="mt-2 text-lg font-semibold text-slate-100">
        {decisionLabel(payload.decision)}
      </h3>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">
        {payload.comment || 'No comment provided.'}
      </p>
      <p className="mt-4 text-xs leading-5 text-slate-500">
        This decision is immutable. A retry sends the exact same decision and comment.
      </p>
      {error ? (
        <ReviewError
          title={
            error instanceof ApiError && error.status === 503
              ? 'Review service unavailable'
              : 'Review was not saved'
          }
        >
          {apiErrorMessage(error)}{' '}
          {error instanceof ApiError && error.status === 503
            ? 'Retry when the service is available; the prepared request is unchanged.'
            : null}
        </ReviewError>
      ) : null}
      <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button className="secondary-button" disabled={pending} onClick={onBack} type="button">
          Back
        </button>
        <button className="primary-button" disabled={pending} onClick={onConfirm} type="button">
          {pending ? <LoaderCircle aria-hidden="true" className="animate-spin" size={17} /> : null}
          {pending ? 'Submitting…' : error ? 'Retry exact review' : 'Submit immutable review'}
        </button>
      </div>
    </div>
  )
}

function CompletedReview({
  review,
  conflictResolved,
}: {
  review: Review
  conflictResolved: boolean
}) {
  return (
    <div className="mt-6 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.04] p-5">
      <div className="flex items-center gap-2 text-emerald-200">
        <CheckCircle2 aria-hidden="true" size={19} />
        <h3 className="font-semibold">
          {conflictResolved ? 'Existing immutable review' : 'Review completed'}
        </h3>
      </div>
      {conflictResolved ? (
        <p className="mt-3 text-sm leading-6 text-amber-100/80">
          Another review already exists. Its authoritative record is shown below; no replacement was
          made.
        </p>
      ) : null}
      <dl className="mt-5 grid gap-5 sm:grid-cols-3">
        <div>
          <dt className="metadata-label">Decision</dt>
          <dd className="mt-2 text-sm font-semibold text-slate-100">
            {decisionLabel(review.decision)}
          </dd>
        </div>
        <div>
          <dt className="metadata-label">Reviewer</dt>
          <dd className="mt-2 break-all text-sm text-slate-300">{review.reviewer}</dd>
        </div>
        <div>
          <dt className="metadata-label">Recorded</dt>
          <dd className="mt-2 text-sm text-slate-300">{formatDate(review.created_at)}</dd>
        </div>
      </dl>
      <div className="mt-5 border-t border-slate-800 pt-5">
        <p className="metadata-label">Comment</p>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
          {review.comment || 'No comment provided.'}
        </p>
      </div>
    </div>
  )
}

function ReviewError({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5 error-banner" role="alert">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-sm">{children}</p>
    </div>
  )
}

function decisionLabel(decision: ReviewPut['decision']): string {
  return decision.charAt(0) + decision.slice(1).toLowerCase()
}

function apiErrorMessage(error: Error): string {
  return error instanceof ApiError ? error.message : 'An unexpected error occurred.'
}
