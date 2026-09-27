// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import TaskCard from './TaskCard.vue'
import type { Task } from '../types'

const task: Task = {
  id: 'task-organization',
  title: 'Review Linux lab',
  description: 'Check the networking notes',
  status: 'pending',
  planned_date: null,
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'high',
  category: { id: 'category-1', name: 'Learning' },
  tags: [
    { id: 'tag-1', name: 'linux' },
    { id: 'tag-2', name: 'lab' },
  ],
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
}

describe('TaskCard organization metadata', () => {
  it('renders priority, category, tags, and Inbox date semantics', () => {
    const wrapper = mount(TaskCard, {
      props: { task },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('Learning')
    expect(wrapper.text()).toContain('linux')
    expect(wrapper.text()).toContain('lab')
    expect(wrapper.text()).toContain('计划日期：收件箱')
  })
})
