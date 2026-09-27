import { ApiRequestError, taskApi } from './api'
import type { Task, TaskCreatePayload, TaskUpdatePayload } from './types'

export type ConfirmScheduleConflict = () => Promise<boolean>

function isScheduleConflict(error: unknown): boolean {
  return error instanceof ApiRequestError && error.code === 'schedule_conflict'
}

export async function updateTaskWithConflict(
  task: Task,
  payload: TaskUpdatePayload,
  confirmConflict: ConfirmScheduleConflict,
): Promise<Task | null> {
  try {
    return await taskApi.update(task.id, task.version, payload)
  } catch (error) {
    if (!isScheduleConflict(error)) throw error
    if (!(await confirmConflict())) return null
    return taskApi.update(task.id, task.version, payload, { allowScheduleConflict: true })
  }
}

export async function createTaskWithConflict(
  payload: TaskCreatePayload,
  confirmConflict: ConfirmScheduleConflict,
): Promise<Task | null> {
  try {
    return await taskApi.create(payload)
  } catch (error) {
    if (!isScheduleConflict(error)) throw error
    if (!(await confirmConflict())) return null
    return taskApi.create(payload, { allowScheduleConflict: true })
  }
}
