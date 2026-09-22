import { http, HttpResponse } from 'msw'

import { buildIncident } from './fixtures'

export const handlers = [
  http.get('*/api/v1/incidents', () => HttpResponse.json([buildIncident()])),
  http.post('*/api/v1/incidents', () => HttpResponse.json(buildIncident(), { status: 201 })),
]
