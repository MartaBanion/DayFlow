// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskEditor from './TaskEditor.vue'
import type { Task } from '../types'

const stubs = {
  'el-button': {
    props: ['nativeType'],
    template: '<button :type="nativeType || \'button\'" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-date-picker': {
    props: ['modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-dialog': {
    props: ['modelValue'],
    template: '<div v-if="modelValue"><slot /></div>',
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

describe('TaskEditor organization fields', () => {
  it('can select category and tags', async () => {
    const wrapper = mount(TaskEditor, {
      props: { open: true, task, categories, tags },
      global: { stubs },
    })

    const selects = wrapper.findAll('select')
    await selects[1].setValue('category-2')
    await selects[2].setValue(['tag-2'])
    await wrapper.findAll('button').find((button) => button.text() === '保存修改')!.trigger('click')

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
    await wrapper.findAll('button').find((button) => button.text() === '保存修改')!.trigger('click')

    const payload = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>

    expect(payload).toMatchObject({ category_id: null, tag_ids: [] })
    expect(Object.prototype.hasOwnProperty.call(payload, 'category_id')).toBe(true)
    expect(payload.category_id).toBeNull()
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
    await wrapper.findAll('button').find((button) => button.text() === '保存修改')!.trigger('click')

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
    await wrapper.findAll('button').find((button) => button.text() === '保存修改')!.trigger('click')

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
    await wrapper.findAll('button').find((button) => button.text() === '创建任务')!.trigger('click')

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
})
