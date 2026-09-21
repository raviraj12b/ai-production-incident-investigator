import type { Incident, Investigation, Review } from '../api/types'

export function buildIncident(overrides: Partial<Incident> = {}): Incident {
  return {
    id: 'incident-001',
    title: 'Checkout latency increase',
    description: 'Customer requests exceeded the expected latency window.',
    service: 'checkout-api',
    severity: 'HIGH',
    status: 'OPEN',
    window_start: '2026-09-21T10:00:00Z',
    window_end: '2026-09-21T10:30:00Z',
    created_at: '2026-09-21T10:35:00Z',
    updated_at: '2026-09-21T10:35:00Z',
    ...overrides,
  }
}

export function buildInvestigation(overrides: Partial<Investigation> = {}): Investigation {
  return {
    id: 'investigation-001',
    incident_id: 'incident-001',
    parent_id: null,
    status: 'QUEUED',
    focus: null,
    window_start: '2026-09-21T10:00:00Z',
    window_end: '2026-09-21T10:30:00Z',
    created_at: '2026-09-21T10:36:00Z',
    started_at: null,
    finished_at: null,
    error: null,
    job: { status: 'PENDING', attempts: 0 },
    ...overrides,
  }
}

export function buildReview(overrides: Partial<Review> = {}): Review {
  return {
    id: 'review-001',
    investigation_id: 'investigation-001',
    decision: 'INCONCLUSIVE',
    reviewer: 'reviewer@example.com',
    comment: 'More evidence is required.',
    created_at: '2026-09-21T10:50:00Z',
    ...overrides,
  }
}
