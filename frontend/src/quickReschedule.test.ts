import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, taskApi } from './api'
import {
  addCalendarDays,
  buildQuickReschedulePayload,
  nextMonday,
  quickRescheduleTask,
  QuickRescheduleError,
} from './quickReschedule'
import type { Task } from './types'

const task: Task = {
  id: 'task-1',
  title: '计划任务',
  description: null,
  status: 'pending',
  planned_date: '2026-10-05',
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-10-05T00:00:00.000Z',
  updated_at_utc: '2026-10-05T00:00:00.000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 4,
}

afterEach(() => vi.restoreAllMocks())

describe('quick reschedule date helper', () => {
  it.each([
    ['2026-10-05', '2026-10-06'],
    ['2026-10-31', '2026-11-01'],
    ['2026-12-31', '2027-01-01'],
    ['2028-02-28', '2028-02-29'],
    ['2028-02-29', '2028-03-01'],
  ])('adds one calendar day: %s -> %s', (value, expected) => {
    expect(addCalendarDays(value, 1)).toBe(expected)
  })

  it.each([
    ['2026-10-05', '2026-10-12'],
    ['2026-10-06', '2026-10-12'],
    ['2026-10-11', '2026-10-12'],
  ])('finds the next Monday: %s -> %s', (value, expected) => {
    expect(nextMonday(value)).toBe(expected)
  })

  it('does not depend on browser Date or timezone behavior', () => {
    expect(addCalendarDays('2028-02-29', 1)).toBe('2028-03-01')
    expect(nextMonday('2026-10-11')).toBe('2026-10-12')
  })
})

describe('quick reschedule payloads', () => {
  it('maps runtime-based actions to planned_date only', () => {
    expect(buildQuickReschedulePayload(task, '2026-10-05', 'today')).toEqual({
      planned_date: '2026-10-05',
    })
    expect(buildQuickReschedulePayload(task, '2026-10-05', 'tomorrow')).toEqual({
      planned_date: '2026-10-06',
    })
    expect(buildQuickReschedulePayload(task, '2026-10-06', 'next_monday')).toEqual({
      planned_date: '2026-10-12',
    })
    expect(buildQuickReschedulePayload(task, null, 'choose_date', '2027-01-01')).toEqual({
      planned_date: '2027-01-01',
    })
  })

  it('clears the schedule atomically when moving to Inbox', () => {
    expect(buildQuickReschedulePayload(task, null, 'inbox')).toEqual({
      planned_date: null,
      schedule: null,
    })
  })

  it('fails closed when runtime or selected date is unavailable', () => {
    expect(() => buildQuickReschedulePayload(task, null, 'today')).toThrowError(
      expect.objectContaining<QuickRescheduleError>({ code: 'runtime_unavailable' }),
    )
    expect(() => buildQuickReschedulePayload(task, '2026-10-05', 'choose_date')).toThrowError(
      expect.objectContaining<QuickRescheduleError>({ code: 'selected_date_required' }),
    )
  })

  it('rejects completed and deleted tasks before calling the API', () => {
    const update = vi.spyOn(taskApi, 'update')
    expect(() => buildQuickReschedulePayload({ ...task, status: 'completed' }, '2026-10-05', 'today'))
      .toThrowError(expect.objectContaining<QuickRescheduleError>({ code: 'task_not_pending' }))
    expect(() => buildQuickReschedulePayload({ ...task, deleted_at_utc: '2026-10-05T01:00:00Z' }, '2026-10-05', 'today'))
      .toThrowError(expect.objectContaining<QuickRescheduleError>({ code: 'task_deleted' }))
    expect(update).not.toHaveBeenCalled()
  })
})

describe('quick reschedule update flow', () => {
  it('uses the task version and the existing update helper path', async () => {
    const saved = { ...task, planned_date: '2026-10-06', version: 5 }
    const update = vi.spyOn(taskApi, 'update').mockResolvedValue(saved)

    const result = await quickRescheduleTask({
      task,
      runtimeLocalDate: '2026-10-05',
      action: 'tomorrow',
      confirmScheduleConflict: async () => true,
    })

    expect(result).toEqual(saved)
    expect(update).toHaveBeenCalledWith(task.id, task.version, { planned_date: '2026-10-06' })
  })

  it('reuses the existing schedule conflict confirmation flow', async () => {
    const saved = { ...task, planned_date: '2026-10-06', version: 5 }
    const update = vi
      .spyOn(taskApi, 'update')
      .mockRejectedValueOnce(new ApiRequestError('overlap', 409, 'schedule_conflict'))
      .mockResolvedValueOnce(saved)
    const confirm = vi.fn().mockResolvedValue(true)

    const result = await quickRescheduleTask({
      task,
      runtimeLocalDate: '2026-10-05',
      action: 'tomorrow',
      confirmScheduleConflict: confirm,
    })

    expect(result).toEqual(saved)
    expect(confirm).toHaveBeenCalledOnce()
    expect(update).toHaveBeenNthCalledWith(2, task.id, task.version, { planned_date: '2026-10-06' }, {
      allowScheduleConflict: true,
    })
  })
})
