import { describe, expect, it } from 'vitest'

import { calculateCompletionRate, toDateInputValue } from './date'
import type { Task } from './types'

const task = (status: Task['status']): Task => ({
  id: status,
  title: status,
  description: null,
  status,
  planned_date: '2026-09-26',
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
})

describe('date helpers', () => {
  it('formats a local date for date inputs', () => {
    expect(toDateInputValue(new Date(2026, 8, 26))).toBe('2026-09-26')
  })

  it('calculates completion rate without division by zero', () => {
    expect(calculateCompletionRate([])).toBe(0)
    expect(calculateCompletionRate([task('pending'), task('completed')])).toBe(50)
    expect(calculateCompletionRate([task('completed')])).toBe(100)
  })
})
