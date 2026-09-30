import { expect, test } from '@playwright/test'

import {
  createTask,
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  todayDate,
  uniqueName,
} from '../helpers/api'

async function chooseRepeatFrequency(
  page: import('@playwright/test').Page,
  dialog: import('@playwright/test').Locator,
  label: '每天' | '每周' | '每月',
): Promise<void> {
  const item = dialog.locator('.el-form-item').filter({ hasText: '重复方式' })
  await item.locator('.el-select').click()
  await page.getByRole('option', { name: label, exact: true }).click()
}

async function getRecurrenceRule(request: import('@playwright/test').APIRequestContext, ruleId: string) {
  const response = await request.get(`/api/v1/recurrence-rules/${ruleId}`)
  expect(response.ok()).toBeTruthy()
  return await response.json() as {
    frequency: string
    weekdays: number[] | null
    month_day: number | null
    stopped_at_utc: string | null
    version: number
  }
}

async function chooseTodayDateField(
  page: import('@playwright/test').Page,
  dialog: import('@playwright/test').Locator,
  label: string,
): Promise<void> {
  const editor = dialog.locator('.el-form-item').filter({ hasText: label }).locator('.el-date-editor')
  await editor.click()
  const picker = page.locator('.el-picker-panel:visible').last()
  await expect(picker).toBeVisible()
  const day = String(Number(todayDate().slice(-2)))
  await picker
    .locator('td.available:not(.prev-month):not(.next-month)')
    .filter({ hasText: new RegExp(`^${day}$`) })
    .click()
}

