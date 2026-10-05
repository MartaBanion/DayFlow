import { updateTaskWithConflict, type ConfirmScheduleConflict } from './taskSave'
import type { Task, TaskUpdatePayload } from './types'

export type QuickRescheduleAction =
  | 'today'
  | 'tomorrow'
  | 'next_monday'
  | 'inbox'
  | 'choose_date'

export type QuickRescheduleErrorCode =
  | 'task_not_pending'
  | 'task_deleted'
  | 'runtime_unavailable'
  | 'invalid_date'
  | 'selected_date_required'

export class QuickRescheduleError extends Error {
  constructor(
    public readonly code: QuickRescheduleErrorCode,
    message: string,
  ) {
    super(message)
    this.name = 'QuickRescheduleError'
  }
}

type CalendarDate = { year: number; month: number; day: number }

const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeapYear(year) ? 29 : 28
  return [4, 6, 9, 11].includes(month) ? 30 : 31
}

function parseCalendarDate(value: string): CalendarDate {
  const match = DATE_PATTERN.exec(value)
  if (!match) throw new QuickRescheduleError('invalid_date', `Invalid calendar date: ${value}`)

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
    throw new QuickRescheduleError('invalid_date', `Invalid calendar date: ${value}`)
  }
  return { year, month, day }
}

function formatCalendarDate({ year, month, day }: CalendarDate): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function isCalendarDate(value: string): boolean {
  try {
    parseCalendarDate(value)
    return true
  } catch (error) {
    if (error instanceof QuickRescheduleError && error.code === 'invalid_date') return false
    throw error
  }
}

export function addCalendarDays(value: string, amount: number): string {
  if (!Number.isInteger(amount)) {
    throw new QuickRescheduleError('invalid_date', 'Calendar day amount must be an integer')
  }

  const parsed = parseCalendarDate(value)
  let { year, month, day } = parsed
  let remaining = Math.abs(amount)
  const direction = amount < 0 ? -1 : 1

  while (remaining > 0) {
    day += direction
    if (direction > 0 && day > daysInMonth(year, month)) {
      day = 1
      month += 1
      if (month > 12) {
        month = 1
        year += 1
      }
    } else if (direction < 0 && day < 1) {
      month -= 1
      if (month < 1) {
        month = 12
        year -= 1
      }
      day = daysInMonth(year, month)
    }
    remaining -= 1
  }

  if (year < 1) throw new QuickRescheduleError('invalid_date', 'Calendar date is outside the supported range')
  return formatCalendarDate({ year, month, day })
}

function dayOfWeek({ year, month, day }: CalendarDate): number {
  const offsets = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
  const adjustedYear = month < 3 ? year - 1 : year
  return (
    adjustedYear
    + Math.floor(adjustedYear / 4)
    - Math.floor(adjustedYear / 100)
    + Math.floor(adjustedYear / 400)
    + offsets[month - 1]
    + day
  ) % 7
}

export function nextMonday(value: string): string {
  const parsed = parseCalendarDate(value)
  const weekday = dayOfWeek(parsed) // Sunday = 0, Monday = 1.
  const daysUntilNextMonday = ((8 - weekday) % 7) || 7
  return addCalendarDays(value, daysUntilNextMonday)
}

function requiredRuntimeDate(runtimeLocalDate: string | null | undefined): string {
  if (!runtimeLocalDate || !isCalendarDate(runtimeLocalDate)) {
    throw new QuickRescheduleError(
      'runtime_unavailable',
      'DayFlow runtime local date is unavailable',
    )
  }
  return runtimeLocalDate
}

function ensurePendingTask(task: Task): void {
  if (task.deleted_at_utc) {
    throw new QuickRescheduleError('task_deleted', 'Deleted tasks cannot be rescheduled')
  }
  if (task.status !== 'pending') {
    throw new QuickRescheduleError('task_not_pending', 'Only pending tasks can be rescheduled')
  }
}

export function buildQuickReschedulePayload(
  task: Task,
  runtimeLocalDate: string | null | undefined,
  action: QuickRescheduleAction,
  selectedDate?: string | null,
): TaskUpdatePayload {
  ensurePendingTask(task)

  if (action === 'inbox') return { planned_date: null, schedule: null }

  if (action === 'choose_date') {
    if (!selectedDate || !isCalendarDate(selectedDate)) {
      throw new QuickRescheduleError(
        'selected_date_required',
        'A valid selected date is required',
      )
    }
    return { planned_date: selectedDate }
  }

  const localDate = requiredRuntimeDate(runtimeLocalDate)
  if (action === 'today') return { planned_date: localDate }
  if (action === 'tomorrow') return { planned_date: addCalendarDays(localDate, 1) }
  return { planned_date: nextMonday(localDate) }
}

export interface QuickRescheduleRequest {
  task: Task
  runtimeLocalDate: string | null | undefined
  action: QuickRescheduleAction
  selectedDate?: string | null
  confirmScheduleConflict: ConfirmScheduleConflict
}

export async function quickRescheduleTask({
  task,
  runtimeLocalDate,
  action,
  selectedDate,
  confirmScheduleConflict,
}: QuickRescheduleRequest): Promise<Task | null> {
  const payload = buildQuickReschedulePayload(task, runtimeLocalDate, action, selectedDate)
  return updateTaskWithConflict(task, payload, confirmScheduleConflict)
}
