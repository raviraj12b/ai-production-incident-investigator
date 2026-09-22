import type { PageParams } from './types'

function page(params: PageParams = {}) {
  return { limit: params.limit ?? 20, offset: params.offset ?? 0 } as const
}

export const queryKeys = {
  incidents: {
    all: ['incidents'] as const,
    lists: ['incidents', 'list'] as const,
    list: (params?: PageParams) => ['incidents', 'list', page(params)] as const,
    detail: (incidentId: string) => ['incidents', 'detail', incidentId] as const,
    investigations: (incidentId: string, params?: PageParams) =>
      ['incidents', 'detail', incidentId, 'investigations', page(params)] as const,
  },
  investigations: {
    detail: (investigationId: string) => ['investigations', 'detail', investigationId] as const,
    evidence: (investigationId: string, params?: PageParams) =>
      ['investigations', 'detail', investigationId, 'evidence', page(params)] as const,
    report: (investigationId: string) =>
      ['investigations', 'detail', investigationId, 'report'] as const,
    review: (investigationId: string) =>
      ['investigations', 'detail', investigationId, 'review'] as const,
  },
}
