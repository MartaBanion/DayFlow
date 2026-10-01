// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TaskEditor from './TaskEditor.vue'
import { recurrenceApi, reminderApi, taskApi } from '../api'
import type { Task } from '../types'

const stubs = {
  'el-button': {
    props: ['nativeType'],
    inheritAttrs: false,
    template: '<button :class="$attrs.class" :type="nativeType || \'button\'" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-date-picker': {
    props: ['modelValue'],
    template: '<input type="date" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-dialog': {
    props: ['modelValue'],
    template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
  },
  'el-form': {
    template: '<form @submit.prevent="$emit(\'submit\')"><slot /></form>',
  },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'type'],
    template: '<textarea v-if="type === \'textarea\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><input v-else :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  'el-select': {
    props: ['modelValue'],
    template: '<select :multiple="Array.isArray(modelValue)" :value="modelValue" @change="$emit(\'update:modelValue\', Array.isArray(modelValue) ? Array.from($event.target.selectedOptions).map((option) => option.value) : ($event.target.value || undefined))"><slot /></select>',
  },
}

const task: Task = {
  id: 'task-1',
  title: 'Review Linux notes',
  description: 'A note',
  status: 'pending',
  planned_date: null,
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: { id: 'category-1', name: 'Learning' },
  tags: [{ id: 'tag-1', name: 'linux' }],
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 4,
}

const categories = [
  { id: 'category-1', name: 'Learning' },
  { id: 'category-2', name: 'Work' },
]
const tags = [
  { id: 'tag-1', name: 'linux' },
  { id: 'tag-2', name: 'lab' },
]
const projects = [
  { id: 'project-1', name: 'DayFlow', status: 'active' as const },
]

