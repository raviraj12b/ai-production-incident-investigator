import { apiClient, type ApiClient } from './client'
import type {
  Evidence,
  Incident,
  IncidentCreate,
  IncidentUpdate,
  Investigation,
  InvestigationCreate,
  PageParams,
  Report,
  Review,
  ReviewPut,
} from './types'

function resourceId(value: string): string {
  return encodeURIComponent(value)
}

function pageQuery(params: PageParams = {}): string {
  const search = new URLSearchParams()
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  const query = search.toString()
  return query ? `?${query}` : ''
}

export function createApi(client: ApiClient = apiClient) {
  return {
    getReadiness: () => client.request<{ status: string }>('/ready'),
    listIncidents: (params?: PageParams) =>
      client.request<Incident[]>(`/api/v1/incidents${pageQuery(params)}`),
    getIncident: (incidentId: string) =>
      client.request<Incident>(`/api/v1/incidents/${resourceId(incidentId)}`),
    createIncident: (body: IncidentCreate, idempotencyKey: string) =>
      client.request<Incident>('/api/v1/incidents', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body,
      }),
    updateIncident: (incidentId: string, body: IncidentUpdate) =>
      client.request<Incident>(`/api/v1/incidents/${resourceId(incidentId)}`, {
        method: 'PATCH',
        body,
      }),
    listInvestigations: (incidentId: string, params?: PageParams) =>
      client.request<Investigation[]>(
        `/api/v1/incidents/${resourceId(incidentId)}/investigations${pageQuery(params)}`,
      ),
    createInvestigation: (incidentId: string, body: InvestigationCreate, idempotencyKey: string) =>
      client.request<Investigation>(`/api/v1/incidents/${resourceId(incidentId)}/investigations`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body,
      }),
    getInvestigation: (investigationId: string) =>
      client.request<Investigation>(`/api/v1/investigations/${resourceId(investigationId)}`),
    listEvidence: (investigationId: string, params?: PageParams) =>
      client.request<Evidence[]>(
        `/api/v1/investigations/${resourceId(investigationId)}/evidence${pageQuery(params)}`,
      ),
    getReport: (investigationId: string) =>
      client.request<Report>(`/api/v1/investigations/${resourceId(investigationId)}/report`),
    getReview: (investigationId: string, reviewerToken: string) =>
      client.request<Review>(`/api/v1/investigations/${resourceId(investigationId)}/review`, {
        bearerToken: reviewerToken,
      }),
    putReview: (investigationId: string, body: ReviewPut, reviewerToken: string) =>
      client.request<Review>(`/api/v1/investigations/${resourceId(investigationId)}/review`, {
        method: 'PUT',
        bearerToken: reviewerToken,
        body,
      }),
  }
}

export const api = createApi()
