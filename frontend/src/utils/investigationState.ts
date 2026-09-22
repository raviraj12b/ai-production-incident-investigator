import type { Investigation } from '../api/types'

const ACTIVE_STATES = new Set(['QUEUED', 'RUNNING'])

export function isActiveInvestigation(investigation: Investigation): boolean {
  return ACTIVE_STATES.has(investigation.status)
}

export function investigationPollInterval(investigation?: Investigation): number | false {
  if (!investigation || !isActiveInvestigation(investigation)) return false
  return 4_000
}

export function investigationListPollInterval(investigations?: Investigation[]): number | false {
  if (!investigations?.some(isActiveInvestigation)) return false
  return 4_000
}

const failureMessages: Record<string, string> = {
  ATTEMPTS_EXHAUSTED: 'The worker exhausted its retry limit.',
  PROCESSOR_ERROR: 'The investigation processor could not complete the run.',
  TELEMETRY_UNAVAILABLE: 'Required telemetry was unavailable.',
  MODEL_UNAVAILABLE: 'The configured analysis model was unavailable.',
  RESULT_INVALID: 'The analysis result did not satisfy the required contract.',
}

export function investigationFailureMessage(error: string | null): string {
  if (!error) return 'The investigation did not complete.'
  return failureMessages[error] ?? 'The investigation failed with an unrecognized safe error code.'
}
