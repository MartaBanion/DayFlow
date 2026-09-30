// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ReminderCenter from './ReminderCenter.vue'
import { reminderApi, taskApi } from '../api'

const reminder = {
  id: 'reminder-1',
  task_id: 'task-1',
  trigger_at_utc: '2026-09-29T08:00:00Z',
  reminder_timezone: 'Asia/Shanghai',
  status: 'pending' as const,
  acknowledged_at_utc: null,
  dismissed_at_utc: null,
  created_at_utc: '2026-09-29T00:00:00Z',
  updated_at_utc: '2026-09-29T00:00:00Z',
  version: 1,
}

describe('ReminderCenter', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    vi.spyOn(taskApi, 'get').mockResolvedValue({ id: 'task-1', title: '学习 Linux' } as never)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('acknowledges a due reminder once per browser session', async () => {
    vi.spyOn(reminderApi, 'due').mockResolvedValue([reminder])
    const acknowledge = vi.spyOn(reminderApi, 'acknowledge').mockResolvedValue({ ...reminder, status: 'acknowledged', version: 2 })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)

    const first = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    first.unmount()
    const second = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(acknowledge).toHaveBeenCalledTimes(1)
    second.unmount()
  })

  it('dismisses a reminder when the user closes the prompt', async () => {
    vi.spyOn(reminderApi, 'due').mockResolvedValue([reminder])
    const dismiss = vi.spyOn(reminderApi, 'dismiss').mockResolvedValue({ ...reminder, status: 'dismissed', version: 2 })
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue(new Error('closed'))

    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(dismiss).toHaveBeenCalledWith('reminder-1', 1)
    wrapper.unmount()
  })

  it('does not dismiss when acknowledging fails', async () => {
    vi.spyOn(reminderApi, 'due').mockResolvedValue([reminder])
    const acknowledge = vi.spyOn(reminderApi, 'acknowledge').mockRejectedValue(new Error('network'))
    const dismiss = vi.spyOn(reminderApi, 'dismiss').mockResolvedValue({ ...reminder, status: 'dismissed', version: 2 })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)

    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(acknowledge).toHaveBeenCalledWith('reminder-1', 1)
    expect(dismiss).not.toHaveBeenCalled()
    expect(window.sessionStorage.getItem('dayflow.reminder-shown.reminder-1')).toBeNull()
    wrapper.unmount()
  })
})
