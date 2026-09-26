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
    template: '<select :multiple="Array.isArray(modelValue)" :value="modelValue" @change="$emit(\'update:modelValue\', Array.isArray(modelValue) ? Array.from($event.target.selectedOptions).map((option) => option.value) : ($event.target.value || null))"><slot /></select>',
  },
}

const task: Task = {
  id: 'task-1',
  title: 'Review Linux notes',
  description: 'A note',
  status: 'pending',
  planned_date: null,
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

  it('can clear category and tags', async () => {
    const wrapper = mount(TaskEditor, {
      props: { open: true, task, categories, tags },
      global: { stubs },
    })

    const selects = wrapper.findAll('select')
    await selects[1].setValue('')
    await selects[2].setValue([])
    await wrapper.findAll('button').find((button) => button.text() === '保存修改')!.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      category_id: null,
      tag_ids: [],
    })
  })
})
