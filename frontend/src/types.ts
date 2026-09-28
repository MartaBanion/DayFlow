export type TaskStatus = 'pending' | 'completed'
export type TaskPriority = 'low' | 'normal' | 'high'
export type ProjectStatus = 'active' | 'completed'

export interface Category {
  id: string
  name: string
}

export interface Tag {
  id: string
  name: string
}

export interface ProjectSummary {
  id: string
  name: string
  status: ProjectStatus
}

export interface Project {
  id: string
  name: string
  description: string | null
  status: ProjectStatus
  created_at_utc: string
  updated_at_utc: string
  completed_at_utc: string | null
  deleted_at_utc: string | null
  version: number
  task_count: number
  completed_task_count: number
  progress_percent: number
}

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  planned_date: string | null
  start_at_utc: string | null
  end_at_utc: string | null
  schedule_timezone: string | null
  priority: TaskPriority
  category: Category | null
  tags: Tag[]
  project_id?: string | null
  project?: ProjectSummary | null
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
  project_id?: string | null
  schedule?: TaskSchedulePayload | null
}

export interface TaskUpdatePayload {
  title?: string
  description?: string | null
  planned_date?: string | null
  priority?: TaskPriority
  category_id?: string | null
  tag_ids?: string[]
  project_id?: string | null
  schedule?: TaskSchedulePayload | null
}

export interface ProjectCreatePayload {
  name: string
  description: string | null
}

export interface ProjectUpdatePayload {
  name?: string
  description?: string | null
}

export interface TaskSchedulePayload {
  start_time: string
  end_time: string
  timezone?: string
}

export interface RuntimeInfo {
  timezone: string
  local_date: string
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}
