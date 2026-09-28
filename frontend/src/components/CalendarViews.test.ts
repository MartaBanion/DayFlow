// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { taskApi } from '../api'
import type { Task } from '../types'
import CalendarDayView from './CalendarDayView.vue'
import CalendarMonthView from './CalendarMonthView.vue'
import CalendarView from './CalendarView.vue'
import CalendarWeekView from './CalendarWeekView.vue'

const task = (overrides: Partial<Task> = {}): Task => ({
  id: 'calendar-task',
  title: '日历任务',
  description: null,
  status: 'pending',
  planned_date: '2026-09-26',
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-26T00:00:00.000Z',
  updated_at_utc: '2026-09-26T00:00:00.000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
  ...overrides,
})

afterEach(() => vi.restoreAllMocks())

describe('calendar views', () => {
  it('renders date-only tasks in the Day View 未安排时间 section', () => {
    const wrapper = mount(CalendarDayView, {
      props: { date: '2026-09-26', tasks: [task()] },
    })

    expect(wrapper.text()).toContain('未安排时间')
    expect(wrapper.text()).toContain('日历任务')
  })

  it('renders timed tasks in Week and Month views', () => {
    const scheduled = task({
      title: '有时间的任务',
      start_at_utc: '2026-09-26T06:00:00.000Z',
      end_at_utc: '2026-09-26T07:00:00.000Z',
      schedule_timezone: 'Asia/Shanghai',
    })
    const week = mount(CalendarWeekView, {
      props: {
        days: [
          '2026-09-21',
          '2026-09-22',
          '2026-09-23',
          '2026-09-24',
          '2026-09-25',
          '2026-09-26',
          '2026-09-27',
        ],
        today: '2026-09-26',
        tasks: [scheduled],
      },
    })
    const month = mount(CalendarMonthView, {
      props: { days: ['2026-09-26'], month: '2026-09', tasks: [scheduled] },
    })

    expect(week.text()).toContain('有时间的任务')
    expect(week.text()).toContain('14:00–15:00')
    expect(week.findAll('.calendar-week-day')).toHaveLength(7)
    expect(week.find('.calendar-week-untimed').exists()).toBe(true)
    expect(week.find('.calendar-week-timeline').exists()).toBe(true)
    expect(week.findAll('.calendar-week-column')).toHaveLength(7)
    expect(month.text()).toContain('有时间的任务')
  })
})

describe('CalendarView runtime and states', () => {
  it('uses the Backend runtime date for the initial calendar range', async () => {
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({
      timezone: 'Asia/Shanghai',
      local_date: '2026-09-26',
    })
    const listCalendar = vi.spyOn(taskApi, 'listCalendar').mockResolvedValue([task()])

    const wrapper = mount(CalendarView, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(listCalendar).toHaveBeenCalledWith('2026-09-21', '2026-09-27')
    expect(wrapper.text()).toContain('日历任务')
  })

  it('keeps API failures as an error state instead of an empty calendar', async () => {
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({
      timezone: 'Asia/Shanghai',
      local_date: '2026-09-26',
    })
    vi.spyOn(taskApi, 'listCalendar').mockRejectedValue(new Error('network'))

    const wrapper = mount(CalendarView, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.find('.calendar-state.is-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('日历加载失败')
    expect(wrapper.text()).not.toContain('这个时间范围还没有任务')
  })
})
