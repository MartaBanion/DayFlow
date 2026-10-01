// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, projectApi } from '../api'
import type { Project } from '../types'
import ProjectsView from './ProjectsView.vue'

const stubs = {
  'el-alert': { props: ['title'], template: '<div class="stub-alert">{{ title }}</div>' },
  'el-button': {
    props: ['nativeType', 'disabled', 'loading'],
    template: '<button :disabled="disabled" :type="nativeType || \'button\'"><slot /></button>',
  },
  'el-dialog': {
    props: ['modelValue', 'title'],
    template: '<div v-if="modelValue" class="stub-dialog"><h3>{{ title }}</h3><slot /></div>',
  },
  'el-empty': { props: ['description'], template: '<div class="stub-empty">{{ description }}<slot /></div>' },
  'el-form': { template: '<form @submit.prevent="$emit(\'submit\')"><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    template: '<textarea v-if="$attrs.type === \'textarea\'" :value="modelValue" v-bind="$attrs" @input="$emit(\'update:modelValue\', $event.target.value)" /><input v-else :value="modelValue" v-bind="$attrs" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-progress': { props: ['percentage'], template: '<div class="stub-progress">{{ percentage }}%</div>' },
  'el-tag': { template: '<span class="stub-tag"><slot /></span>' },
  'el-dropdown': { template: '<div><slot /><slot name="dropdown" /></div>' },
  'el-dropdown-menu': { template: '<div><slot /></div>' },
  'el-dropdown-item': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'project-1',
    name: '学习 Linux',
    description: 'Linux 学习计划',
    status: 'active',
    created_at_utc: '2026-09-26T00:00:00.000000Z',
    updated_at_utc: '2026-09-26T00:00:00.000000Z',
    completed_at_utc: null,
    deleted_at_utc: null,
    version: 1,
    task_count: 2,
    completed_task_count: 1,
    progress_percent: 50,
    ...overrides,
  }
}

