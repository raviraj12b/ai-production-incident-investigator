import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { AppProviders } from '../app/AppProviders'
import { buildEvidence, buildInvestigation, buildReport } from '../test/fixtures'
import { server } from '../test/server'
import { EvidenceWorkspace } from './EvidenceWorkspace'

function renderWorkspace(status = 'AWAITING_REVIEW') {
  return render(
    <AppProviders>
      <EvidenceWorkspace investigation={buildInvestigation({ status })} />
    </AppProviders>,
  )
}

describe('evidence and report workspace', () => {
  it('renders evidence before analysis and resolves support, contradiction, and missing references', async () => {
    const log = buildEvidence()
    const trace = buildEvidence({
      id: 'evidence-002',
      kind: 'TRACE',
      observed_at: '2026-09-21T10:03:00Z',
      summary: 'Trace span observed',
      source_backend: 'jaeger',
      source_ref: 'jaeger:0123456789abcdef0123456789abcdef:0123456789abcdef',
    })
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () =>
        HttpResponse.json([log, trace]),
      ),
      http.get('*/api/v1/investigations/investigation-001/report', () =>
        HttpResponse.json(
          buildReport({
            hypotheses: [
              {
                id: 'hypothesis-001',
                explanation: 'The dependency error pattern may explain the incident.',
                confidence: 'MEDIUM',
                missing_evidence: ['CHANGE_FEED_NOT_CONFIGURED'],
                evidence: [
                  { evidence_id: log.id, relation: 'SUPPORTS' },
                  { evidence_id: trace.id, relation: 'CONTRADICTS' },
                  { evidence_id: 'missing-evidence-id', relation: 'SUPPORTS' },
                ],
              },
            ],
          }),
        ),
      ),
    )
    renderWorkspace()

    const evidenceHeading = await screen.findByRole('heading', {
      name: 'Chronological evidence timeline',
    })
    const analysisHeading = await screen.findByRole('heading', { name: 'Report and hypotheses' })
    expect(
      evidenceHeading.compareDocumentPosition(analysisHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.getAllByText('request_failed (HTTP 500)').length).toBeGreaterThan(0)
    expect(screen.getByText('Supporting evidence')).toBeInTheDocument()
    expect(screen.getByText('Contradicting evidence')).toBeInTheDocument()
    expect(screen.getByText('Evidence reference unavailable')).toBeInTheDocument()
    expect(screen.getByText(/change feed is not configured/i)).toBeInTheDocument()
    expect(screen.getByText('MEDIUM confidence')).toBeInTheDocument()
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
  })

  it('filters the complete bounded evidence set by kind', async () => {
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () =>
        HttpResponse.json([
          buildEvidence(),
          buildEvidence({
            id: 'evidence-002',
            kind: 'TRACE',
            summary: 'Trace span observed',
            source_backend: 'jaeger',
          }),
        ]),
      ),
      http.get('*/api/v1/investigations/investigation-001/report', () =>
        HttpResponse.json(buildReport()),
      ),
    )
    const user = userEvent.setup()
    renderWorkspace()

    const timeline = await screen.findByRole('list', { name: 'Evidence timeline' })
    expect(within(timeline).getByText('request_failed (HTTP 500)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'TRACE' }))

    expect(within(timeline).queryByText('request_failed (HTTP 500)')).not.toBeInTheDocument()
    expect(within(timeline).getByText('Trace span observed')).toBeInTheDocument()
  })

  it('renders an empty hypothesis list as valid abstention', async () => {
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () => HttpResponse.json([])),
      http.get('*/api/v1/investigations/investigation-001/report', () =>
        HttpResponse.json(
          buildReport({
            summary: 'The available evidence does not support a root-cause hypothesis.',
            uncertainty: 'Missing: NO_TRACES, CHANGE_FEED_NOT_CONFIGURED.',
            hypotheses: [],
          }),
        ),
      ),
    )
    renderWorkspace()

    expect(await screen.findByText('No supported hypothesis')).toBeInTheDocument()
    expect(screen.getByText(/analysis abstained/i)).toBeInTheDocument()
    expect(screen.getByText('NO_TRACES')).toBeInTheDocument()
    expect(screen.getByText('CHANGE_FEED_NOT_CONFIGURED')).toBeInTheDocument()
  })

  it('treats a report 404 during an active run as pending analysis', async () => {
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () => HttpResponse.json([])),
      http.get('*/api/v1/investigations/investigation-001/report', () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Report is not available' } },
          { status: 404 },
        ),
      ),
    )
    renderWorkspace('RUNNING')

    expect(await screen.findByText('Analysis is not available yet')).toBeInTheDocument()
    expect(screen.getByText(/without inventing interim conclusions/i)).toBeInTheDocument()
  })

  it('fetches the report again when an active investigation reaches review', async () => {
    let reportCalls = 0
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () => HttpResponse.json([])),
      http.get('*/api/v1/investigations/investigation-001/report', () => {
        reportCalls += 1
        return reportCalls === 1
          ? HttpResponse.json(
              { error: { code: 'NOT_FOUND', message: 'Report is not available' } },
              { status: 404 },
            )
          : HttpResponse.json(buildReport())
      }),
    )
    const view = renderWorkspace('RUNNING')

    await screen.findByText('Analysis is not available yet')
    view.rerender(
      <AppProviders>
        <EvidenceWorkspace investigation={buildInvestigation({ status: 'AWAITING_REVIEW' })} />
      </AppProviders>,
    )

    expect(
      await screen.findByText('Failures coincided with elevated checkout errors.'),
    ).toBeInTheDocument()
    expect(reportCalls).toBe(2)
  })

  it('keeps a valid report visible when evidence retrieval fails independently', async () => {
    server.use(
      http.get('*/api/v1/investigations/investigation-001/evidence', () =>
        HttpResponse.json(
          { error: { code: 'UNAVAILABLE', message: 'Evidence store is unavailable' } },
          { status: 503 },
        ),
      ),
      http.get('*/api/v1/investigations/investigation-001/report', () =>
        HttpResponse.json(buildReport()),
      ),
    )
    renderWorkspace()

    expect(await screen.findByText('Evidence is unavailable')).toBeInTheDocument()
    expect(
      screen.getByText('Failures coincided with elevated checkout errors.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Evidence reference not loaded')).toBeInTheDocument()
  })
})
