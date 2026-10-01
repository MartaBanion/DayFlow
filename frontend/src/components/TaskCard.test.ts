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
  project_id: 'project-1',
  project: { id: 'project-1', name: 'DayFlow', status: 'active' },
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
}

describe('TaskCard organization metadata', () => {
  it('keeps full long titles accessible and disables actions during a request', async () => {
    const title = '很长的任务标题'.repeat(12)
    const wrapper = mount(TaskCard, { props: { task: { ...task, title }, busy: true }, global: { plugins: [ElementPlus] } })
    expect(wrapper.get('h4').attributes('title')).toBe(title)
    expect(wrapper.get('.task-check').attributes('disabled')).toBeDefined()
    await wrapper.get('.task-check').trigger('click')
    expect(wrapper.emitted('complete')).toBeUndefined()
  })
  it('shows high and overdue as explicit labels and a neutral normal priority', () => {
    const wrapper = mount(TaskCard, { props: { task: { ...task, deadline_date: '2026-01-01', deadline_status: 'overdue', deadline_timezone: 'Asia/Shanghai' } }, global: { plugins: [ElementPlus] } })
    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('已逾期')
    const normal = mount(TaskCard, { props: { task: { ...task, priority: 'normal', planned_date: '2026-09-30' }, contextDate: '2026-09-30' }, global: { plugins: [ElementPlus] } })
    expect(normal.text()).not.toContain('计划日期：')
    expect(normal.find('.task-priority-caption').text()).toContain('普通')
    expect(wrapper.find('button[aria-label^="更多操作"]').exists()).toBe(true)
  })
  it('renders priority, category, tags, and Inbox date semantics', () => {
    const wrapper = mount(TaskCard, {
      props: { task },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('Learning')
    expect(wrapper.text()).toContain('linux')
    expect(wrapper.text()).toContain('lab')
    expect(wrapper.text()).toContain('DayFlow')
    expect(wrapper.text()).toContain('暂未安排日期')
  })
})
