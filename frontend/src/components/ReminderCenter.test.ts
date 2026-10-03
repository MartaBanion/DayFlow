// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

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
    vi.useRealTimers()
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

  it('shows a restrained error and keeps the last reminder count after polling fails', async () => {
    vi.useFakeTimers()
    const due = vi.spyOn(reminderApi, 'due')
      .mockResolvedValueOnce([reminder])
      .mockRejectedValueOnce(new Error('network'))
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue(new Error('closed'))
    vi.spyOn(reminderApi, 'dismiss').mockRejectedValue(new Error('network'))

    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('1 条')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)

    await vi.advanceTimersByTimeAsync(45_000)
    await flushPromises()

    expect(due).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[role="alert"]').text()).toContain('提醒查询失败')
    expect(wrapper.text()).toContain('1 条')
    wrapper.unmount()
  })

  it('shows the polling error and clears it after a successful retry', async () => {
    const due = vi.spyOn(reminderApi, 'due')
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce([])
    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('提醒查询失败')
    const retry = wrapper.get('button[aria-label="重试提醒查询"]')
    await retry.trigger('click')
    await flushPromises()

    expect(due).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('prevents duplicate retry requests and keeps the error when retry fails', async () => {
    const due = vi.spyOn(reminderApi, 'due').mockRejectedValue(new Error('network'))
    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    let resolveRetry!: (value: Reminder[]) => void
    due.mockImplementationOnce(() => new Promise<Reminder[]>((resolve) => { resolveRetry = resolve }))
    const retry = wrapper.get('button[aria-label="重试提醒查询"]')
    await retry.trigger('click')
    await retry.trigger('click')
    await nextTick()

    expect(due).toHaveBeenCalledTimes(2)
    expect(retry.attributes('disabled')).toBeDefined()
    resolveRetry([])
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('clears the error after the next 45-second poll succeeds', async () => {
    vi.useFakeTimers()
    const due = vi.spyOn(reminderApi, 'due')
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce([])
    const wrapper = mount(ReminderCenter, { global: { plugins: [ElementPlus] } })
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(45_000)
    await flushPromises()

    expect(due).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
    vi.useRealTimers()
  })
})
