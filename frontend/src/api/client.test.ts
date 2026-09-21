import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ApiClient, ApiError } from './client'
import { createApi } from './endpoints'
import { buildIncident, buildReview } from '../test/fixtures'
import { server } from '../test/server'

const origin = 'http://localhost'
const api = createApi(new ApiClient(origin))

async function expectApiError(request: Promise<unknown>): Promise<ApiError> {
  try {
    await request
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('Expected request to reject')
}

describe('API contract boundary', () => {
  it('returns a typed successful response and preserves pagination', async () => {
    const incident = buildIncident()
    server.use(
      http.get(`${origin}/api/v1/incidents`, ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.get('limit')).toBe('10')
        expect(url.searchParams.get('offset')).toBe('20')
        return HttpResponse.json([incident])
      }),
    )

    await expect(api.listIncidents({ limit: 10, offset: 20 })).resolves.toEqual([incident])
  })

  it('normalizes validation issues from the product error envelope', async () => {
    server.use(
      http.get(`${origin}/api/v1/incidents`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Invalid request',
              issues: [{ location: ['query', 'limit'], message: 'Input should be less than 101' }],
            },
          },
          { status: 422, headers: { 'x-request-id': 'request-422' } },
        ),
      ),
    )

    const error = await expectApiError(api.listIncidents({ limit: 101 }))
    expect(error).toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'Invalid request',
      requestId: 'request-422',
      issues: [{ location: ['query', 'limit'], message: 'Input should be less than 101' }],
    })
  })

  it('normalizes a conflict and sends the required idempotency key', async () => {
    server.use(
      http.post(`${origin}/api/v1/incidents`, async ({ request }) => {
        expect(request.headers.get('Idempotency-Key')).toBe('incident-create-001')
        return HttpResponse.json(
          { error: { code: 'CONFLICT', message: 'Idempotency-Key was used with another payload' } },
          { status: 409 },
        )
      }),
    )

    const error = await expectApiError(
      api.createIncident(
        {
          title: 'Checkout latency increase',
          description: '',
          service: 'checkout-api',
          severity: 'HIGH',
          window_start: '2026-09-21T10:00:00Z',
          window_end: '2026-09-21T10:30:00Z',
        },
        'incident-create-001',
      ),
    )
    expect(error).toMatchObject({ status: 409, code: 'CONFLICT' })
  })

  it('normalizes an unavailable dependency', async () => {
    server.use(
      http.get(`${origin}/api/v1/incidents`, () =>
        HttpResponse.json(
          { error: { code: 'DATABASE_UNAVAILABLE', message: 'Product database error' } },
          { status: 503 },
        ),
      ),
    )

    const error = await expectApiError(api.listIncidents())
    expect(error).toMatchObject({
      status: 503,
      code: 'DATABASE_UNAVAILABLE',
      message: 'Product database error',
    })
  })

  it('uses a safe fallback for malformed non-JSON errors', async () => {
    server.use(
      http.get(
        `${origin}/api/v1/incidents`,
        () =>
          new HttpResponse('<h1>upstream failed</h1>', {
            status: 502,
            headers: { 'Content-Type': 'text/html', 'x-request-id': 'request-502' },
          }),
      ),
    )

    const error = await expectApiError(api.listIncidents())
    expect(error).toMatchObject({
      status: 502,
      code: 'HTTP_502',
      message: 'Request failed with status 502',
      requestId: 'request-502',
      issues: [],
    })
  })

  it('scopes bearer credentials to review requests', async () => {
    server.use(
      http.get(`${origin}/api/v1/investigations/investigation-001/review`, ({ request }) => {
        expect(request.headers.get('Authorization')).toBe('Bearer local-reviewer-token')
        return HttpResponse.json(buildReview())
      }),
      http.get(`${origin}/api/v1/incidents`, ({ request }) => {
        expect(request.headers.has('Authorization')).toBe(false)
        return HttpResponse.json([buildIncident()])
      }),
    )

    await expect(api.getReview('investigation-001', 'local-reviewer-token')).resolves.toEqual(
      buildReview(),
    )
    await expect(api.listIncidents()).resolves.toEqual([buildIncident()])
  })
})
