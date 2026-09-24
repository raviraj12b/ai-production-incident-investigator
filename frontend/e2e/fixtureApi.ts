import type { Page, Route } from '@playwright/test'

const incident = {
  id: 'incident-e2e',
  title: 'Checkout fixture incident',
  description: 'Fixture-driven browser workflow.',
  service: 'checkout-api',
  severity: 'HIGH',
  status: 'OPEN',
  window_start: '2026-09-21T10:00:00Z',
  window_end: '2026-09-21T10:30:00Z',
  created_at: '2026-09-21T10:35:00Z',
  updated_at: '2026-09-21T10:35:00Z',
}

const evidence = {
  id: 'evidence-e2e',
  investigation_id: 'investigation-e2e',
  kind: 'LOG',
  observed_at: '2026-09-21T10:02:00Z',
  service: 'checkout-api',
  summary: 'Fixture checkout requests returned HTTP 500.',
  source_backend: 'loki',
  source_ref: 'loki:fixture-evidence-reference',
  trace_id: '0123456789abcdef0123456789abcdef',
  captured_at: '2026-09-21T10:40:00Z',
}

const report = {
  id: 'report-e2e',
  investigation_id: 'investigation-e2e',
  summary: 'Fixture evidence shows elevated checkout errors during the incident window.',
  uncertainty: 'Missing: CHANGE_FEED_NOT_CONFIGURED.',
  created_at: '2026-09-21T10:48:00Z',
  hypotheses: [
    {
      id: 'hypothesis-e2e',
      explanation: 'The observed checkout errors may explain the reported incident.',
      confidence: 'MEDIUM',
      missing_evidence: ['CHANGE_FEED_NOT_CONFIGURED'],
      evidence: [{ evidence_id: evidence.id, relation: 'SUPPORTS' }],
    },
  ],
}

export interface FixtureCaptures {
  incidentBody?: Record<string, unknown>
  incidentIdempotencyKey?: string | null
  investigationBody?: Record<string, unknown>
  investigationIdempotencyKey?: string | null
  reviewAuthorization?: string | null
  reviewBody?: Record<string, unknown>
}

export async function installFixtureApi(page: Page): Promise<FixtureCaptures> {
  const captures: FixtureCaptures = {}
  let investigationStatus = 'AWAITING_REVIEW'

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (path === '/ready') return json(route, { status: 'ready' })

    if (path === '/api/v1/incidents' && method === 'POST') {
      captures.incidentBody = request.postDataJSON() as Record<string, unknown>
      captures.incidentIdempotencyKey = request.headers()['idempotency-key'] ?? null
      return json(route, incident, 201)
    }
    if (path === '/api/v1/incidents' && method === 'GET') return json(route, [incident])
    if (path === `/api/v1/incidents/${incident.id}` && method === 'GET') {
      return json(route, incident)
    }

    if (path === `/api/v1/incidents/${incident.id}/investigations` && method === 'POST') {
      captures.investigationBody = request.postDataJSON() as Record<string, unknown>
      captures.investigationIdempotencyKey = request.headers()['idempotency-key'] ?? null
      return json(route, investigation('QUEUED'), 202)
    }
    if (path === `/api/v1/incidents/${incident.id}/investigations` && method === 'GET') {
      return json(route, [])
    }

    if (path === '/api/v1/investigations/investigation-e2e' && method === 'GET') {
      return json(route, investigation(investigationStatus))
    }
    if (path === '/api/v1/investigations/investigation-e2e/evidence' && method === 'GET') {
      return json(route, [evidence])
    }
    if (path === '/api/v1/investigations/investigation-e2e/report' && method === 'GET') {
      return json(route, report)
    }
    if (path === '/api/v1/investigations/investigation-e2e/review' && method === 'PUT') {
      captures.reviewAuthorization = request.headers().authorization ?? null
      captures.reviewBody = request.postDataJSON() as Record<string, unknown>
      investigationStatus = 'COMPLETED'
      return json(route, {
        id: 'review-e2e',
        investigation_id: 'investigation-e2e',
        decision: captures.reviewBody.decision,
        reviewer: 'fixture-reviewer',
        comment: captures.reviewBody.comment,
        created_at: '2026-09-21T10:50:00Z',
      })
    }

    if (path.startsWith('/api/v1/')) {
      return json(
        route,
        { error: { code: 'UNEXPECTED_E2E_REQUEST', message: `${method} ${path}` } },
        500,
      )
    }
    await route.continue()
  })

  return captures
}

function investigation(status: string) {
  return {
    id: 'investigation-e2e',
    incident_id: incident.id,
    parent_id: null,
    status,
    focus: 'Checkout errors during fixture window',
    window_start: incident.window_start,
    window_end: incident.window_end,
    created_at: '2026-09-21T10:36:00Z',
    started_at: '2026-09-21T10:37:00Z',
    finished_at: '2026-09-21T10:48:00Z',
    error: null,
    job: { status: status === 'COMPLETED' ? 'DONE' : 'AWAITING_REVIEW', attempts: 1 },
  }
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}
