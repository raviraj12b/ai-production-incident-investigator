import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppProviders } from '../app/AppProviders'
import { buildIncident, buildInvestigation } from '../test/fixtures'
import { server } from '../test/server'
import {
  investigationListPollInterval,
  investigationPollInterval,
} from '../utils/investigationState'
import { IncidentDetailPage } from './IncidentDetailPage'
import { InvestigationDetailPage } from './InvestigationDetailPage'

function renderIncidentDetail() {
  return render(
    <MemoryRouter initialEntries={['/incidents/incident-001']}>
      <AppProviders>
        <Routes>
          <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
          <Route
            path="/investigations/:investigationId"
            element={<p>Investigation destination</p>}
          />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  )
}

function renderInvestigationDetail() {
  return render(
    <MemoryRouter initialEntries={['/investigations/investigation-001']}>
      <AppProviders>
        <Routes>
          <Route path="/investigations/:investigationId" element={<InvestigationDetailPage />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  )
}

describe('incident investigation history', () => {
  it('shows active durable job state and prevents a second active run', async () => {
    server.use(
      http.get('*/api/v1/incidents/incident-001', () => HttpResponse.json(buildIncident())),
      http.get('*/api/v1/incidents/incident-001/investigations', () =>
        HttpResponse.json([
          buildInvestigation({ status: 'RUNNING', job: { status: 'RUNNING', attempts: 2 } }),
        ]),
      ),
    )
    renderIncidentDetail()

    expect(await screen.findByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('Attempt 2')).toBeInTheDocument()
    expect(screen.getByText(/already running/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Queue investigation' })).toBeDisabled()
  })

  it('reuses the idempotency key when retrying an unchanged request', async () => {
    const keys: string[] = []
    let attempts = 0
    server.use(
      http.get('*/api/v1/incidents/incident-001', () => HttpResponse.json(buildIncident())),
      http.get('*/api/v1/incidents/incident-001/investigations', () => HttpResponse.json([])),
      http.post('*/api/v1/incidents/incident-001/investigations', ({ request }) => {
        keys.push(request.headers.get('Idempotency-Key') ?? '')
        attempts += 1
        if (attempts === 1) return HttpResponse.error()
        return HttpResponse.json(buildInvestigation(), { status: 202 })
      }),
    )
    const user = userEvent.setup()
    renderIncidentDetail()

    await screen.findByText('No investigations yet')
    await user.type(screen.getByLabelText(/focus/i), 'Check recent deployment')
    await user.click(screen.getByRole('button', { name: 'Queue investigation' }))
    await screen.findByText('Investigation was not queued')
    await user.click(screen.getByRole('button', { name: 'Queue investigation' }))

    expect(await screen.findByText('Investigation destination')).toBeInTheDocument()
    expect(keys).toHaveLength(2)
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
  })

  it('refreshes history and explains a backend active-run conflict', async () => {
    let listCalls = 0
    server.use(
      http.get('*/api/v1/incidents/incident-001', () => HttpResponse.json(buildIncident())),
      http.get('*/api/v1/incidents/incident-001/investigations', () => {
        listCalls += 1
        return HttpResponse.json(listCalls > 1 ? [buildInvestigation()] : [])
      }),
      http.post('*/api/v1/incidents/incident-001/investigations', () =>
        HttpResponse.json(
          {
            error: {
              code: 'CONFLICT',
              message: 'An investigation is already active for this incident',
            },
          },
          { status: 409 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderIncidentDetail()

    await screen.findByText('No investigations yet')
    await user.click(screen.getByRole('button', { name: 'Queue investigation' }))

    expect(await screen.findByText('Investigation conflict')).toBeInTheDocument()
    expect(await screen.findByText(/already queued/i)).toBeInTheDocument()
    expect(listCalls).toBeGreaterThanOrEqual(2)
  })
})

describe('investigation lifecycle workspace', () => {
  it('shows worker failure, attempt count, and immutable parent ancestry', async () => {
    server.use(
      http.get('*/api/v1/investigations/investigation-001', () =>
        HttpResponse.json(
          buildInvestigation({
            parent_id: 'investigation-parent',
            status: 'FAILED',
            error: 'ATTEMPTS_EXHAUSTED',
            finished_at: '2026-09-21T10:50:00Z',
            job: { status: 'FAILED', attempts: 3 },
          }),
        ),
      ),
    )
    renderInvestigationDetail()

    expect(await screen.findByText('FAILED')).toBeInTheDocument()
    expect(screen.getByText(/worker attempts/i)).toHaveTextContent('3 / 3')
    expect(screen.getByText('The worker exhausted its retry limit.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'investigation-parent' })).toBeInTheDocument()
    expect(screen.getByText(/parent report remains unchanged/i)).toBeInTheDocument()
    expect(screen.getByText(/no browser retry control exists/i)).toBeInTheDocument()
  })

  it('polls only active investigations and delegates hidden-tab pausing to the query client', () => {
    const queued = buildInvestigation({ status: 'QUEUED' })
    const running = buildInvestigation({ status: 'RUNNING' })
    const awaitingReview = buildInvestigation({ status: 'AWAITING_REVIEW' })
    expect(investigationPollInterval(queued)).toBe(4_000)
    expect(investigationListPollInterval([awaitingReview, running])).toBe(4_000)
    expect(investigationPollInterval(awaitingReview)).toBe(false)
    expect(investigationListPollInterval([awaitingReview])).toBe(false)
  })
})
