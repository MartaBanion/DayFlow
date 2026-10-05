// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, taskApi } from '../api'
import type { Task } from '../types'
import QuickRescheduleMenu from './QuickRescheduleMenu.vue'

const task: Task = {
  id: 'quick-task',
  title: '准备会议材料',
  description: null,
  status: 'pending',
  planned_date: '2026-10-05',
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-10-05T00:00:00.000000Z',
  updated_at_utc: '2026-10-05T00:00:00.000000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 3,
}

const stubs = {
  'el-dialog': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div v-if="modelValue" class="test-dialog"><slot /><slot name="footer" /></div>',
  },
  'el-button': {
    props: ['disabled', 'loading'],
    emits: ['click'],
    template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-alert': {
    props: ['title'],
    template: '<div role="alert">{{ title }}<slot /></div>',
  },
  'el-date-picker': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input id="quick-reschedule-date" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

afterEach(() => vi.restoreAllMocks())

function mountMenu(overrides: Partial<Task> = {}) {
  return mount(QuickRescheduleMenu, {
    props: {
      task: { ...task, ...overrides },
      runtimeLocalDate: '2026-10-05',
      modelValue: true,
    },
    global: { stubs },
  })
}

describe('QuickRescheduleMenu', () => {
  it('uses the shared core and current task version for Tomorrow', async () => {
    const update = vi.spyOn(taskApi, 'update').mockResolvedValue({ ...task, planned_date: '2026-10-06', version: 4 })
    const wrapper = mountMenu()

    await wrapper.findAll('button').find(button => button.text() === '明天')!.trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(task.id, task.version, { planned_date: '2026-10-06' })
    expect(wrapper.emitted('success')).toHaveLength(1)
  })

  it('requires confirmation before clearing a scheduled Inbox task', async () => {
    const update = vi.spyOn(taskApi, 'update').mockResolvedValue({ ...task, planned_date: null, version: 4 })
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce(new Error('cancel'))
    const wrapper = mountMenu({ start_at_utc: '2026-10-05T01:00:00.000000Z', end_at_utc: '2026-10-05T02:00:00.000000Z', schedule_timezone: 'Asia/Shanghai' })

    expect(wrapper.text()).toContain('移回收件箱会清除当前时间安排')
    await wrapper.findAll('button').find(button => button.text() === '移回收件箱')!.trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledOnce()
    expect(update).not.toHaveBeenCalled()

    confirm.mockResolvedValueOnce({ action: 'confirm' })
    await wrapper.findAll('button').find(button => button.text() === '移回收件箱')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(task.id, task.version, { planned_date: null, schedule: null })
  })

  it('supports Choose Date and keeps the selected date out of browser date math', async () => {
    const update = vi.spyOn(taskApi, 'update').mockResolvedValue({ ...task, planned_date: '2027-01-01', version: 4 })
    const wrapper = mountMenu()

    await wrapper.findAll('button').find(button => button.text() === '选择日期')!.trigger('click')
    await wrapper.get('#quick-reschedule-date').setValue('2027-01-01')
    await wrapper.findAll('button').find(button => button.text() === '确认日期')!.trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(task.id, task.version, { planned_date: '2027-01-01' })
  })

  it('keeps the dialog open and reports update failures', async () => {
    vi.spyOn(taskApi, 'update').mockRejectedValue(new ApiRequestError('offline', 503))
    const wrapper = mountMenu()

    await wrapper.findAll('button').find(button => button.text() === '今天')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('日历请求失败')
    expect(wrapper.find('.test-dialog').exists()).toBe(true)
  })
})