describe('TaskEditor organization fields', () => {
  it('summarizes existing values without requests and reveals invalid collapsed sections', async () => {
    const wrapper = mount(TaskEditor, { props: { open: true, task, categories, tags }, global: { stubs } })
    expect(wrapper.get('details[data-group="基础信息"] summary').text()).toContain(task.title)
    const section = wrapper.get('details[data-group="基础信息"]')
    section.element.removeAttribute('open')
    await wrapper.get('input').setValue('')
    await wrapper.findAll('button').find(b => b.text() === '保存任务')!.trigger('click')
    await flushPromises()
    expect(section.attributes('open')).toBeDefined()
    expect(section.text()).toContain('请先填写任务标题')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.text()).toContain('取消任务编辑不会撤销')
  })
  afterEach(() => vi.restoreAllMocks())

  it('can select category and tags', async () => {
    const wrapper = mount(TaskEditor, {
      props: { open: true, task, categories, tags },
      global: { stubs },
    })

    const selects = wrapper.findAll('select')
    await selects[1].setValue('category-2')
    await selects[2].setValue(['tag-2'])
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      category_id: 'category-2',
      tag_ids: ['tag-2'],
    })
  })

  it('sends null when clearing category and keeps an empty tag list', async () => {
    const wrapper = mount(TaskEditor, {
      props: { open: true, task, categories, tags },
      global: { stubs },
    })

    const selects = wrapper.findAll('select')
    await selects[1].setValue('')
    await selects[2].setValue([])
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    const payload = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>

    expect(payload).toMatchObject({ category_id: null, tag_ids: [] })
    expect(Object.prototype.hasOwnProperty.call(payload, 'category_id')).toBe(true)
    expect(payload.category_id).toBeNull()
  })

  it('sends null when clearing a task project', async () => {
    const projectTask: Task = {
      ...task,
      project_id: 'project-1',
      project: projects[0],
    }
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: projectTask, categories, tags, projects },
      global: { stubs },
    })

    const selects = wrapper.findAll('select')
    await selects[3].setValue('')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    const payload = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>
    expect(Object.prototype.hasOwnProperty.call(payload, 'project_id')).toBe(true)
    expect(payload.project_id).toBeNull()
    expect(payload.tag_ids).toEqual(['tag-1'])
  })

  it('sends schedule null when an existing time block is cleared', async () => {
    const scheduledTask: Task = {
      ...task,
      planned_date: '2026-09-26',
      start_at_utc: '2026-09-26T06:00:00.000Z',
      end_at_utc: '2026-09-26T07:00:00.000Z',
      schedule_timezone: 'Asia/Shanghai',
    }
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: scheduledTask, categories, tags },
      global: { stubs },
    })

    await wrapper.get('.clear-schedule-button').trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      planned_date: '2026-09-26',
      schedule: null,
    })
  })

  it('clears both the planned date and schedule when the date is removed', async () => {
    const scheduledTask: Task = {
      ...task,
      planned_date: '2026-09-26',
      start_at_utc: '2026-09-26T06:00:00.000Z',
      end_at_utc: '2026-09-26T07:00:00.000Z',
      schedule_timezone: 'Asia/Shanghai',
    }
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: scheduledTask, categories, tags },
      global: { stubs },
    })

    await wrapper.findAll('input')[1].setValue('')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      planned_date: null,
      schedule: null,
    })
  })

  it('sends a schedule payload for a newly timed task', async () => {
    const wrapper = mount(TaskEditor, {
      props: {
        open: true,
        task: null,
        initialDate: '2026-09-26',
        runtimeTimezone: 'Asia/Shanghai',
        categories,
        tags,
      },
      global: { stubs },
    })

    await wrapper.get('input').setValue('New timed task')
    const timeInputs = wrapper.findAll('input[type="time"]')
    await timeInputs[0].setValue('14:00')
    await timeInputs[1].setValue('15:00')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      title: 'New timed task',
      planned_date: '2026-09-26',
      schedule: {
        start_time: '14:00',
        end_time: '15:00',
        timezone: 'Asia/Shanghai',
      },
    })
  })

  it('supports a date-only deadline and explicitly clears it', async () => {
    const deadlineTask: Task = {
      ...task,
      planned_date: '2026-09-26',
      deadline_date: '2026-10-20',
      deadline_timezone: 'Asia/Shanghai',
      deadline_status: 'upcoming',
    }
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: deadlineTask, categories, tags, runtimeTimezone: 'Asia/Shanghai' },
      global: { stubs },
    })

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[1].setValue('')
    await dateInputs[1].trigger('change')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({ deadline: null })
  })

  it('submits a timed deadline without changing the planned date', async () => {
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: null, initialDate: '2026-09-26', runtimeTimezone: 'Asia/Shanghai', categories, tags },
      global: { stubs },
    })

    await wrapper.get('input').setValue('Deadline task')
    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[1].setValue('2026-10-20')
    await dateInputs[1].trigger('change')
    const timeInputs = wrapper.findAll('input[type="time"]')
    await timeInputs[2].setValue('17:00')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      planned_date: '2026-09-26',
      deadline: { date: '2026-10-20', time: '17:00', timezone: 'Asia/Shanghai' },
    })
  })

  it('changes a timed deadline to date-only without changing the planned date', async () => {
    const timedDeadlineTask: Task = {
      ...task,
      planned_date: '2026-09-26',
      deadline_date: '2026-10-20',
      deadline_at_utc: '2026-10-20T09:00:00.000Z',
      deadline_timezone: 'Asia/Shanghai',
      deadline_status: 'upcoming',
    }
    const wrapper = mount(TaskEditor, {
      props: { open: true, task: timedDeadlineTask, categories, tags, runtimeTimezone: 'Asia/Shanghai' },
      global: { stubs },
    })

    const deadlineTimeInput = wrapper.findAll('input[type="time"]')[2]
    await deadlineTimeInput.setValue('')
    await deadlineTimeInput.trigger('input')
    await wrapper.findAll('button').find((button) => button.text() === '保存任务')!.trigger('click')

    const payload = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>
    expect(payload.planned_date).toBe('2026-09-26')
    expect(payload.deadline).toEqual({ date: '2026-10-20', timezone: 'Asia/Shanghai' })
  })

  it('creates a repeat rule with the current Task version', async () => {
    vi.spyOn(reminderApi, 'list').mockResolvedValue([])
    vi.spyOn(taskApi, 'get').mockResolvedValue({ ...task, version: 5 })
    const create = vi.spyOn(recurrenceApi, 'create').mockResolvedValue({
      id: 'rule-1', frequency: 'daily', weekdays: null, month_day: null,
      starts_on: '2026-09-26', timezone: 'Asia/Shanghai', stopped_at_utc: null,
      created_at_utc: '2026-09-26T00:00:00Z', updated_at_utc: '2026-09-26T00:00:00Z', version: 1,
    })
    const repeatTask = { ...task, planned_date: '2026-09-26', version: 4 }
    const wrapper = mount(TaskEditor, {
      props: { open: false, task: repeatTask, categories, tags, runtimeTimezone: 'Asia/Shanghai' },
      global: { stubs },
    })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '启用重复')!.trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledWith('task-1', expect.objectContaining({ version: 4, frequency: 'daily' }))
    expect(create).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[role="status"]').text()).toBe('重复规则已保存')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('keeps draft and untouched deadline when the same task is refreshed', async () => {
    const original = { ...task, deadline_date: '2026-10-20', deadline_timezone: 'Asia/Shanghai' }
    const wrapper = mount(TaskEditor, { props: { open: true, task: original, categories, tags }, global: { stubs } })
    await wrapper.get('input').setValue('未保存的标题')
    await wrapper.setProps({ task: { ...original, version: 5 }, saveError: '保存失败，请重试。' })
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('未保存的标题')
    expect(wrapper.text()).toContain('保存失败，请重试。')
    const group = wrapper.get('details')
    group.element.removeAttribute('open')
    group.element.setAttribute('open', '')
    await wrapper.findAll('button').find(b => b.text() === '保存任务')!.trigger('click')
    const payload = wrapper.emitted('submit')![0]![0] as Record<string, unknown>
    expect(payload.title).toBe('未保存的标题')
    expect(payload).not.toHaveProperty('deadline')
    expect(payload).not.toHaveProperty('schedule')
  })

  it('saves repeat immediately without closing or submitting the Task draft', async () => {
    vi.spyOn(reminderApi, 'list').mockResolvedValue([])
    vi.spyOn(recurrenceApi, 'create').mockResolvedValue({ id: 'rule-1', frequency: 'daily', weekdays: null, month_day: null, starts_on: '2026-09-26', timezone: 'Asia/Shanghai', stopped_at_utc: null, created_at_utc: '', updated_at_utc: '', version: 1 })
    vi.spyOn(taskApi, 'get').mockResolvedValue({ ...task, version: 5, recurrence_rule_id: 'rule-1' })
    const wrapper = mount(TaskEditor, { props: { open: true, task: { ...task, planned_date: '2026-09-26' }, categories, tags, runtimeTimezone: 'Asia/Shanghai' }, global: { stubs } })
    await wrapper.get('input').setValue('重复操作前的草稿')
    await wrapper.findAll('button').find(b => b.text() === '启用重复')!.trigger('click')
    await flushPromises()
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('重复操作前的草稿')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
    expect(wrapper.emitted('changed')![0]![0]).toMatchObject({ version: 5 })
  })

  it('keeps Task draft after independently saving a reminder', async () => {
    vi.spyOn(reminderApi, 'create').mockResolvedValue({} as never)
    vi.spyOn(reminderApi, 'list').mockResolvedValue([])
    const wrapper = mount(TaskEditor, { props: { open: true, task: { ...task, planned_date: '2026-09-26' }, categories, tags }, global: { stubs } })
    await wrapper.get('input').setValue('提醒操作前的草稿')
    await wrapper.get('input[aria-label="提醒时间"]').setValue('14:00')
    await wrapper.findAll('button').find(b => b.text() === '新增提醒')!.trigger('click')
    await flushPromises()
    expect(reminderApi.create).toHaveBeenCalledTimes(1)
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('提醒操作前的草稿')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })

  it('explains why new tasks cannot edit recurrence or reminders', () => {
    const wrapper = mount(TaskEditor, { props: { open: true, task: null, categories, tags }, global: { stubs } })
    expect(wrapper.text()).toContain('保存任务后可设置重复规则和提醒。')
    expect(wrapper.findAll('button').some(b => ['启用重复', '新增提醒'].includes(b.text()))).toBe(false)
    expect(wrapper.text()).not.toContain('保存全部')
  })

  it('does not discard unsaved draft when skipping the current occurrence', async () => {
    const rule = { id: 'rule-1', frequency: 'daily' as const, weekdays: null, month_day: null, starts_on: '2026-09-26', timezone: 'Asia/Shanghai', stopped_at_utc: null, created_at_utc: '', updated_at_utc: '', version: 1 }
    vi.spyOn(reminderApi, 'list').mockResolvedValue([])
    vi.spyOn(recurrenceApi, 'get').mockResolvedValue(rule)
    const skip = vi.spyOn(recurrenceApi, 'skip').mockResolvedValue({} as never)
    const wrapper = mount(TaskEditor, { props: { open: false, task: { ...task, recurrence_rule_id: rule.id }, categories, tags }, global: { stubs } })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.get('input').setValue('需要保留的草稿')
    await wrapper.findAll('button').find(b => b.text() === '跳过本次')!.trigger('click')
    expect(skip).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先保存任务草稿')
    expect(wrapper.emitted('update:open')).toBeUndefined()
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('需要保留的草稿')
  })
})
