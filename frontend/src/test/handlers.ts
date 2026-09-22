import { http, HttpResponse } from 'msw'

import { buildIncident, buildInvestigation } from './fixtures'

export const handlers = [
  http.get('*/ready', () => HttpResponse.json({ status: 'ready' })),
  http.get('*/api/v1/incidents', () => HttpResponse.json([buildIncident()])),
  http.post('*/api/v1/incidents', () => HttpResponse.json(buildIncident(), { status: 201 })),
  http.get('*/api/v1/incidents/:incidentId/investigations', () => HttpResponse.json([])),
  http.get('*/api/v1/investigations/:investigationId', ({ params }) =>
    HttpResponse.json(buildInvestigation({ id: String(params.investigationId) })),
  ),
  http.get('*/api/v1/investigations/:investigationId/evidence', () => HttpResponse.json([])),
  http.get('*/api/v1/investigations/:investigationId/report', () =>
    HttpResponse.json(
      { error: { code: 'NOT_FOUND', message: 'Report is not available' } },
      { status: 404 },
    ),
  ),
]
