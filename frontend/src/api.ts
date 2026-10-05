import type {
  ApiErrorBody,
  Category,
  Task,
  TaskCreatePayload,
  RuntimeInfo,
  TaskUpdatePayload,
  TaskListParams,
  Tag,
  Project,
  ProjectCreatePayload,
  ProjectStatus,
  ProjectUpdatePayload,
  RecurrenceCreatePayload,
  RecurrenceRule,
  RecurrenceUpdatePayload,
  Reminder,
  ReminderPayload,
  Backup,
  BackupVerification,
  ReviewResponse,
  ReviewScope,
} from './types'

const API_BASE = '/api/v1'

export const reviewApi = {
  get(scope: ReviewScope): Promise<ReviewResponse> {
    return request<ReviewResponse>(`/review?scope=${encodeURIComponent(scope)}`)
  },
}

export const backupApi = {
  list(): Promise<Backup[]> { return request<Backup[]>('/backups') },
  create(): Promise<Backup> { return request<Backup>('/backups', { method: 'POST' }) },
  verify(id: string): Promise<BackupVerification> {
    return request<BackupVerification>(`/backups/${encodeURIComponent(id)}/verify`, { method: 'POST' })
  },
}

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
  get(id: string): Promise<Task> {
    return request<Task>(`/tasks/${encodeURIComponent(id)}`)
  },

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

  list(params: TaskListParams = {}): Promise<Task[]> {
    const query = new URLSearchParams()
    if (params.inbox) query.set('inbox', 'true')
    if (params.query) query.set('q', params.query)
    if (params.priority) query.set('priority', params.priority)
    if (params.categoryId) query.set('category_id', params.categoryId)
    if (params.tagId) query.set('tag_id', params.tagId)
    if (params.projectId) query.set('project_id', params.projectId)
    if (params.status) query.set('status', params.status)
    if (params.overdue) query.set('overdue', 'true')
    if (params.plannedBucket) query.set('planned_bucket', params.plannedBucket)
    if (params.sort) query.set('sort', params.sort)
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

export const recurrenceApi = {
  create(taskId: string, payload: RecurrenceCreatePayload): Promise<RecurrenceRule> {
    return request<RecurrenceRule>(
      `/tasks/${encodeURIComponent(taskId)}/recurrence`,
      jsonRequest('POST', payload),
    )
  },

  get(ruleId: string): Promise<RecurrenceRule> {
    return request<RecurrenceRule>(`/recurrence-rules/${encodeURIComponent(ruleId)}`)
  },

  update(ruleId: string, version: number, payload: RecurrenceUpdatePayload): Promise<RecurrenceRule> {
    return request<RecurrenceRule>(
      `/recurrence-rules/${encodeURIComponent(ruleId)}?version=${encodeURIComponent(String(version))}`,
      jsonRequest('PATCH', payload),
    )
  },

  stop(ruleId: string, version: number): Promise<RecurrenceRule> {
    return request<RecurrenceRule>(
      `/recurrence-rules/${encodeURIComponent(ruleId)}/stop`,
      jsonRequest('POST', { version }),
    )
  },

  materialize(ruleId: string): Promise<Task> {
    return request<Task>(`/recurrence-rules/${encodeURIComponent(ruleId)}/materialize`, {
      method: 'POST',
    })
  },

  skip(taskId: string, version: number): Promise<Task> {
    return request<Task>(
      `/tasks/${encodeURIComponent(taskId)}/skip`,
      jsonRequest('POST', { version }),
    )
  },
}

export const reminderApi = {
  list(taskId: string): Promise<Reminder[]> {
    return request<Reminder[]>(`/tasks/${encodeURIComponent(taskId)}/reminders`)
  },

  create(taskId: string, payload: ReminderPayload): Promise<Reminder> {
    return request<Reminder>(
      `/tasks/${encodeURIComponent(taskId)}/reminders`,
      jsonRequest('POST', payload),
    )
  },

  due(): Promise<Reminder[]> {
    return request<Reminder[]>('/reminders/due')
  },

  update(reminderId: string, version: number, payload: ReminderPayload): Promise<Reminder> {
    return request<Reminder>(
      `/reminders/${encodeURIComponent(reminderId)}?version=${encodeURIComponent(String(version))}`,
      jsonRequest('PATCH', payload),
    )
  },

  remove(reminderId: string, version: number): Promise<void> {
    return request<void>(
      `/reminders/${encodeURIComponent(reminderId)}`,
      jsonRequest('DELETE', { version }),
    )
  },

  acknowledge(reminderId: string, version: number): Promise<Reminder> {
    return request<Reminder>(
      `/reminders/${encodeURIComponent(reminderId)}/acknowledge`,
      jsonRequest('POST', { version }),
    )
  },

  dismiss(reminderId: string, version: number): Promise<Reminder> {
    return request<Reminder>(
      `/reminders/${encodeURIComponent(reminderId)}/dismiss`,
      jsonRequest('POST', { version }),
    )
  },
}

export const projectApi = {
  list(params: { includeDeleted?: boolean; status?: ProjectStatus } = {}): Promise<Project[]> {
    const query = new URLSearchParams()
    if (params.includeDeleted) query.set('include_deleted', 'true')
    if (params.status) query.set('status', params.status)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request<Project[]>(`/projects${suffix}`)
  },

  get(id: string): Promise<Project> {
    return request<Project>(`/projects/${encodeURIComponent(id)}`)
  },

  create(payload: ProjectCreatePayload): Promise<Project> {
    return request<Project>('/projects', jsonRequest('POST', payload))
  },

  update(id: string, version: number, payload: ProjectUpdatePayload): Promise<Project> {
    return request<Project>(
      `/projects/${encodeURIComponent(id)}?version=${encodeURIComponent(String(version))}`,
      jsonRequest('PATCH', payload),
    )
  },

  complete(id: string, version: number): Promise<Project> {
    return request<Project>(
      `/projects/${encodeURIComponent(id)}/complete`,
      jsonRequest('POST', { version }),
    )
  },

  reopen(id: string, version: number): Promise<Project> {
    return request<Project>(
      `/projects/${encodeURIComponent(id)}/reopen`,
      jsonRequest('POST', { version }),
    )
  },

  restore(id: string, version: number): Promise<Project> {
    return request<Project>(
      `/projects/${encodeURIComponent(id)}/restore`,
      jsonRequest('POST', { version }),
    )
  },

  remove(id: string, version: number): Promise<void> {
    return request<void>(
      `/projects/${encodeURIComponent(id)}`,
      jsonRequest('DELETE', { version }),
    )
  },
}
