// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, projectApi, reviewApi, taskApi } from '../api'
import type { Project, ReviewResponse, Task } from '../types'
import ReviewView from './ReviewView.vue'

const timezone = 'Asia/Shanghai'
const task = (overrides: Partial<Task> = {}): Task => ({
  id: 'task-completed',
  title: '整理项目笔记',
  description: '保留的完成记录',
  status: 'completed',
  planned_date: '2026-10-03',
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'high',
  category: { id: 'category-1', name: '学习' },
  tags: [],
  project_id: 'project-1',
  project: { id: 'project-1', name: 'DayFlow', status: 'active' },
  created_at_utc: '2026-10-01T00:00:00.000000Z',
  updated_at_utc: '2026-10-03T08:00:00.000000Z',
  completed_at_utc: '2026-10-03T08:00:00.000000Z',
  deleted_at_utc: null,
  version: 1,
  ...overrides,
})

const project = (overrides: Partial<Project> = {}) => ({
  id: 'project-1',
  name: 'DayFlow',
  status: 'active' as const,
  task_count: 3,
  completed_task_count: 1,
  pending_task_count: 2,
  overdue_task_count: 1,
  progress_percent: 33,
  latest_completed_at_utc: '2026-10-03T08:00:00.000000Z',
  ...overrides,
})

const response = (overrides: Partial<ReviewResponse> = {}): ReviewResponse => ({
  scope: 'today',
  local_timezone: timezone,
  local_date: '2026-10-03',
  range_start_utc: '2026-10-02T16:00:00.000000Z',
  range_end_utc: '2026-10-03T16:00:00.000000Z',
  generated_at_utc: '2026-10-03T08:00:00.000000Z',
  completed: { count: 1, tasks: [task()] },
  overdue: { count: 1, tasks: [task({ id: 'task-overdue', title: '处理逾期任务', status: 'pending', deadline_date: '2026-10-01', deadline_timezone: timezone, deadline_status: 'overdue', completed_at_utc: null })] },
  carryover: { count: 1, tasks: [task({ id: 'task-overdue', title: '处理逾期任务', status: 'pending', planned_date: '2026-10-01', deadline_date: '2026-10-01', deadline_timezone: timezone, deadline_status: 'overdue', completed_at_utc: null })] },
  projects: [project()],
  ...overrides,
})

const stubs = {
  TaskEditor: {
    props: ['open', 'task'],
    template: '<div v-if="open" class="stub-editor"><button type="button" @click="$emit(\'submit\', { title: task.title, description: task.description, planned_date: task.planned_date, priority: task.priority, category_id: task.category?.id ?? null, tag_ids: [], project_id: task.project_id ?? null })">保存任务</button></div>',
  },
}

let wrapper: VueWrapper

beforeEach(() => {
  vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
  vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
  vi.spyOn(projectApi, 'list').mockResolvedValue([])
})

afterEach(() => {
  wrapper?.unmount()
  window.location.hash = ''
  vi.restoreAllMocks()
})

async function open(initial: ReviewResponse = response()): Promise<void> {
  vi.spyOn(reviewApi, 'get').mockResolvedValue(initial)
  wrapper = mount(ReviewView, { global: { stubs } })
  await flushPromises()
}

