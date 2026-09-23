import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { AppProviders } from '../app/AppProviders'
import type { Investigation } from '../api/types'
import { buildInvestigation, buildReview } from '../test/fixtures'
import { server } from '../test/server'
import { ReviewPanel } from './ReviewPanel'

function renderReviewPanel(status: Investigation['status'] = 'AWAITING_REVIEW') {
  return render(
    <AppProviders>
      <ReviewPanel investigation={buildInvestigation({ status })} />
    </AppProviders>,
  )
}

async function prepareReview(
  user: ReturnType<typeof userEvent.setup>,
  { credential = 'local-review-key', comment = 'Evidence supports the report.' } = {},
) {
  await user.type(screen.getByLabelText('Reviewer credential'), credential)
  await user.click(screen.getByLabelText('Accepted'))
  await user.type(screen.getByLabelText('Comment (optional)'), comment)
  await user.click(screen.getByRole('button', { name: 'Review decision' }))
  await user.click(screen.getByRole('button', { name: 'Submit immutable review' }))
}

describe('immutable human review', () => {
  it('submits one confirmed decision with review-only bearer authorization', async () => {
    let authorization: string | null = null
    let body: unknown
    server.use(
      http.put('*/api/v1/investigations/investigation-001/review', async ({ request }) => {
        authorization = request.headers.get('authorization')
        body = await request.json()
        return HttpResponse.json(
          buildReview({ decision: 'ACCEPTED', comment: 'Evidence supports the report.' }),
        )
      }),
    )
    const user = userEvent.setup()
    renderReviewPanel()

    await prepareReview(user)

    expect(await screen.findByText('Review completed')).toBeInTheDocument()
    expect(screen.getByText('Accepted')).toBeInTheDocument()
    expect(authorization).toBe('Bearer local-review-key')
    expect(body).toEqual({ decision: 'ACCEPTED', comment: 'Evidence supports the report.' })
  })

  it('handles a rejected reviewer credential without losing the prepared decision', async () => {
    server.use(
      http.put('*/api/v1/investigations/investigation-001/review', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'Reviewer credential is invalid' } },
          { status: 401 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderReviewPanel()

    await prepareReview(user)

    expect(await screen.findByText('Credential rejected')).toBeInTheDocument()
    expect(screen.getByText('Evidence supports the report.')).toBeInTheDocument()
    expect(screen.getByLabelText('Reviewer credential')).toHaveValue('local-review-key')
  })

  it('retries an unavailable service with the exact credential and payload', async () => {
    const attempts: Array<{ authorization: string | null; body: unknown }> = []
    server.use(
      http.put('*/api/v1/investigations/investigation-001/review', async ({ request }) => {
        attempts.push({
          authorization: request.headers.get('authorization'),
          body: await request.json(),
        })
        if (attempts.length === 1) {
          return HttpResponse.json(
            { error: { code: 'UNAVAILABLE', message: 'Review service is unavailable.' } },
            { status: 503 },
          )
        }
        return HttpResponse.json(
          buildReview({ decision: 'ACCEPTED', comment: 'Evidence supports the report.' }),
        )
      }),
    )
    const user = userEvent.setup()
    renderReviewPanel()

    await prepareReview(user)
    expect(await screen.findByText('Review service unavailable')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry exact review' }))

    expect(await screen.findByText('Review completed')).toBeInTheDocument()
    expect(attempts).toHaveLength(2)
    expect(attempts[1]).toEqual(attempts[0])
  })

  it('retrieves and displays the authoritative existing review after a conflict', async () => {
    let getAuthorization: string | null = null
    server.use(
      http.put('*/api/v1/investigations/investigation-001/review', () =>
        HttpResponse.json(
          { error: { code: 'CONFLICT', message: 'Investigation already has a review' } },
          { status: 409 },
        ),
      ),
      http.get('*/api/v1/investigations/investigation-001/review', ({ request }) => {
        getAuthorization = request.headers.get('authorization')
        return HttpResponse.json(
          buildReview({ decision: 'REJECTED', comment: 'An earlier reviewer disagreed.' }),
        )
      }),
    )
    const user = userEvent.setup()
    renderReviewPanel()

    await prepareReview(user)

    expect(await screen.findByText('Existing immutable review')).toBeInTheDocument()
    expect(screen.getByText('An earlier reviewer disagreed.')).toBeInTheDocument()
    expect(screen.getByText(/no replacement was made/i)).toBeInTheDocument()
    expect(getAuthorization).toBe('Bearer local-review-key')
  })

  it('authenticates before loading the immutable review for a completed investigation', async () => {
    let authorization: string | null = null
    server.use(
      http.get('*/api/v1/investigations/investigation-001/review', ({ request }) => {
        authorization = request.headers.get('authorization')
        return HttpResponse.json(buildReview())
      }),
    )
    const user = userEvent.setup()
    renderReviewPanel('COMPLETED')

    expect(screen.queryByText('More evidence is required.')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Reviewer credential'), 'completed-review-key')
    await user.click(screen.getByRole('button', { name: 'Load existing review' }))

    expect(await screen.findByText('More evidence is required.')).toBeInTheDocument()
    expect(authorization).toBe('Bearer completed-review-key')
  })

  it('keeps the reviewer credential only in component memory', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    const originalUrl = window.location.href
    const user = userEvent.setup()
    const view = renderReviewPanel()

    await user.type(screen.getByLabelText('Reviewer credential'), 'memory-only-secret')

    expect(storageWrite).not.toHaveBeenCalled()
    expect(window.location.href).toBe(originalUrl)
    view.unmount()
    renderReviewPanel()
    await waitFor(() => expect(screen.getByLabelText('Reviewer credential')).toHaveValue(''))
    storageWrite.mockRestore()
  })
})
