// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { projectApi, taskApi } from '../api'
import type { Project, Task } from '../types'
import InboxView from './InboxView.vue'

const project: Project = {
  id: 'project-1',
  name: 'DayFlow 项目',
  description: null,
  status: 'active',
  created_at_utc: '2026-09-28T00:00:00.000000Z',
  updated_at_utc: '2026-09-28T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
  task_count: 0,
  completed_task_count: 0,
  progress_percent: 0,
}

const task: Task = {
  id: 'task-1',
  title: '整理任务',
  description: null,
  status: 'pending',
  planned_date: null,
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-28T00:00:00.000000Z',
  updated_at_utc: '2026-09-28T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
}

const stubs = {
  'el-alert': { props: ['title'], template: '<div><span>{{ title }}</span><slot /></div>' },
  'el-button': {
    props: ['nativeType', 'disabled', 'loading'],
    template: '<button :disabled="disabled" :type="nativeType || \'button\'"><slot /></button>',
  },
  'el-card': { template: '<div><slot /></div>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}<slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    template: '<input :value="modelValue" v-bind="$attrs" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  'el-select': {
    props: ['modelValue'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
  },
  'el-tag': { template: '<span><slot /></span>' },
  MetadataManager: { template: '<div />' },
  TaskCard: { props: ['task'], template: '<div>{{ task.title }}</div>' },
  TaskEditor: { template: '<div />' },
}

describe('Inbox project filter', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
    vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
    vi.spyOn(taskApi, 'list').mockResolvedValue([])
    vi.spyOn(projectApi, 'list').mockResolvedValue([project])
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  it('passes the selected project id to search requests', async () => {
    wrapper = mount(InboxView, {
      props: { searchOnly: true },
      global: { stubs },
    })
    await flushPromises()

    const projectSelect = wrapper.findAll('select')[3]
    await projectSelect.setValue(project.id)
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: false,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
      projectId: project.id,
    })
  })

  it('retains selected filters while collapsed and clears them explicitly', async () => {
    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('还没有可搜索的任务')
    await wrapper.findAll('select')[3].setValue(project.id)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无匹配任务')
    await wrapper.findAll('button').find(b => b.text() === '收起筛选')!.trigger('click')
    expect(wrapper.get('.filter-summary').text()).toContain(project.name)
    expect(wrapper.get('#task-filters').isVisible()).toBe(false)
    await wrapper.findAll('button').find(b => b.text() === '清除筛选')!.trigger('click')
    await flushPromises()
    expect(taskApi.list).toHaveBeenLastCalledWith({ inbox: false, query: undefined, priority: undefined, categoryId: undefined, tagId: undefined })
  })

  it('uses search-specific loading and error copy and keeps Retry accessible', async () => {
    vi.mocked(taskApi.list).mockRejectedValue(new Error('offline'))
    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    expect(wrapper.text()).toContain('正在搜索')
    expect(wrapper.text()).not.toContain('正在加载收件箱')
    await flushPromises()
    expect(wrapper.text()).toContain('搜索失败')
    expect(wrapper.text()).not.toContain('收件箱加载失败')
    expect(wrapper.findAll('button').some(b => b.text() === '重试')).toBe(true)
  })

  it('maps V0.8 search filters to the frozen task query enums', async () => {
    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    await flushPromises()

    await wrapper.findAll('select')[4].setValue('pending')
    await flushPromises()
    await wrapper.find('#overdue-filter').setValue(true)
    await flushPromises()
    await wrapper.findAll('select')[5].setValue('past')
    await flushPromises()
    await wrapper.findAll('select')[6].setValue('completed')
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: false,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
      status: 'pending',
      overdue: true,
      plannedBucket: 'past',
      sort: 'completed',
    })
  })

  it('resets search filters without changing the search mode', async () => {
    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    await flushPromises()
    await wrapper.find('input#overdue-filter').setValue(true)
    await flushPromises()
    await wrapper.findAll('select')[4].setValue('completed')
    await flushPromises()

    await wrapper.findAll('button').find(button => button.text() === '清除筛选')!.trigger('click')
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: false,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })
    expect(wrapper.text()).toContain('搜索结果')
  })

  it('keeps loaded search results when a refresh fails and offers retry', async () => {
    vi.mocked(taskApi.list).mockReset()
    let listCalls = 0
    vi.mocked(taskApi.list).mockImplementation(() => {
      listCalls += 1
      return listCalls === 1 ? Promise.resolve([task]) : Promise.reject(new Error('offline'))
    })

    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain(task.title)

    await wrapper.findAll('button').find(button => button.text() === '刷新')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(task.title)
    expect(wrapper.text()).toContain('当前结果可能未更新')
    expect(wrapper.findAll('button').some(button => button.text() === '重试')).toBe(true)
  })

  it('ignores an older response after filters change quickly', async () => {
    vi.mocked(taskApi.list).mockReset()
    const resolvers: Array<(value: Task[]) => void> = []
    vi.mocked(taskApi.list).mockImplementation(() => new Promise(resolve => resolvers.push(resolve)))

    wrapper = mount(InboxView, { props: { searchOnly: true }, global: { stubs } })
    await flushPromises()
    expect(resolvers).toHaveLength(1)
    resolvers[0]!([])
    await flushPromises()

    await wrapper.findAll('select')[4].setValue('pending')
    await wrapper.findAll('select')[5].setValue('past')
    expect(resolvers.length).toBeGreaterThan(1)

    const latestResolver = resolvers.at(-1)!
    latestResolver([task])
    for (const resolver of resolvers.slice(0, -1)) resolver([{ ...task, title: '旧响应' }])
    await flushPromises()

    expect(wrapper.text()).toContain(task.title)
    expect(wrapper.text()).not.toContain('旧响应')
  })
})

describe('Inbox query scope', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
    vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
    vi.spyOn(taskApi, 'list').mockResolvedValue([task])
    vi.spyOn(projectApi, 'list').mockResolvedValue([])
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  it('keeps inbox=true when an Inbox query is submitted', async () => {
    wrapper = mount(InboxView, { global: { stubs } })
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: true,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })

    await wrapper.find('#task-search').setValue('整理')
    await wrapper.find('form.search-form').trigger('submit')
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: true,
      query: '整理',
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })
    expect(wrapper.get('h2').text()).toBe('收件箱')
    expect(wrapper.get('.task-heading h3').text()).toBe('待安排任务')
    expect(wrapper.text()).not.toContain('搜索结果')
  })

  it('clears the Inbox query back to the ordinary Inbox request and copy', async () => {
    wrapper = mount(InboxView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('#task-search').setValue('整理')
    await wrapper.find('form.search-form').trigger('submit')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '清除筛选')!.trigger('click')
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      inbox: true,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })
    expect(wrapper.get('.task-heading h3').text()).toBe('待安排任务')
  })
})
