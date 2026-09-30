import { expect, test } from '@playwright/test'

import {
  createTask,
  saveTaskEditor,
  taskCard,
  todayDate,
  uniqueName,
} from '../helpers/api'

test('日历支持日周月视图、日期任务和时间块持久化', async ({ page }) => {
  const dateOnlyTitle = uniqueName('E2E-日历-未安排')
  const timedTitle = uniqueName('E2E-日历-时间块')

  await page.goto('/#calendar')
  await expect(page.getByRole('navigation', { name: '主要导航' }).getByRole('link', { name: '日历', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.locator('.calendar-header h2')).toHaveText(/^[0-9]{4}年[0-9]+月 · 第[0-9]+周$/)
  await expect(page.locator('.calendar-header .muted')).toHaveText(/^[0-9]+月[0-9]+日 - [0-9]+月[0-9]+日$/)
  await expect(page.getByRole('button', { name: '周', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  const createDialog = page.locator('.el-dialog').filter({ hasText: '新建任务' }).last()
  await expect(createDialog).toBeVisible()
  await createDialog.getByLabel('任务标题').fill(dateOnlyTitle)
  await createDialog.getByRole('button', { name: '创建任务', exact: true }).click()
  await expect(createDialog).toBeHidden()
  await expect(page.locator('.calendar-task').filter({ hasText: dateOnlyTitle })).toBeVisible()
  await expect(page.getByText('未安排时间', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.calendar-week-untimed')).toBeVisible()
  await expect(page.locator('.calendar-week-timeline')).toBeVisible()
  await expect(page.locator('.calendar-week-column')).toHaveCount(7)

  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  const timedDialog = page.locator('.el-dialog').filter({ hasText: '新建任务' }).last()
  await timedDialog.getByLabel('任务标题').fill(timedTitle)
  await timedDialog.locator('input[aria-label="开始时间"]').fill('14:00')
  await timedDialog.locator('input[aria-label="结束时间"]').fill('15:00')
  await timedDialog.getByRole('button', { name: '创建任务', exact: true }).click()
  await expect(timedDialog).toBeHidden()
  await expect(page.locator('.calendar-task').filter({ hasText: timedTitle })).toContainText('14:00')
  await expect(page.locator('.calendar-task-timed').filter({ hasText: timedTitle })).toContainText('14:00–15:00')

  await page.getByRole('button', { name: '日', exact: true }).click()
  await expect(page.locator('.calendar-day-view')).toBeVisible()
  await expect(page.locator('.calendar-day-view .calendar-task-timed').filter({ hasText: timedTitle })).toBeVisible()
  await page.getByRole('button', { name: '月', exact: true }).click()
  await expect(page.locator('.calendar-month-view')).toBeVisible()
  await page.getByRole('button', { name: '周', exact: true }).click()

  const timedTask = page.locator('.calendar-task').filter({ hasText: timedTitle }).first()
  await timedTask.click()
  const editDialog = page.locator('.el-dialog').filter({ hasText: '编辑任务' }).last()
  await expect(editDialog).toBeVisible()
  await editDialog.getByRole('button', { name: '清除时间安排', exact: true }).click()
  await saveTaskEditor(editDialog)
  await expect(page.locator('.calendar-task').filter({ hasText: timedTitle })).toBeVisible()
  await expect(page.locator('.calendar-task').filter({ hasText: timedTitle })).not.toContainText('14:00')

  await page.reload()
  await expect(page.locator('.calendar-task').filter({ hasText: dateOnlyTitle })).toBeVisible()
  await expect(page.locator('.calendar-task').filter({ hasText: timedTitle })).toBeVisible()

  await page.goto('/#today')
  await expect(taskCard(page, dateOnlyTitle)).toBeVisible()
  await expect(taskCard(page, timedTitle)).toBeVisible()
})

test('时间冲突显示中文确认并支持显式覆盖', async ({ page, request }) => {
  const firstTitle = uniqueName('E2E-冲突-已有')
  const secondTitle = uniqueName('E2E-冲突-待改')
  const date = todayDate()

  await createTask(request, {
    title: firstTitle,
    planned_date: date,
    schedule: { start_time: '14:00', end_time: '15:00', timezone: 'Asia/Shanghai' },
  })
  await createTask(request, {
    title: secondTitle,
    planned_date: date,
    schedule: { start_time: '15:00', end_time: '16:00', timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#calendar')
  const secondTask = page.locator('.calendar-task').filter({ hasText: secondTitle }).first()
  await expect(secondTask).toBeVisible()
  await secondTask.click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '编辑任务' }).last()
  await dialog.locator('input[aria-label="开始时间"]').fill('14:30')
  await dialog.locator('input[aria-label="结束时间"]').fill('15:30')
  await dialog.getByRole('button', { name: '保存修改', exact: true }).click()

  const conflictBox = page.locator('.el-message-box').last()
  await expect(conflictBox).toContainText('该时间段与已有任务冲突，是否仍然保存？')
  await conflictBox.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeVisible()

  await dialog.getByRole('button', { name: '保存修改', exact: true }).click()
  const secondConflictBox = page.locator('.el-message-box').last()
  await secondConflictBox.getByRole('button', { name: '仍然保存', exact: true }).click()
  await expect(dialog).toBeHidden()
})

test('Calendar API 失败时显示错误和重试而不是正常空状态', async ({ page }) => {
  await page.route('**/api/v1/calendar*', (route) => route.abort('failed'))
  await page.goto('/#calendar')

  const errorState = page.locator('.calendar-state.is-error')
  await expect(errorState).toBeVisible()
  await expect(errorState).toContainText('日历加载失败')
  await expect(errorState.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  await expect(page.getByText('这个时间范围还没有任务', { exact: true })).toHaveCount(0)

  await page.unroute('**/api/v1/calendar*')
  await errorState.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.locator('.calendar-content')).toBeVisible()
})
