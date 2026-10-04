// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, projectApi, taskApi } from '../api'
import type { Project, Task } from '../types'
import ProjectDetailView from './ProjectDetailView.vue'

const stubs = {
  'el-alert': { props: ['title'], template: '<div class="stub-alert"><span>{{ title }}</span><slot /></div>' },
  'el-button': {
    props: ['nativeType', 'disabled', 'loading'],
    template: '<button :disabled="disabled" :type="nativeType || \'button\'"><slot /></button>',
  },
  'el-dialog': { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}<slot /></div>' },
  'el-progress': { props: ['percentage'], template: '<div>{{ percentage }}%</div>' },
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  'el-select': {
    props: ['modelValue'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
  },
  'el-tag': { template: '<span><slot /></span>' },
  TaskEditor: {
    props: ['open'],
    template: '<button v-if="open" class="stub-editor-submit" @click="$emit(\'submit\', { title: \'Unassigned task\', description: null, planned_date: null, priority: \'normal\', category_id: null, tag_ids: [], project_id: null })">保存任务</button>',
  },
  TaskCard: {
    props: ['task'],
    template: '<button class="stub-task" @click="$emit(\'complete\', task)">{{ task.title }}</button>',
  },
}

const project: Project = {
  id: 'project-1',
  name: '学习 Linux',
  description: '学习计划',
  status: 'active',
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 2,
  task_count: 1,
  completed_task_count: 0,
  progress_percent: 0,
}

const task: Task = {
  id: 'task-1',
  title: '完成实验',
  description: null,
  status: 'pending',
  planned_date: null,
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  project_id: project.id,
  project: { id: project.id, name: project.name, status: project.status },
  created_at_utc: '2026-09-26T00:00:00.000000Z',
  updated_at_utc: '2026-09-26T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 1,
}

describe('ProjectDetailView', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.spyOn(projectApi, 'get').mockResolvedValue(project)
    vi.spyOn(taskApi, 'list').mockResolvedValue([task])
    vi.spyOn(taskApi, 'complete').mockResolvedValue({ ...task, status: 'completed', version: 2 })
    vi.spyOn(taskApi, 'create').mockResolvedValue({ ...task, id: 'task-2', title: 'Unassigned task', project_id: null, project: null })
    vi.spyOn(taskApi, 'listCategories').mockResolvedValue([])
    vi.spyOn(taskApi, 'listTags').mockResolvedValue([])
    vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: '2026-09-28' })
    vi.spyOn(projectApi, 'list').mockResolvedValue([project])
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  it('loads project progress and related tasks', async () => {
    wrapper = mount(ProjectDetailView, {
      props: { projectId: project.id },
      global: { stubs },
    })
    await flushPromises()

    expect(taskApi.list).toHaveBeenCalledWith({ projectId: project.id })
    expect(wrapper.text()).toContain('学习 Linux')
    expect(wrapper.text()).toContain('0%')
    expect(wrapper.text()).toContain('完成实验')
  })

  it('refreshes progress after completing a project task', async () => {
    const updatedProject = { ...project, completed_task_count: 1, progress_percent: 100, version: 3 }
    vi.mocked(projectApi.get).mockResolvedValueOnce(project).mockResolvedValueOnce(updatedProject)
    vi.mocked(taskApi.list).mockResolvedValueOnce([task]).mockResolvedValueOnce([{ ...task, status: 'completed', version: 2 }])

    wrapper = mount(ProjectDetailView, {
      props: { projectId: project.id },
      global: { stubs },
    })
    await flushPromises()
    await wrapper.get('.stub-task').trigger('click')
    await flushPromises()

    expect(taskApi.complete).toHaveBeenCalledWith(task.id, task.version)
    expect(wrapper.text()).toContain('100%')
  })

  it('keeps an explicitly cleared project when creating a task from project detail', async () => {
    wrapper = mount(ProjectDetailView, {
      props: { projectId: project.id },
      global: { stubs },
    })
    await flushPromises()

    await wrapper.findAll('.page-header-actions button').find((button) => button.text() === '新建任务')!.trigger('click')
    await flushPromises()
    await wrapper.get('.stub-editor-submit').trigger('click')
    await flushPromises()

    expect(taskApi.create).toHaveBeenCalledWith({
      title: 'Unassigned task',
      description: null,
      planned_date: null,
      priority: 'normal',
      category_id: null,
      tag_ids: [],
      project_id: null,
      schedule: undefined,
    })
  })

  it('shows an error state and retries project detail loading', async () => {
    vi.mocked(projectApi.get)
      .mockRejectedValueOnce(new ApiRequestError('unavailable', 503))
      .mockResolvedValueOnce(project)

    wrapper = mount(ProjectDetailView, {
      props: { projectId: project.id },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.find('.today-state.is-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('项目详情加载失败')
    expect(wrapper.text()).not.toContain('这个项目还没有任务')

    await wrapper.get('.today-state.is-error button').trigger('click')
    await flushPromises()
    expect(projectApi.get).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.today-state.is-error').exists()).toBe(false)
    expect(wrapper.text()).toContain('关联任务')
  })

  it('reuses the fixed project id for task filters and reset', async () => {
    wrapper = mount(ProjectDetailView, {
      props: { projectId: project.id },
      global: { stubs },
    })
    await flushPromises()

    await wrapper.findAll('select')[0].setValue('pending')
    await flushPromises()
    await wrapper.find('#project-overdue-filter').setValue(true)
    await flushPromises()
    await wrapper.findAll('select')[1].setValue('past')
    await flushPromises()
    await wrapper.findAll('select')[2].setValue('planned')
    await flushPromises()

    expect(taskApi.list).toHaveBeenLastCalledWith({
      projectId: project.id,
      status: 'pending',
      overdue: true,
      plannedBucket: 'past',
      sort: 'planned',
    })

    await wrapper.get('.project-task-filters').findAll('button').find(button => button.text() === '清除筛选')!.trigger('click')
    await flushPromises()
    expect(taskApi.list).toHaveBeenLastCalledWith({ projectId: project.id })
    expect(wrapper.text()).toContain('学习 Linux')
  })
})
