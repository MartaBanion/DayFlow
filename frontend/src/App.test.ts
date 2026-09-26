// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import App from './App.vue'
import { ApiRequestError, taskApi } from './api'
import type { Task } from './types'

const today = '2026-09-26'

const makeTask = (overrides: Partial<Task> = {}): Task => ({
  id: 'task-1',
  title: 'Prepare Linux notes',
  description: null,
  status: 'pending',
  planned_date: today,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
  ...overrides,
})

let wrapper: VueWrapper | undefined

beforeEach(() => {
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' })
})

afterEach(() => {
  ElMessage.closeAll()
  wrapper?.unmount()
  window.location.hash = ''
  vi.restoreAllMocks()
})

async function deleteTaskFromToday(): Promise<HTMLButtonElement> {
  const deleteButton = wrapper
    ?.findAll('.task-actions button')
    .find((button) => button.text() === 'Delete')
  expect(deleteButton).toBeDefined()

  await deleteButton!.trigger('click')
  await flushPromises()

  const undoButton = document.querySelector<HTMLButtonElement>('.delete-undo')
  expect(undoButton).not.toBeNull()
  return undoButton!
}

describe('delete undo flow', () => {
  it('restores a soft-deleted task from the success message', async () => {
    const task = makeTask()
    const restoredTask = makeTask({ version: 3 })
    vi.spyOn(taskApi, 'listToday')
      .mockResolvedValueOnce([task])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([restoredTask])
    const remove = vi.spyOn(taskApi, 'remove').mockResolvedValue(undefined)
    const restore = vi.spyOn(taskApi, 'restore').mockResolvedValue(restoredTask)

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const undoButton = await deleteTaskFromToday()
    expect(remove).toHaveBeenCalledWith(task.id, 1)

    undoButton.click()
    await flushPromises()

    expect(restore).toHaveBeenCalledWith(task.id, 2)
    expect(taskApi.listToday).toHaveBeenCalledTimes(3)
    expect(wrapper.text()).toContain(task.title)
  })

  it('shows a clear error when undo restore fails', async () => {
    const task = makeTask()
    vi.spyOn(taskApi, 'listToday').mockResolvedValueOnce([task]).mockResolvedValueOnce([])
    vi.spyOn(taskApi, 'remove').mockResolvedValue(undefined)
    const restore = vi
      .spyOn(taskApi, 'restore')
      .mockRejectedValue(new ApiRequestError('Task version conflict', 409))

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    const undoButton = await deleteTaskFromToday()
    undoButton.click()
    await flushPromises()

    expect(restore).toHaveBeenCalledWith(task.id, 2)
    expect(wrapper.find('.page-alert').text()).toContain(
      'This task changed elsewhere. Refresh the Today list and try again.',
    )
  })
})

describe('Today load state', () => {
  it('shows a loading state instead of empty task content while loading', async () => {
    vi.spyOn(taskApi, 'listToday').mockReturnValue(new Promise<Task[]>(() => {}))

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await nextTick()

    expect(wrapper.find('.today-state.is-loading').exists()).toBe(true)
    expect(wrapper.text()).toContain('Loading today’s tasks…')
    expect(wrapper.find('.summary-grid').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Nothing planned for this day')
  })

  it('shows an error state with Retry and loads normal content after retry', async () => {
    const task = makeTask()
    const listToday = vi
      .spyOn(taskApi, 'listToday')
      .mockRejectedValueOnce(new ApiRequestError('Request failed with status 502', 502))
      .mockResolvedValueOnce([task])

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.find('.today-state.is-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Request failed with status 502')
    expect(wrapper.find('.summary-grid').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Nothing planned for this day')

    await wrapper.get('.today-state.is-error button').trigger('click')
    await flushPromises()

    expect(listToday).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.today-state.is-error').exists()).toBe(false)
    expect(wrapper.find('.summary-grid').exists()).toBe(true)
    expect(wrapper.text()).toContain(task.title)
  })
})

describe('Inbox and search', () => {
  it('loads Inbox and captures an undated task', async () => {
    const task = makeTask({ id: 'inbox-1', title: 'Capture Linux idea', planned_date: null })
    vi.spyOn(taskApi, 'listToday').mockResolvedValue([])
    const list = vi.spyOn(taskApi, 'list').mockResolvedValue([task])
    vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
    vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
    const create = vi.spyOn(taskApi, 'create').mockResolvedValue(task)

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await wrapper.get('a[href="#inbox"]').trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalledWith({
      inbox: true,
      query: undefined,
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })
    expect(wrapper.text()).toContain('Capture Linux idea')

    await wrapper.get('input[aria-label="New Inbox task title"]').setValue('New Inbox item')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(create).toHaveBeenCalledWith({
      title: 'New Inbox item',
      description: null,
      planned_date: null,
    })
  })

  it('shows search error state without pretending the result is empty', async () => {
    vi.spyOn(taskApi, 'listToday').mockResolvedValue([])
    vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
    vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
    const list = vi
      .spyOn(taskApi, 'list')
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new ApiRequestError('Search service unavailable', 503))
      .mockResolvedValueOnce([])

    wrapper = mount(App, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await wrapper.get('a[href="#inbox"]').trigger('click')
    await flushPromises()

    await wrapper.get('input[aria-label="Search tasks"]').setValue('linux')
    await wrapper.get('form.search-form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.today-state.is-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Search service unavailable')
    expect(wrapper.text()).not.toContain('No tasks match your search')
    expect(list).toHaveBeenLastCalledWith({
      inbox: false,
      query: 'linux',
      priority: undefined,
      categoryId: undefined,
      tagId: undefined,
    })

    await wrapper.get('.today-state.is-error button').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(3)
  })
})
