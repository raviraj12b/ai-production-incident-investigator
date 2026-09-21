import type { components } from './schema'

export type Evidence = components['schemas']['EvidenceOut']
export type Hypothesis = components['schemas']['HypothesisOut']
export type Incident = components['schemas']['IncidentOut']
export type IncidentCreate = components['schemas']['IncidentCreate']
export type IncidentUpdate = components['schemas']['IncidentUpdate']
export type Investigation = components['schemas']['InvestigationOut']
export type InvestigationCreate = components['schemas']['InvestigationCreate']
export type Report = components['schemas']['ReportOut']
export type Review = components['schemas']['ReviewOut']
export type ReviewPut = components['schemas']['ReviewPut']

export interface PageParams {
  limit?: number
  offset?: number
}

export interface ApiIssue {
  location: Array<string | number>
  message: string
}
