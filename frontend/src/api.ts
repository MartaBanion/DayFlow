import type {
  ApiErrorBody,
  Task,
  TaskCreatePayload,
  TaskUpdatePayload,
} from './types'

const API_BASE = '/api/v1'

export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string | undefined

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    let body: ApiErrorBody = {}
    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // Keep the HTTP status as the useful error when the server returned no JSON.
    }
    throw new ApiRequestError(
      body.error?.message ?? `Request failed with status ${response.status}`,
      response.status,
      body.error?.code,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    body: JSON.stringify(body),
  }
}

export const taskApi = {
  listToday(date: string): Promise<Task[]> {
    return request<Task[]>(`/today?date=${encodeURIComponent(date)}`)
  },

  create(payload: TaskCreatePayload): Promise<Task> {
    return request<Task>('/tasks', jsonRequest('POST', payload))
  },

  update(id: string, version: number, payload: TaskUpdatePayload): Promise<Task> {
    return request<Task>(
      `/tasks/${encodeURIComponent(id)}?version=${version}`,
      jsonRequest('PATCH', payload),
    )
  },

  complete(id: string, version: number): Promise<Task> {
    return request<Task>(
      `/tasks/${encodeURIComponent(id)}/complete`,
      jsonRequest('POST', { version }),
    )
  },

  restore(id: string, version: number): Promise<Task> {
    return request<Task>(
      `/tasks/${encodeURIComponent(id)}/restore`,
      jsonRequest('POST', { version }),
    )
  },

  remove(id: string, version: number): Promise<void> {
    return request<void>(
      `/tasks/${encodeURIComponent(id)}`,
      jsonRequest('DELETE', { version }),
    )
  },
}
