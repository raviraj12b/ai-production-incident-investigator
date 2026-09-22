import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AppProviders } from '../app/AppProviders'
import { buildIncident } from '../test/fixtures'
import { server } from '../test/server'
import { IncidentDetailPage } from './IncidentDetailPage'
import { IncidentsPage } from './IncidentsPage'
import { NewIncidentPage } from './NewIncidentPage'

function renderPage(path: string, element: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppProviders>
        <Routes>
          <Route path="/incidents" element={element} />
          <Route path="/incidents/new" element={element} />
          <Route path="/incidents/:incidentId" element={element} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  )
}

describe('incident list', () => {
  it('shows an honest empty state and disables heuristic next navigation', async () => {
    server.use(http.get('*/api/v1/incidents', () => HttpResponse.json([])))
    renderPage('/incidents', <IncidentsPage />)

    expect(await screen.findByText('No incidents yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('requests the next offset only when a full page is returned', async () => {
    const offsets: string[] = []
    server.use(
      http.get('*/api/v1/incidents', ({ request }) => {
        const offset = new URL(request.url).searchParams.get('offset') ?? ''
        offsets.push(offset)
        return HttpResponse.json(
          offset === '20'
            ? [buildIncident({ id: 'incident-next', title: 'Next page incident' })]
            : Array.from({ length: 20 }, (_, index) =>
                buildIncident({ id: `incident-${index}`, title: `Incident ${index}` }),
              ),
        )
      }),
    )
    const user = userEvent.setup()
    renderPage('/incidents', <IncidentsPage />)

    await screen.findByText('Incident 0')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Next page incident')).toBeInTheDocument()
    expect(offsets).toEqual(['0', '20'])
  })
})

describe('manual incident intake', () => {
  it('validates the time window before sending a request', async () => {
    const createRequest = vi.fn()
    server.use(http.post('*/api/v1/incidents', createRequest))
    const user = userEvent.setup()
    renderPage('/incidents/new', <NewIncidentPage />)

    await user.type(screen.getByLabelText('Title'), 'API latency')
    await user.type(screen.getByLabelText('Service'), 'orders-api')
    await user.type(screen.getByLabelText(/window start/i), '2026-09-21T11:00')
    await user.type(screen.getByLabelText(/window end/i), '2026-09-21T10:00')
    await user.click(screen.getByRole('button', { name: 'Create incident' }))

    expect(
      await screen.findByText('Window end must be later than window start'),
    ).toBeInTheDocument()
    expect(createRequest).not.toHaveBeenCalled()
  })

  it('reuses a key for an unchanged retry and replaces it after an edit', async () => {
    const keys: string[] = []
    const bodies: unknown[] = []
    let attempts = 0
    server.use(
      http.post('*/api/v1/incidents', async ({ request }) => {
        keys.push(request.headers.get('Idempotency-Key') ?? '')
        bodies.push(await request.json())
        attempts += 1
        if (attempts < 3) return HttpResponse.error()
        return HttpResponse.json(buildIncident({ title: 'Edited title' }), { status: 201 })
      }),
      http.get('*/api/v1/incidents/incident-001', () =>
        HttpResponse.json(buildIncident({ title: 'Edited title' })),
      ),
    )
    const user = userEvent.setup()
    renderPage('/incidents/new', <NewIncidentPage />)

    const title = screen.getByLabelText('Title')
    await user.type(title, 'Original title')
    await user.type(screen.getByLabelText('Service'), 'orders-api')
    await user.type(screen.getByLabelText(/window start/i), '2026-09-21T10:00')
    await user.type(screen.getByLabelText(/window end/i), '2026-09-21T11:00')

    await user.click(screen.getByRole('button', { name: 'Create incident' }))
    await screen.findByText('Incident was not created')
    await user.click(screen.getByRole('button', { name: 'Create incident' }))
    await screen.findByText('Incident was not created')
    await user.clear(title)
    await user.type(title, 'Edited title')
    await user.click(screen.getByRole('button', { name: 'Create incident' }))

    await waitFor(() => expect(keys).toHaveLength(3))
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
    expect(keys[2]).not.toBe(keys[1])
    expect(bodies[2]).toMatchObject({
      title: 'Edited title',
      window_start: '2026-09-21T10:00:00.000Z',
      window_end: '2026-09-21T11:00:00.000Z',
    })
  })

  it('maps backend validation issues to their fields', async () => {
    server.use(
      http.post('*/api/v1/incidents', () =>
        HttpResponse.json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Request validation failed',
              issues: [{ location: ['body', 'service'], message: 'Unknown service' }],
            },
          },
          { status: 422 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderPage('/incidents/new', <NewIncidentPage />)

    await user.type(screen.getByLabelText('Title'), 'API latency')
    await user.type(screen.getByLabelText('Service'), 'unknown-api')
    await user.type(screen.getByLabelText(/window start/i), '2026-09-21T10:00')
    await user.type(screen.getByLabelText(/window end/i), '2026-09-21T11:00')
    await user.click(screen.getByRole('button', { name: 'Create incident' }))

    expect(await screen.findByText('Unknown service')).toBeInTheDocument()
  })
})

describe('incident detail', () => {
  it('loads immutable metadata and patches only supported editable fields', async () => {
    let patchBody: unknown
    server.use(
      http.get('*/api/v1/incidents/incident-001', () => HttpResponse.json(buildIncident())),
      http.patch('*/api/v1/incidents/incident-001', async ({ request }) => {
        patchBody = await request.json()
        return HttpResponse.json(buildIncident({ title: 'Updated checkout latency' }))
      }),
    )
    const user = userEvent.setup()
    renderPage('/incidents/incident-001', <IncidentDetailPage />)

    expect(
      await screen.findByRole('heading', { name: 'Checkout latency increase' }),
    ).toBeInTheDocument()
    expect(screen.getByText('checkout-api')).toBeInTheDocument()
    const title = screen.getByLabelText('Title')
    await user.clear(title)
    await user.type(title, 'Updated checkout latency')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(patchBody).toEqual({
        title: 'Updated checkout latency',
        description: 'Customer requests exceeded the expected latency window.',
        severity: 'HIGH',
      }),
    )
    expect(
      await screen.findByRole('heading', { name: 'Updated checkout latency' }),
    ).toBeInTheDocument()
  })
})
