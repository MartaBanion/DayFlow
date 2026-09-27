import type {
  ApiErrorBody,
  Category,
  Task,
  TaskCreatePayload,
  TaskPriority,
  RuntimeInfo,
  TaskUpdatePayload,
  Tag,
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

  getRuntime(): Promise<RuntimeInfo> {
    return request<RuntimeInfo>('/runtime')
  },

  listCalendar(start: string, end: string): Promise<Task[]> {
    const query = new URLSearchParams({ start, end })
    return request<Task[]>(`/calendar?${query.toString()}`)
  },

  list(params: {
    inbox?: boolean
    query?: string
    priority?: TaskPriority
    categoryId?: string
    tagId?: string
  } = {}): Promise<Task[]> {
    const query = new URLSearchParams()
    if (params.inbox) query.set('inbox', 'true')
    if (params.query) query.set('q', params.query)
    if (params.priority) query.set('priority', params.priority)
    if (params.categoryId) query.set('category_id', params.categoryId)
    if (params.tagId) query.set('tag_id', params.tagId)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request<Task[]>(`/tasks${suffix}`)
  },

  listCategories(): Promise<Category[]> {
    return request<Category[]>('/categories')
  },

  createCategory(name: string): Promise<Category> {
    return request<Category>('/categories', jsonRequest('POST', { name }))
  },

  updateCategory(id: string, name: string): Promise<Category> {
    return request<Category>(
      `/categories/${encodeURIComponent(id)}`,
      jsonRequest('PATCH', { name }),
    )
  },

  removeCategory(id: string): Promise<void> {
    return request<void>(
      `/categories/${encodeURIComponent(id)}`,
      jsonRequest('DELETE', undefined),
    )
  },

  listTags(): Promise<Tag[]> {
    return request<Tag[]>('/tags')
  },

  createTag(name: string): Promise<Tag> {
    return request<Tag>('/tags', jsonRequest('POST', { name }))
  },

  updateTag(id: string, name: string): Promise<Tag> {
    return request<Tag>(
      `/tags/${encodeURIComponent(id)}`,
      jsonRequest('PATCH', { name }),
    )
  },

  removeTag(id: string): Promise<void> {
    return request<void>(
      `/tags/${encodeURIComponent(id)}`,
      jsonRequest('DELETE', undefined),
    )
  },

  create(
    payload: TaskCreatePayload,
    options: { allowScheduleConflict?: boolean } = {},
  ): Promise<Task> {
    const query = options.allowScheduleConflict ? '?allow_schedule_conflict=true' : ''
    return request<Task>(`/tasks${query}`, jsonRequest('POST', payload))
  },

  update(
    id: string,
    version: number,
    payload: TaskUpdatePayload,
    options: { allowScheduleConflict?: boolean } = {},
  ): Promise<Task> {
    const query = new URLSearchParams({ version: String(version) })
    if (options.allowScheduleConflict) query.set('allow_schedule_conflict', 'true')
    return request<Task>(
      `/tasks/${encodeURIComponent(id)}?${query.toString()}`,
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
