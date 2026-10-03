import { expect, test } from '@playwright/test'

const reminder = {
  id: 'reminder-poll-1',
  task_id: 'reminder-task',
  trigger_at_utc: '2026-09-29T08:00:00Z',
  reminder_timezone: 'Asia/Shanghai',
  status: 'pending',
  acknowledged_at_utc: null,
  dismissed_at_utc: null,
  created_at_utc: '2026-09-29T00:00:00Z',
  updated_at_utc: '2026-09-29T00:00:00Z',
  version: 1,
}

test('提醒轮询失败时显示可见错误，并可通过重试恢复', async ({ page }) => {
  await page.route('**/api/v1/reminders/due', (route) => route.abort('failed'))
  await page.goto('/#today')

  const error = page.locator('.reminder-poll-error')
  await expect(error).toBeVisible()
  await expect(error).toContainText('提醒查询失败')
  await expect(error).toContainText('部分提醒可能暂时无法更新')

  await page.unroute('**/api/v1/reminders/due')
  await error.getByRole('button', { name: '重试提醒查询', exact: true }).click()
  await expect(error).toBeHidden()
})

test('轮询失败时保留已有提醒，并在后续自动轮询成功后清除错误', async ({ page }) => {
  await page.clock.install()
  let dueCalls = 0
  await page.route('**/api/v1/reminders/due', async (route) => {
    dueCalls += 1
    if (dueCalls === 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([reminder]),
      })
      return
    }
    if (dueCalls === 2) {
      await route.abort('failed')
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  })
  await page.route('**/api/v1/tasks/reminder-task', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ id: 'reminder-task', title: '轮询保留测试' }),
  }))
  await page.route('**/api/v1/reminders/reminder-poll-1/dismiss', (route) => route.abort('failed'))

  await page.goto('/#today')
  const summary = page.locator('.reminder-poll-summary')
  await expect(summary).toContainText('1 条')

  const messageBox = page.locator('.el-message-box').last()
  await expect(messageBox).toBeVisible()
  await messageBox.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(messageBox).toBeHidden()
  await expect(summary).toContainText('1 条')

  await page.clock.fastForward(45_000)
  const error = page.locator('.reminder-poll-error')
  await expect(error).toBeVisible()
  await expect(summary).toContainText('1 条')

  await page.clock.fastForward(45_000)
  await expect(error).toBeHidden()
  await expect(summary).toHaveCount(0)
  expect(dueCalls).toBeGreaterThanOrEqual(3)
})
