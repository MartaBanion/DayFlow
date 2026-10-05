import { expect, test, type Page } from '@playwright/test'

import { addCalendarDays } from '../../src/quickReschedule'
import { createTask, taskCard, todayDate, uniqueName } from '../helpers/api'

async function openQuickReschedule(page: Page, title: string) {
  await page.getByRole('button', { name: `更多操作：${title}` }).click()
  await page.getByRole('menuitem', { name: '调整日期', exact: true }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await expect(dialog).toBeVisible()
  return dialog
}

test('Today → Tomorrow 后任务离开 Today', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-今天到明天')
  await createTask(request, { title, planned_date: date })

  await page.goto('/#today')
  const dialog = await openQuickReschedule(page, title)
  await dialog.getByRole('button', { name: '明天', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(taskCard(page, title)).toHaveCount(0)

  const saved = await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>
  expect(saved.find(task => task.title === title)?.planned_date).toBe(addCalendarDays(date, 1))
})

test('Today → Inbox 会警告并原子清除 Time Block', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-今天到收件箱')
  await createTask(request, {
    title,
    planned_date: date,
    schedule: { start_time: '09:00', end_time: '10:00', timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#today')
  let dialog = await openQuickReschedule(page, title)
  await dialog.getByRole('button', { name: '移回收件箱', exact: true }).click()
  const warning = page.locator('.el-message-box').last()
  await expect(warning).toContainText('移回收件箱会清除当前时间安排')
  await warning.getByRole('button', { name: '取消', exact: true }).click()
  expect((await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>).find(task => task.title === title)?.planned_date).toBe(date)

  // Cancelling the warning leaves the reschedule dialog open so the user can
  // choose another action without reopening the menu.
  await dialog.getByRole('button', { name: '移回收件箱', exact: true }).click()
  await page.locator('.el-message-box').last().getByRole('button', { name: '移回收件箱', exact: true }).click()
  await expect(taskCard(page, title)).toHaveCount(0)

  const inbox = await (await request.get('/api/v1/tasks?inbox=true')).json() as Array<{ title: string; planned_date: string | null; start_at_utc: string | null; end_at_utc: string | null; schedule_timezone: string | null }>
  const moved = inbox.find(task => task.title === title)
  expect(moved).toMatchObject({ planned_date: null, start_at_utc: null, end_at_utc: null, schedule_timezone: null })
})

test('Calendar Task → Today 复用 Quick Reschedule 并刷新当前范围', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-日历到今天')
  await createTask(request, { title, planned_date: addCalendarDays(date, 1) })

  await page.goto('/#calendar')
  await page.getByRole('button', { name: `调整日期：${title}` }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await dialog.getByRole('button', { name: '今天', exact: true }).click()
  await expect(dialog).toBeHidden()

  const saved = await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>
  expect(saved.find(task => task.title === title)?.planned_date).toBe(date)
})

test('Calendar Quick Reschedule 支持 Choose Date', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-选择日期')
  await createTask(request, { title, planned_date: addCalendarDays(date, 1) })

  await page.goto('/#calendar')
  await page.getByRole('button', { name: `调整日期：${title}` }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await dialog.getByRole('button', { name: '选择日期', exact: true }).click()
  await dialog.getByLabel('新的计划日期').click()
  const picker = page.locator('.el-picker-panel:visible').last()
  await picker.locator('td.available:not(.prev-month):not(.next-month)').filter({ hasText: new RegExp(`^${Number(date.slice(-2))}$`) }).click()
  await dialog.getByRole('button', { name: '确认日期', exact: true }).click()
  await expect(dialog).toBeHidden()

  const saved = await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>
  expect(saved.find(task => task.title === title)?.planned_date).toBe(date)
})

test('Time Block 调整日期后保留本地时钟与 timezone', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-时间块移动')
  const created = await createTask(request, {
    title,
    planned_date: addCalendarDays(date, 1),
    schedule: { start_time: '09:00', end_time: '10:00', timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#calendar')
  await page.getByRole('button', { name: `调整日期：${title}` }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await dialog.getByRole('button', { name: '今天', exact: true }).click()
  await expect(dialog).toBeHidden()

  const moved = await (await request.get(`/api/v1/tasks/${created.id}`)).json() as typeof created
  expect(moved.planned_date).toBe(date)
  expect(moved.schedule_timezone).toBe('Asia/Shanghai')
  expect(moved.start_at_utc).not.toBe(created.start_at_utc)
  await expect(page.locator('.calendar-task-timed').filter({ hasText: title })).toContainText('09:00–10:00')
})

test('Calendar Quick Reschedule 复用 schedule conflict 确认流程', async ({ page, request }) => {
  const date = todayDate()
  const firstTitle = uniqueName('V09-冲突已有')
  const secondTitle = uniqueName('V09-冲突待改')
  await createTask(request, { title: firstTitle, planned_date: date, schedule: { start_time: '13:00', end_time: '14:00', timezone: 'Asia/Shanghai' } })
  await createTask(request, { title: secondTitle, planned_date: addCalendarDays(date, 1), schedule: { start_time: '13:00', end_time: '14:00', timezone: 'Asia/Shanghai' } })

  await page.goto('/#calendar')
  await page.getByRole('button', { name: `调整日期：${secondTitle}` }).click()
  let dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await dialog.getByRole('button', { name: '今天', exact: true }).click()
  let conflict = page.locator('.el-message-box').last()
  await expect(conflict).toContainText('该时间段与已有任务冲突')
  await conflict.getByRole('button', { name: '取消', exact: true }).click()

  const unchanged = await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>
  expect(unchanged.find(task => task.title === secondTitle)?.planned_date).toBe(addCalendarDays(date, 1))

  dialog = page.locator('.el-dialog').filter({ hasText: '调整日期' }).last()
  await dialog.getByRole('button', { name: '今天', exact: true }).click()
  conflict = page.locator('.el-message-box').last()
  await conflict.getByRole('button', { name: '仍然保存', exact: true }).click()
  await expect(dialog).toBeHidden()
  const forced = await (await request.get(`/api/v1/tasks?status=pending`)).json() as Array<{ title: string; planned_date: string }>
  expect(forced.find(task => task.title === secondTitle)?.planned_date).toBe(date)
})

test('Recurring occurrence Quick Reschedule 不修改 recurrence rule', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-重复任务')
  const created = await createTask(request, { title, planned_date: date })
  const ruleResponse = await request.post(`/api/v1/tasks/${created.id}/recurrence`, {
    data: { version: created.version, frequency: 'daily', starts_on: date, timezone: 'Asia/Shanghai' },
  })
  expect(ruleResponse.ok()).toBeTruthy()
  const rule = await ruleResponse.json() as { id: string }
  const beforeTask = await (await request.get(`/api/v1/tasks/${created.id}`)).json() as { version: number; recurrence_occurrence_date: string | null }
  const beforeRule = await (await request.get(`/api/v1/recurrence-rules/${rule.id}`)).json()

  await page.goto('/#today')
  const dialog = await openQuickReschedule(page, title)
  await dialog.getByRole('button', { name: '明天', exact: true }).click()
  await expect(dialog).toBeHidden()

  const afterTask = await (await request.get(`/api/v1/tasks/${created.id}`)).json() as typeof beforeTask & { planned_date: string }
  const afterRule = await (await request.get(`/api/v1/recurrence-rules/${rule.id}`)).json()
  expect(afterTask.planned_date).toBe(addCalendarDays(date, 1))
  expect(afterTask.recurrence_occurrence_date).toBe(beforeTask.recurrence_occurrence_date)
  expect(afterRule).toEqual(beforeRule)
})

test('Reminder Quick Reschedule 不修改 trigger/status', async ({ page, request }) => {
  const date = todayDate()
  const title = uniqueName('V09-提醒任务')
  const created = await createTask(request, { title, planned_date: date })
  const reminderResponse = await request.post(`/api/v1/tasks/${created.id}/reminders`, {
    data: { date: addCalendarDays(date, 1), time: '08:00', timezone: 'Asia/Shanghai' },
  })
  expect(reminderResponse.ok()).toBeTruthy()
  const before = await (await request.get(`/api/v1/tasks/${created.id}/reminders`)).json()

  await page.goto('/#today')
  const dialog = await openQuickReschedule(page, title)
  await dialog.getByRole('button', { name: '明天', exact: true }).click()
  await expect(dialog).toBeHidden()

  const after = await (await request.get(`/api/v1/tasks/${created.id}/reminders`)).json()
  expect(after).toEqual(before)
})

test('Month 日期和“还有 N 项”进入现有 Day View', async ({ page, request }) => {
  const date = todayDate()
  const titles = await Promise.all(
    Array.from({ length: 4 }, (_, index) => createTask(request, { title: uniqueName(`V09-月视图-${index}`), planned_date: date })),
  )

  await page.goto('/#calendar')
  await page.getByRole('button', { name: '月', exact: true }).click()
  await expect(page.locator('.calendar-month-view')).toBeVisible()
  await page.getByRole('button', { name: `查看 ${date} 的日视图` }).click()
  await expect(page.locator('.calendar-day-view')).toBeVisible()
  await expect(page.locator('.calendar-day-view')).toContainText(titles[0]!.title)

  await page.getByRole('button', { name: '月', exact: true }).click()
  await expect(page.getByRole('button', { name: `查看 ${date} 的全部任务` })).toBeVisible()
  await page.getByRole('button', { name: `查看 ${date} 的全部任务` }).click()
  await expect(page.locator('.calendar-day-view')).toBeVisible()
})

test('Month 空日期进入 existing Day View', async ({ page }) => {
  await page.goto('/#calendar')
  await page.getByRole('button', { name: '月', exact: true }).click()
  await expect(page.locator('.calendar-month-view')).toBeVisible()

  const emptyDayCells = page.locator('.calendar-month-day:not(.is-outside-month)').filter({
    hasNot: page.locator('.calendar-month-task'),
  })
  await expect(emptyDayCells.first()).toBeVisible()
  const emptyDateButton = emptyDayCells.first().locator('.calendar-month-day-trigger')
  const emptyDate = (await emptyDateButton.getAttribute('aria-label'))?.replace(/^查看 | 的日视图$/g, '')
  expect(emptyDate).toBeTruthy()

  await emptyDateButton.click()
  await expect(page.locator('.calendar-day-view')).toBeVisible()
  await expect(page.locator('.calendar-day-view .calendar-day-heading h3')).toHaveText(emptyDate!)
  await expect(page.getByText('这个时间范围还没有任务', { exact: true })).toHaveCount(0)
})

test('900×700 下 Quick Reschedule 和 Month 控件无横向溢出', async ({ page, request }) => {
  await page.setViewportSize({ width: 900, height: 700 })
  const date = todayDate()
  const title = uniqueName('V09-响应式')
  await createTask(request, { title, planned_date: date })

  await page.goto('/#today')
  const dialog = await openQuickReschedule(page, title)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await dialog.getByRole('button', { name: '取消', exact: true }).click()

  await page.goto('/#calendar')
  await page.getByRole('button', { name: '月', exact: true }).click()
  await expect(page.locator('.calendar-month-view')).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
