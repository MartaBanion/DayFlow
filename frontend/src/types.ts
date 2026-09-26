export type TaskStatus = 'pending' | 'completed'
export type TaskPriority = 'low' | 'normal' | 'high'

export interface Category {
  id: string
  name: string
}

export interface Tag {
  id: string
  name: string
}

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  planned_date: string | null
  priority: TaskPriority
  category: Category | null
  tags: Tag[]
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
  priority?: TaskPriority
  category_id?: string | null
  tag_ids?: string[]
}

export interface TaskUpdatePayload {
  title?: string
  description?: string | null
  planned_date?: string | null
  priority?: TaskPriority
  category_id?: string | null
  tag_ids?: string[]
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}
