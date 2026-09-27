import { describe, expect, it } from 'vitest'

import {
  addDays,
  calendarRange,
  listDays,
  shiftAnchor,
  startOfWeek,
  taskLocalClockMinutes,
  taskTimeLabel,
} from './calendar'
import type { Task } from './types'

const task: Task = {
  id: 'scheduled-task',
  title: '学习 Linux',
  description: null,
  status: 'pending',
  planned_date: '2026-09-26',
  start_at_utc: '2026-09-26T06:00:00.000Z',
  end_at_utc: '2026-09-26T07:30:00.000Z',
  schedule_timezone: 'Asia/Shanghai',
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-26T00:00:00.000Z',
  updated_at_utc: '2026-09-26T00:00:00.000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
}

describe('calendar date ranges', () => {
  it('uses local date strings without UTC date parsing', () => {
    expect(addDays('2026-09-30', 1)).toBe('2026-10-01')
    expect(startOfWeek('2026-09-26')).toBe('2026-09-21')
    expect(listDays('2026-09-26', '2026-09-28')).toEqual([
      '2026-09-26',
      '2026-09-27',
      '2026-09-28',
    ])
  })

  it('calculates day, week, and bounded month ranges', () => {
    expect(calendarRange('day', '2026-09-26')).toMatchObject({
      start: '2026-09-26',
      end: '2026-09-26',
      days: ['2026-09-26'],
    })
    expect(calendarRange('week', '2026-09-26')).toMatchObject({
      start: '2026-09-21',
      end: '2026-09-27',
    })
    const month = calendarRange('month', '2026-09-26')
    expect(month.start).toBe('2026-08-31')
    expect(month.end).toBe('2026-10-04')
    expect(month.days.length).toBeLessThanOrEqual(62)
  })

  it('moves day, week, and month anchors', () => {
    expect(shiftAnchor('day', '2026-09-26', 1)).toBe('2026-09-27')
    expect(shiftAnchor('week', '2026-09-26', -1)).toBe('2026-09-19')
    expect(shiftAnchor('month', '2026-09-26', 1)).toBe('2026-10-01')
  })
})

describe('calendar task time helpers', () => {
  it('formats a persisted UTC time in the task timezone', () => {
    expect(taskLocalClockMinutes(task.start_at_utc, task.schedule_timezone)).toBe(14 * 60)
    expect(taskTimeLabel(task)).toBe('14:00–15:30')
  })
})