describe('ProjectsView', () => {
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' })
    vi.spyOn(projectApi, 'list').mockResolvedValue([
      makeProject(),
      makeProject({ id: 'project-deleted', name: '已删除项目', deleted_at_utc: '2026-09-27T00:00:00Z' }),
    ])
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  it('loads projects and displays backend progress', async () => {
    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()

    expect(projectApi.list).toHaveBeenCalledWith({ includeDeleted: true })
    expect(wrapper.text()).toContain('学习 Linux')
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('1 / 2 个任务已完成')
  })

  it('creates and edits a project', async () => {
    const created = makeProject({ id: 'project-2', name: '个人博客' })
    let currentProjects = [makeProject()]
    vi.mocked(projectApi.list).mockImplementation(async () => currentProjects)
    vi.spyOn(projectApi, 'create').mockImplementation(async () => {
      currentProjects = [...currentProjects, created]
      return created
    })
    vi.spyOn(projectApi, 'update').mockResolvedValue({ ...created, version: 2, name: '博客项目' })

    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '新建项目')!.trigger('click')
    await wrapper.get('input[placeholder="例如：学习 Linux"]').setValue('个人博客')
    await wrapper.findAll('.stub-dialog button').find((button) => button.text() === '创建项目')!.trigger('click')
    await flushPromises()

    expect(projectApi.create).toHaveBeenCalledWith({ name: '个人博客', description: null })
    expect(wrapper.text()).toContain('个人博客')

    const editButton = wrapper.findAll('.project-card').find((card) => card.text().includes('个人博客'))!.findAll('button').find((button) => button.text() === '编辑')
    await editButton!.trigger('click')
    await wrapper.get('input[placeholder="例如：学习 Linux"]').setValue('博客项目')
    await wrapper.findAll('.stub-dialog button').find((button) => button.text() === '保存修改')!.trigger('click')
    await flushPromises()
    expect(projectApi.update).toHaveBeenCalledWith('project-2', 1, {
      name: '博客项目',
      description: 'Linux 学习计划',
    })
  })

  it('shows deleted projects and restores them without changing task history in the UI', async () => {
    const deleted = makeProject({
      id: 'project-deleted',
      name: '已删除项目',
      deleted_at_utc: '2026-09-27T00:00:00Z',
      version: 3,
    })
    vi.mocked(projectApi.list).mockResolvedValue([makeProject(), deleted])
    vi.spyOn(projectApi, 'restore').mockResolvedValue({ ...deleted, deleted_at_utc: null, version: 4 })

    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.deleted-project-section .section-heading button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.deleted-project-section').text()).toContain('恢复项目')
    const restoreButton = wrapper.find('.deleted-project-section').findAll('button').find((button) => button.text() === '恢复项目')
    await restoreButton!.trigger('click')
    await flushPromises()
    expect(projectApi.restore).toHaveBeenCalledWith('project-deleted', 3)
  })

  it('keeps API failures in an error state', async () => {
    vi.mocked(projectApi.list)
      .mockRejectedValueOnce(new ApiRequestError('unavailable', 503))
      .mockResolvedValueOnce([makeProject()])
    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.today-state.is-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('项目加载失败')
    expect(wrapper.text()).toContain('项目加载失败，请稍后重试。（HTTP 503）')

    await wrapper.get('.today-state.is-error button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.today-state.is-error').exists()).toBe(false)
    expect(wrapper.text()).toContain('学习 Linux')
  })

  it('handles complete, reopen, and delete with the current project version', async () => {
    let current = makeProject({ task_count: 1, completed_task_count: 0, progress_percent: 0 })
    vi.mocked(projectApi.list).mockImplementation(async () => [current])
    vi.spyOn(projectApi, 'complete').mockImplementation(async (_id, version) => {
      expect(version).toBe(1)
      current = { ...current, status: 'completed', completed_at_utc: '2026-09-28T00:00:00Z', version: 2 }
      return current
    })
    vi.spyOn(projectApi, 'reopen').mockImplementation(async (_id, version) => {
      expect(version).toBe(2)
      current = { ...current, status: 'active', completed_at_utc: null, version: 3 }
      return current
    })
    vi.spyOn(projectApi, 'remove').mockImplementation(async (_id, version) => {
      expect(version).toBe(3)
      current = { ...current, deleted_at_utc: '2026-09-28T00:00:00Z', version: 4 }
    })

    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()
    const card = () => wrapper!.find('.project-card')

    await card().findAll('button').find((button) => button.text() === '完成项目')!.trigger('click')
    await flushPromises()
    expect(card().text()).toContain('已完成')

    await card().findAll('button').find((button) => button.text() === '重新打开')!.trigger('click')
    await flushPromises()
    expect(card().text()).toContain('进行中')

    await card().findAll('button').find((button) => button.text() === '删除')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.project-card.is-deleted').exists()).toBe(true)
  })

  it('shows distinct project name and version conflict messages', async () => {
    const update = vi
      .spyOn(projectApi, 'update')
      .mockRejectedValue(new ApiRequestError('stale', 409, 'project_version_conflict'))
    const create = vi
      .spyOn(projectApi, 'create')
      .mockRejectedValue(new ApiRequestError('duplicate', 409, 'project_name_conflict'))

    wrapper = mount(ProjectsView, { global: { stubs } })
    await flushPromises()
    const editButton = wrapper.find('.project-card').findAll('button').find((button) => button.text() === '编辑')
    await editButton!.trigger('click')
    await wrapper.get('input[placeholder="例如：学习 Linux"]').setValue('新名称')
    await wrapper.findAll('.stub-dialog button').find((button) => button.text() === '保存修改')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalled()
    expect(wrapper.text()).toContain('项目已被其他操作更新，请刷新后重试。')

    await wrapper.findAll('button').find((button) => button.text() === '新建项目')!.trigger('click')
    await wrapper.get('input[placeholder="例如：学习 Linux"]').setValue('重复项目')
    await wrapper.findAll('.stub-dialog button').find((button) => button.text() === '创建项目')!.trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalled()
    expect(wrapper.text()).toContain('项目名称已存在，请换一个名称。')
  })
})
