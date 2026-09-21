import { http, HttpResponse } from 'msw'

import { buildIncident } from './fixtures'

export const handlers = [
  http.get('http://localhost/api/v1/incidents', () => HttpResponse.json([buildIncident()])),
  http.post('http://localhost/api/v1/incidents', () =>
    HttpResponse.json(buildIncident(), { status: 201 }),
  ),
]
