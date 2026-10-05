// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { taskApi } from '../api'
import type { Task } from '../types'
import CalendarMonthView from './CalendarMonthView.vue'
import CalendarView from './CalendarView.vue'
import TodayView from './TodayView.vue'

const today = '2026-10-05'

const task = (overrides: Partial<Task> = {}): Task => ({
  id: 'planning-task',
  title: '规划任务',
  description: null,
  status: 'pending',
  planned_date: today,
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-10-05T00:00:00.000000Z',
  updated_at_utc: '2026-10-05T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
  ...overrides,
})

const todayStubs = {
  MetadataManager: { template: '<div />' },
  TaskEditor: { template: '<div />' },
  TaskCard: {
    props: ['task'],
    emits: ['rescheduled'],
    template: '<article class="task-card-stub"><h4>{{ task.title }}</h4><button type="button" @click="$emit(\'rescheduled\', task)">调整日期</button></article>',
  },
}

const calendarStubs = {
  TaskEditor: { template: '<div />' },
}

afterEach(() => vi.restoreAllMocks())

describe('Today integration', () => {
  it('refreshes after a Quick Reschedule and ignores an older response', async () => {
    const first = task({ title: '旧结果' })
    const latest = task({ title: '最新结果' })
    const resolvers: Array<(value: Task[]) => void> = []
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: today })
    vi.spyOn(taskApi, 'listToday').mockImplementation(() => new Promise(resolve => resolvers.push(resolve)))

    const wrapper = mount(TodayView, { global: { plugins: [ElementPlus], stubs: todayStubs } })
    await flushPromises()
    expect(resolvers).toHaveLength(1)
    resolvers[0]!([first])
    await flushPromises()

    const refresh = wrapper.findAll('button').find(button => button.text() === '刷新')!
    await refresh.trigger('click')
    expect(resolvers).toHaveLength(2)
    resolvers[1]!([latest])
    resolvers[0]!([first])
    await flushPromises()

    expect(wrapper.text()).toContain('最新结果')
    expect(wrapper.text()).not.toContain('旧结果')
  })

  it('refreshes Today after the shared TaskCard emits rescheduled', async () => {
    const current = task()
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: today })
    const listToday = vi.spyOn(taskApi, 'listToday').mockResolvedValueOnce([current]).mockResolvedValueOnce([])

    const wrapper = mount(TodayView, { global: { plugins: [ElementPlus], stubs: todayStubs } })
    await flushPromises()
    await wrapper.get('.task-card-stub button').trigger('click')
    await flushPromises()

    expect(listToday).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.task-card-stub').exists()).toBe(false)
  })
})

describe('Calendar integration', () => {
  it('keeps the newest range response after fast navigation', async () => {
    const first = task({ title: '旧日历结果' })
    const latest = task({ title: '最新日历结果', planned_date: '2026-10-12' })
    const resolvers: Array<(value: Task[]) => void> = []
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: today })
    vi.spyOn(taskApi, 'listCalendar').mockImplementation(() => new Promise(resolve => resolvers.push(resolve)))

    const wrapper = mount(CalendarView, { global: { plugins: [ElementPlus], stubs: calendarStubs } })
    await flushPromises()
    expect(resolvers).toHaveLength(1)

    await wrapper.find('button[aria-label="下一个时间段"]').trigger('click')
    expect(resolvers).toHaveLength(2)
    resolvers[1]!([latest])
    resolvers[0]!([first])
    await flushPromises()

    expect(wrapper.text()).toContain('最新日历结果')
    expect(wrapper.text()).not.toContain('旧日历结果')
  })

  it('switches a Month date into the existing Day View', async () => {
    const calendarTask = task({ title: '月视图任务' })
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: today })
    const listCalendar = vi.spyOn(taskApi, 'listCalendar').mockResolvedValue([calendarTask])

    const wrapper = mount(CalendarView, { global: { plugins: [ElementPlus], stubs: calendarStubs } })
    await flushPromises()
    await wrapper.get('button[aria-pressed="false"]:nth-of-type(3)').trigger('click')
    await flushPromises()

    const dateButton = wrapper.get('button[aria-label="查看 2026-10-05 的日视图"]')
    await dateButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('.calendar-day-view').exists()).toBe(true)
    expect(listCalendar).toHaveBeenLastCalledWith('2026-10-05', '2026-10-05')
  })
})

describe('Month drill-down controls', () => {
  it('supports date, more-items, and keyboard activation without changing task click', async () => {
    const tasks = [
      task({ id: 'one', title: '任务一' }),
      task({ id: 'two', title: '任务二' }),
      task({ id: 'three', title: '任务三' }),
      task({ id: 'four', title: '任务四' }),
    ]
    const wrapper = mount(CalendarMonthView, {
      props: { days: [today], month: '2026-10', tasks },
    })

    await wrapper.get('button.calendar-month-day-trigger').trigger('keydown.enter')
    expect(wrapper.emitted('selectDate')?.[0]).toEqual([today])
    await wrapper.get('.calendar-more').trigger('click')
    expect(wrapper.emitted('selectDate')).toHaveLength(2)
    await wrapper.find('.calendar-month-task').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual([tasks[0]])
  })
})
