// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { projectApi, taskApi } from '../api'
import type { Project } from '../types'
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

const stubs = {
  'el-alert': { props: ['title'], template: '<div>{{ title }}</div>' },
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
})
