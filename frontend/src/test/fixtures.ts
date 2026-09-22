import type { Evidence, Incident, Investigation, Report, Review } from '../api/types'

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
    job: { status: 'QUEUED', attempts: 0 },
    ...overrides,
  }
}

export function buildEvidence(overrides: Partial<Evidence> = {}): Evidence {
  return {
    id: 'evidence-001',
    investigation_id: 'investigation-001',
    kind: 'LOG',
    observed_at: '2026-09-21T10:02:00Z',
    service: 'checkout-api',
    summary: 'request_failed (HTTP 500)',
    source_backend: 'loki',
    source_ref: 'loki:1789984920000000000:0123456789abcdef01234567',
    trace_id: '0123456789abcdef0123456789abcdef',
    captured_at: '2026-09-21T10:40:00Z',
    ...overrides,
  }
}

export function buildReport(overrides: Partial<Report> = {}): Report {
  return {
    id: 'report-001',
    investigation_id: 'investigation-001',
    summary: 'Failures coincided with elevated checkout errors.',
    uncertainty: 'Missing: CHANGE_FEED_NOT_CONFIGURED.',
    created_at: '2026-09-21T10:48:00Z',
    hypotheses: [
      {
        id: 'hypothesis-001',
        explanation: 'The checkout dependency returned elevated errors.',
        confidence: 'MEDIUM',
        missing_evidence: ['CHANGE_FEED_NOT_CONFIGURED'],
        evidence: [{ evidence_id: 'evidence-001', relation: 'SUPPORTS' }],
      },
    ],
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