describe('ReviewView', () => {
  it('loads Today by default and shows the frozen sections from the API', async () => {
    await open()

    expect(reviewApi.get).toHaveBeenCalledWith('today')
    expect(wrapper.get('button[aria-pressed="true"]').text()).toBe('今天')
    expect(wrapper.text()).toContain('日常回顾')
    expect(wrapper.text()).toContain('今天完成了 1 项任务')
    expect(wrapper.text()).toContain('整理项目笔记')
    expect(wrapper.text()).toContain('逾期任务')
    expect(wrapper.text()).toContain('遗留任务')
    expect(wrapper.text()).toContain('处理逾期任务')
    expect(wrapper.text()).toContain('DayFlow')
    expect(wrapper.text()).toContain('3 个任务')
    expect(wrapper.text()).toContain('最近保留完成')
  })

  it('switches to This Week without recalculating response semantics', async () => {
    const week = response({
      scope: 'week',
      completed: { count: 2, tasks: [task(), task({ id: 'task-week', title: '本周另一项任务' })] },
    })
    vi.spyOn(reviewApi, 'get').mockResolvedValueOnce(response()).mockResolvedValueOnce(week)
    wrapper = mount(ReviewView, { global: { stubs } })
    await flushPromises()

    await wrapper.get('[role="group"][aria-label="选择回顾范围"] button:nth-child(2)').trigger('click')
    await flushPromises()

    expect(reviewApi.get).toHaveBeenNthCalledWith(2, 'week')
    expect(wrapper.get('button[aria-pressed="true"]').text()).toBe('本周')
    expect(wrapper.text()).toContain('本周完成了 2 项任务')
    expect(wrapper.text()).toContain('本周另一项任务')
  })

  it('shows the correct completed empty copy for Today and This Week', async () => {
    const emptyToday = response({ completed: { count: 0, tasks: [] } })
    const emptyWeek = response({ scope: 'week', completed: { count: 0, tasks: [] } })
    vi.spyOn(reviewApi, 'get').mockResolvedValueOnce(emptyToday).mockResolvedValueOnce(emptyWeek)
    wrapper = mount(ReviewView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('今天还没有完成的任务')

    await wrapper.get('[role="group"][aria-label="选择回顾范围"] button:nth-child(2)').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('本周还没有保留的完成记录')
  })

  it('renders a loading state before the first response', async () => {
    vi.spyOn(reviewApi, 'get').mockReturnValue(new Promise(() => {}))
    wrapper = mount(ReviewView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('正在加载回顾…')
    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('暂无项目')
  })

  it('shows a retryable error and clears it after success', async () => {
    const get = vi.spyOn(reviewApi, 'get')
      .mockRejectedValueOnce(new ApiRequestError('offline', 503))
      .mockResolvedValueOnce(response())
    wrapper = mount(ReviewView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('回顾加载失败')
    await wrapper.get('.review-state button').trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('整理项目笔记')
  })

  it('keeps existing review data when a refresh fails', async () => {
    vi.spyOn(reviewApi, 'get')
      .mockResolvedValueOnce(response())
      .mockRejectedValueOnce(new Error('offline'))
    await open()

    await wrapper.get('button[aria-label="刷新回顾"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('整理项目笔记')
    expect(wrapper.text()).toContain('当前显示的内容可能未更新')
    expect(wrapper.find('.review-summary-card').exists()).toBe(true)
  })

  it('opens the existing Task Editor and refreshes after save', async () => {
    const updated = task({ title: '整理项目笔记（已更新）', version: 2 })
    vi.spyOn(reviewApi, 'get').mockResolvedValueOnce(response()).mockResolvedValueOnce(response({ completed: { count: 1, tasks: [updated] } }))
    const update = vi.spyOn(taskApi, 'update').mockResolvedValue(updated)
    await open()

    await wrapper.get('button[aria-label="打开任务：整理项目笔记"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('.stub-editor').exists()).toBe(true)

    await wrapper.get('.stub-editor button').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(task().id, 1, expect.objectContaining({ title: task().title }))
    expect(reviewApi.get).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('整理项目笔记（已更新）')
  })

  it('opens the existing Project Detail Hash without adding project actions', async () => {
    await open()
    await wrapper.get('button[aria-label="打开项目：DayFlow"]').trigger('click')

    expect(window.location.hash).toBe('#project:project-1')
    expect(wrapper.find('button[aria-label="完成项目"]').exists()).toBe(false)
  })

  it('shows zero-task projects as a stable zero progress value', async () => {
    await open(response({ projects: [project({ task_count: 0, completed_task_count: 0, pending_task_count: 0, overdue_task_count: 0, progress_percent: 0, latest_completed_at_utc: null })] }))

    expect(wrapper.text()).toContain('0%')
    expect(wrapper.get('progress').attributes('value')).toBe('0')
  })
})
