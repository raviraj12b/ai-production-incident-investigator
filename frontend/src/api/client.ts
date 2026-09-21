import type { ApiIssue } from './types'

interface ApiErrorDetails {
  status: number
  code: string
  message: string
  issues?: ApiIssue[]
  requestId?: string
}

interface RequestOptions extends Omit<RequestInit, 'body' | 'headers'> {
  bearerToken?: string
  body?: unknown
  headers?: HeadersInit
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly issues: ApiIssue[]
  readonly requestId: string | undefined

  constructor({ status, code, message, issues = [], requestId }: ApiErrorDetails) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.issues = issues
    this.requestId = requestId
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseIssues(value: unknown): ApiIssue[] {
  if (!Array.isArray(value)) return []

  return value.flatMap((issue) => {
    if (!isRecord(issue) || !Array.isArray(issue.location) || typeof issue.message !== 'string') {
      return []
    }
    const location = issue.location.filter(
      (part): part is string | number => typeof part === 'string' || typeof part === 'number',
    )
    return [{ location, message: issue.message }]
  })
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const requestId = response.headers.get('x-request-id') ?? undefined
  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    payload = undefined
  }

  if (isRecord(payload) && isRecord(payload.error)) {
    const code =
      typeof payload.error.code === 'string' ? payload.error.code : `HTTP_${response.status}`
    const message =
      typeof payload.error.message === 'string'
        ? payload.error.message
        : `Request failed with status ${response.status}`
    return new ApiError({
      status: response.status,
      code,
      message,
      issues: parseIssues(payload.error.issues),
      ...(requestId ? { requestId } : {}),
    })
  }

  return new ApiError({
    status: response.status,
    code: `HTTP_${response.status}`,
    message: `Request failed with status ${response.status}`,
    ...(requestId ? { requestId } : {}),
  })
}

export class ApiClient {
  private readonly fetchImpl: typeof fetch | undefined

  constructor(
    private readonly baseUrl = '',
    fetchImpl?: typeof fetch,
  ) {
    this.fetchImpl = fetchImpl
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json')
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    if (options.bearerToken) headers.set('Authorization', `Bearer ${options.bearerToken}`)

    const { bearerToken, body, ...requestInit } = options
    void bearerToken

    let response: Response
    try {
      response = await (this.fetchImpl ?? fetch)(`${this.baseUrl}${path}`, {
        ...requestInit,
        headers,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      })
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError({
        status: 0,
        code: 'NETWORK_ERROR',
        message: 'The API could not be reached',
      })
    }

    if (!response.ok) throw await errorFromResponse(response)

    try {
      return (await response.json()) as T
    } catch {
      throw new ApiError({
        status: response.status,
        code: 'INVALID_RESPONSE',
        message: 'The API returned an unreadable response',
      })
    }
  }
}

export const apiClient = new ApiClient()
