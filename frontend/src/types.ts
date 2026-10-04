export type TaskStatus = 'pending' | 'completed'
export type TaskPriority = 'low' | 'normal' | 'high'
export type ProjectStatus = 'active' | 'completed'
export type DeadlineStatus = 'none' | 'upcoming' | 'due_today' | 'overdue' | 'completed'
export type RecurrenceFrequency = 'daily' | 'weekly' | 'monthly'
export type ReminderStatus = 'pending' | 'acknowledged' | 'dismissed'
export type ReviewScope = 'today' | 'week'

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
  deadline_date?: string | null
  deadline_at_utc?: string | null
  deadline_timezone?: string | null
  deadline_status?: DeadlineStatus
  category: Category | null
  tags: Tag[]
  project_id?: string | null
  project?: ProjectSummary | null
  created_at_utc: string
  updated_at_utc: string
  completed_at_utc: string | null
  deleted_at_utc: string | null
  version: number
  recurrence_rule_id?: string | null
  recurrence_occurrence_date?: string | null
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
  deadline?: TaskDeadlinePayload | null
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
  deadline?: TaskDeadlinePayload | null
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

export interface TaskDeadlinePayload {
  date: string
  time?: string
  timezone?: string
}

export interface RecurrenceRule {
  id: string
  frequency: RecurrenceFrequency
  weekdays: number[] | null
  month_day: number | null
  starts_on: string
  timezone: string
  stopped_at_utc: string | null
  created_at_utc: string
  updated_at_utc: string
  version: number
}

export interface RecurrenceCreatePayload {
  version: number
  frequency: RecurrenceFrequency
  starts_on: string
  timezone?: string
  weekdays?: number[] | null
  month_day?: number | null
}

export interface RecurrenceUpdatePayload {
  frequency?: RecurrenceFrequency
  starts_on?: string
  timezone?: string
  weekdays?: number[] | null
  month_day?: number | null
}

export interface Reminder {
  id: string
  task_id: string
  trigger_at_utc: string
  reminder_timezone: string
  status: ReminderStatus
  acknowledged_at_utc: string | null
  dismissed_at_utc: string | null
  created_at_utc: string
  updated_at_utc: string
  version: number
}

export interface ReminderPayload {
  date: string
  time: string
  timezone?: string
}

export interface RuntimeInfo {
  timezone: string
  local_date: string
  app_version?: string
  database_schema?: string | null
}

export interface ReviewTaskSection {
  count: number
  tasks: Task[]
}

export interface ReviewProject {
  id: string
  name: string
  status: ProjectStatus
  task_count: number
  completed_task_count: number
  pending_task_count: number
  overdue_task_count: number
  progress_percent: number
  latest_completed_at_utc: string | null
}

export interface ReviewResponse {
  scope: ReviewScope
  local_timezone: string
  local_date: string
  range_start_utc: string
  range_end_utc: string
  generated_at_utc: string
  completed: ReviewTaskSection
  overdue: ReviewTaskSection
  carryover: ReviewTaskSection
  projects: ReviewProject[]
}

export interface Backup {
  backup_version: 1
  backup_id: string
  filename: string
  created_at_utc: string
  app_version: string
  alembic_version: string
  database_sha256: string
  file_size: number
  integrity_check: 'ok'
  foreign_key_errors: 0
  verified_at_utc: string
  source_database: string
  compatible_for_restore: boolean
}

export interface BackupVerification {
  backup_id: string
  verified_at_utc: string
  status: 'valid' | 'incompatible' | 'corrupted' | 'unreadable' | 'manifest_mismatch'
  compatible_for_restore: boolean
  database_sha256: string | null
  file_size: number | null
  alembic_version: string | null
  integrity_check: string | null
  foreign_key_errors: number | null
  structure_valid: boolean
  issues: string[]
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}
