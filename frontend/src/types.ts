export type TaskStatus = 'pending' | 'completed'

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  planned_date: string | null
  created_at_utc: string
  updated_at_utc: string
  completed_at_utc: string | null
  deleted_at_utc: string | null
  version: number
}

export interface TaskCreatePayload {
  title: string
  description: string | null
  planned_date: string | null
}

export interface TaskUpdatePayload {
  title?: string
  description?: string | null
  planned_date?: string | null
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}