test('截止日期可以展示并在任务编辑器中读取', async ({ page, request }) => {
  const title = uniqueName('E2E-截止日期')
  const task = await createTask(request, {
    title,
    planned_date: todayDate(),
    deadline: { date: '2099-01-01', timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#today')
  const card = taskCard(page, title)
  await expect(card).toContainText('截止：2099-01-01')

  const dialog = await openTaskEditor(page, title)
  await expect(dialog.getByText('截止日期', { exact: true })).toBeVisible()
  await expect(dialog.getByText('截止时间（可选）', { exact: true })).toBeVisible()
  await expect(dialog.getByLabel('截止时区')).toHaveValue('Asia/Shanghai')

  const response = await request.get(`/api/v1/tasks/${task.id}`)
  expect(response.ok()).toBeTruthy()
  const persisted = await response.json() as { deadline_date: string | null; planned_date: string | null }
  expect(persisted.deadline_date).toBe('2099-01-01')
  expect(persisted.planned_date).toBe(todayDate())
})

test('可以在浏览器中创建具体时间截止日期并清除', async ({ page, request }) => {
  const title = uniqueName('E2E-浏览器截止日期')

  await page.goto('/#calendar')
  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  const createDialog = page.locator('.el-dialog').filter({ hasText: '新建任务' }).last()
  await expect(createDialog).toBeVisible()
  await createDialog.getByLabel('任务标题').fill(title)
  await chooseTodayDateField(page, createDialog, '截止日期')
  await createDialog.locator('input[aria-label="截止时间"]').fill('23:59')
  await createDialog.getByRole('button', { name: '保存任务', exact: true }).click()
  await expect(createDialog).toBeHidden()
  await page.goto('/#today')

  const listResponse = await request.get(`/api/v1/tasks?q=${encodeURIComponent(title)}`)
  expect(listResponse.ok()).toBeTruthy()
  const createdTasks = await listResponse.json() as Array<{
    id: string
    deadline_date: string | null
    deadline_at_utc: string | null
  }>
  expect(createdTasks).toHaveLength(1)
  expect(createdTasks[0].deadline_date).toBe(todayDate())
  expect(createdTasks[0].deadline_at_utc).not.toBeNull()

  const dialog = await openTaskEditor(page, title)
  const deadlineEditor = dialog
    .locator('.el-form-item')
    .filter({ hasText: '截止日期' })
    .locator('.el-date-editor')
  await deadlineEditor.hover()
  await deadlineEditor.locator('.el-input__icon.el-icon-circle-close, .clear-icon').click()
  await saveTaskEditor(dialog)

  const cleared = await (await request.get(`/api/v1/tasks/${createdTasks[0].id}`)).json() as {
    deadline_date: string | null
    deadline_at_utc: string | null
    planned_date: string | null
  }
  expect(cleared.deadline_date).toBeNull()
  expect(cleared.deadline_at_utc).toBeNull()
  expect(cleared.planned_date).toBe(todayDate())
})

test('清除截止日期发送 null 且不改变计划日期和时间安排', async ({ page, request }) => {
  const title = uniqueName('E2E-清除截止日期')
  const task = await createTask(request, {
    title,
    planned_date: todayDate(),
    schedule: { start_time: '23:00', end_time: '23:30', timezone: 'Asia/Shanghai' },
    deadline: { date: '2099-01-01', time: '17:00', timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#today')
  const dialog = await openTaskEditor(page, title)
  const deadlineEditor = dialog
    .locator('.el-form-item')
    .filter({ hasText: '截止日期' })
    .locator('.el-date-editor')
  await deadlineEditor.hover()
  await deadlineEditor.locator('.el-input__icon.el-icon-circle-close, .clear-icon').click()
  await saveTaskEditor(dialog)

  const response = await request.get(`/api/v1/tasks/${task.id}`)
  expect(response.ok()).toBeTruthy()
  const persisted = await response.json() as {
    deadline_date: string | null
    deadline_at_utc: string | null
    deadline_timezone: string | null
    planned_date: string | null
    start_at_utc: string | null
    end_at_utc: string | null
    schedule_timezone: string | null
  }
  expect(persisted.deadline_date).toBeNull()
  expect(persisted.deadline_at_utc).toBeNull()
  expect(persisted.deadline_timezone).toBeNull()
  expect(persisted.planned_date).toBe(todayDate())
  expect(persisted.start_at_utc).toMatch(/T15:00:00\.000000Z$/)
  expect(persisted.end_at_utc).toMatch(/T15:30:00\.000000Z$/)
  expect(persisted.schedule_timezone).toBe('Asia/Shanghai')
})

test('重复任务可以通过界面创建并跳过当前 occurrence', async ({ page, request }) => {
  const title = uniqueName('E2E-重复任务')
  const task = await createTask(request, { title, planned_date: todayDate() })

  await page.goto('/#today')
  const dialog = await openTaskEditor(page, title)
  await dialog.getByRole('button', { name: '启用重复', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const afterCreate = await (await request.get(`/api/v1/tasks/${task.id}`)).json() as {
    recurrence_rule_id: string | null
  }
  expect(afterCreate.recurrence_rule_id).toBeTruthy()

  await page.reload()
  const recurringCard = taskCard(page, title)
  await recurringCard.getByRole('button', { name: /更多操作/ }).click()
  await expect(page.getByRole('menuitem', { name: '跳过本次', exact: true })).toBeVisible()
  await page.getByRole('menuitem', { name: '跳过本次', exact: true }).click()

  await expect(taskCard(page, title)).toHaveCount(0)
  const visibleTasks = await (await request.get(`/api/v1/tasks?q=${encodeURIComponent(title)}`)).json() as Array<{
    recurrence_rule_id: string | null
    recurrence_occurrence_date: string | null
  }>
  expect(visibleTasks).toHaveLength(1)
  expect(visibleTasks[0].recurrence_rule_id).toBe(afterCreate.recurrence_rule_id)
  expect(visibleTasks[0].recurrence_occurrence_date).toBeTruthy()
})

test('每周重复可以设置多个星期、编辑并跳过本次', async ({ page, request }) => {
  const title = uniqueName('E2E-每周重复')
  const task = await createTask(request, { title, planned_date: todayDate() })

  await page.goto('/#today')
  let dialog = await openTaskEditor(page, title)
  await chooseRepeatFrequency(page, dialog, '每周')
  const weekdays = dialog.locator('.weekday-picker input[type="checkbox"]')
  await weekdays.nth(1).check()
  await weekdays.nth(2).check()
  await dialog.getByRole('button', { name: '启用重复', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const created = await (await request.get(`/api/v1/tasks/${task.id}`)).json() as {
    recurrence_rule_id: string | null
  }
  expect(created.recurrence_rule_id).toBeTruthy()
  const createdRule = await getRecurrenceRule(request, created.recurrence_rule_id as string)
  expect(createdRule.frequency).toBe('weekly')
  expect(createdRule.weekdays).toEqual([0, 1, 2])

  let materializeCalls = 0
  page.on('request', (requestEvent) => {
    if (requestEvent.url().includes('/materialize')) materializeCalls += 1
  })
  await page.reload()
  await expect(taskCard(page, title)).toBeVisible()
  expect(materializeCalls).toBe(0)

  dialog = await openTaskEditor(page, title)
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeVisible()
  await weekdays.nth(2).uncheck()
  await weekdays.nth(4).check()
  await dialog.getByRole('button', { name: '保存规则', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const editedRule = await getRecurrenceRule(request, created.recurrence_rule_id as string)
  expect(editedRule.weekdays).toEqual([0, 1, 4])
  expect(editedRule.version).toBe(2)

  await page.reload()
  dialog = await openTaskEditor(page, title)
  await dialog.getByRole('button', { name: '手动生成下一次', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(materializeCalls).toBe(1)

  await page.reload()
  const recurringCard = taskCard(page, title)
  await recurringCard.getByRole('button', { name: /更多操作/ }).click()
  await page.getByRole('menuitem', { name: '跳过本次', exact: true }).click()
  await expect(taskCard(page, title)).toHaveCount(0)
  const visibleTasks = await (await request.get(`/api/v1/tasks?q=${encodeURIComponent(title)}`)).json() as Array<{
    recurrence_occurrence_date: string | null
  }>
  expect(visibleTasks).toHaveLength(1)
  expect(visibleTasks[0].recurrence_occurrence_date).toBeTruthy()
  expect(visibleTasks[0].recurrence_occurrence_date as string > todayDate()).toBeTruthy()
})

test('每月重复可以修改日期并停止而不删除当前任务', async ({ page, request }) => {
  const title = uniqueName('E2E-每月重复')
  const task = await createTask(request, { title, planned_date: todayDate() })

  await page.goto('/#today')
  let dialog = await openTaskEditor(page, title)
  await chooseRepeatFrequency(page, dialog, '每月')
  await dialog.locator('input[aria-label="每月日期"]').fill('15')
  await dialog.getByRole('button', { name: '启用重复', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const created = await (await request.get(`/api/v1/tasks/${task.id}`)).json() as {
    recurrence_rule_id: string | null
  }
  expect(created.recurrence_rule_id).toBeTruthy()
  const createdRule = await getRecurrenceRule(request, created.recurrence_rule_id as string)
  expect(createdRule.frequency).toBe('monthly')
  expect(createdRule.month_day).toBe(15)

  await page.reload()
  dialog = await openTaskEditor(page, title)
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeVisible()
  await dialog.locator('input[aria-label="每月日期"]').fill('28')
  await dialog.getByRole('button', { name: '保存规则', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const editedRule = await getRecurrenceRule(request, created.recurrence_rule_id as string)
  expect(editedRule.month_day).toBe(28)
  expect(editedRule.version).toBe(2)

  await page.reload()
  dialog = await openTaskEditor(page, title)
  await dialog.getByRole('button', { name: '停止重复', exact: true }).click()
  const confirm = page.locator('.el-message-box').last()
  await expect(confirm).toContainText('停止重复后不会再生成新的任务')
  await confirm.getByRole('button', { name: '停止重复', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()

  const stoppedRule = await getRecurrenceRule(request, created.recurrence_rule_id as string)
  expect(stoppedRule.stopped_at_utc).not.toBeNull()
  const currentTask = await (await request.get(`/api/v1/tasks/${task.id}`)).json() as {
    status: string
    deleted_at_utc: string | null
  }
  expect(currentTask.status).toBe('pending')
  expect(currentTask.deleted_at_utc).toBeNull()
})

test('提醒可以通过编辑器新增、修改和删除', async ({ page, request }) => {
  const title = uniqueName('E2E-提醒管理')
  const task = await createTask(request, { title, planned_date: todayDate() })

  await page.goto('/#today')
  const dialog = await openTaskEditor(page, title)
  await dialog.locator('input[aria-label="提醒时间"]').fill('23:59')
  await dialog.getByRole('button', { name: '新增提醒', exact: true }).click()
  const reminderRow = dialog.locator('.reminder-row').first()
  await expect(reminderRow).toBeVisible()

  await reminderRow.getByRole('button', { name: '修改', exact: true }).click()
  await dialog.locator('input[aria-label="提醒时间"]').fill('23:58')
  await dialog.getByRole('button', { name: '保存提醒', exact: true }).click()
  await expect(reminderRow).toContainText('23:58')

  await reminderRow.getByRole('button', { name: '删除', exact: true }).click()
  const confirm = page.locator('.el-message-box').last()
  await confirm.getByRole('button', { name: '删除', exact: true }).click()
  await expect(dialog.locator('.reminder-row')).toHaveCount(0)

  const reminders = await (await request.get(`/api/v1/tasks/${task.id}/reminders`)).json() as unknown[]
  expect(reminders).toHaveLength(0)
})

test('到期提醒可以在浏览器中确认且不会自动关闭', async ({ page, request }) => {
  const title = uniqueName('E2E-确认提醒')
  const task = await createTask(request, { title, planned_date: todayDate() })
  const reminderResponse = await request.post(`/api/v1/tasks/${task.id}/reminders`, {
    data: { date: '2000-01-01', time: '00:00', timezone: 'Asia/Shanghai' },
  })
  expect(reminderResponse.ok()).toBeTruthy()

  await page.goto('/#today')
  const messageBox = page.locator('.el-message-box').filter({ hasText: '这条任务提醒已到时间' }).last()
  await expect(messageBox).toBeVisible()
  await messageBox.getByRole('button', { name: '确认提醒', exact: true }).click()

  await expect.poll(async () => {
    const response = await request.get(`/api/v1/tasks/${task.id}/reminders`)
    const reminders = await response.json() as Array<{ status: string }>
    return reminders[0]?.status
  }).toBe('acknowledged')
})

test('任务编辑器可以关闭待处理提醒并保留提醒状态', async ({ page, request }) => {
  const title = uniqueName('E2E-提醒')
  const task = await createTask(request, { title, planned_date: todayDate() })
  const reminderResponse = await request.post(`/api/v1/tasks/${task.id}/reminders`, {
    data: { date: '2099-01-01', time: '09:30', timezone: 'Asia/Shanghai' },
  })
  expect(reminderResponse.ok()).toBeTruthy()

  await page.goto('/#today')
  const dialog = await openTaskEditor(page, title)
  await expect(dialog.getByText('1 条', { exact: true })).toBeVisible()
  const reminderRow = dialog.locator('.reminder-row').first()
  await reminderRow.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(reminderRow.getByText('已关闭', { exact: true })).toBeVisible()

  const reminders = await (await request.get(`/api/v1/tasks/${task.id}/reminders`)).json() as Array<{
    status: string
  }>
  expect(reminders).toHaveLength(1)
  expect(reminders[0].status).toBe('dismissed')
})
