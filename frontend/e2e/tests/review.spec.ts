import { expect, test } from '@playwright/test'

import { createProject, createTask, todayDate, uniqueName } from '../helpers/api'

function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00+08:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

test('Review navigation shows Today, Week, completed, overdue, and carryover facts', async ({ page, request }) => {
  const today = todayDate()
  const yesterday = shiftDate(today, -1)
  const completedTitle = uniqueName('E2E-回顾已完成')
  const attentionTitle = uniqueName('E2E-回顾逾期遗留')

  const completed = await createTask(request, { title: completedTitle, planned_date: today })
  const completeResponse = await request.post(`/api/v1/tasks/${completed.id}/complete`, { data: { version: completed.version } })
  expect(completeResponse.ok()).toBeTruthy()
  await createTask(request, {
    title: attentionTitle,
    planned_date: yesterday,
    deadline: { date: yesterday, timezone: 'Asia/Shanghai' },
  })

  await page.goto('/#review')
  await expect(page.getByRole('link', { name: '回顾', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('heading', { name: '日常回顾', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: `打开任务：${completedTitle}` })).toBeVisible()
  await expect(page.getByRole('button', { name: `打开任务：${attentionTitle}` })).toHaveCount(2)
  await expect(page.getByRole('heading', { name: '逾期任务', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '遗留任务', exact: true })).toBeVisible()

  await page.getByRole('button', { name: '本周', exact: true }).click()
  await expect(page.getByRole('button', { name: '本周', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('本周完成的任务', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: `打开任务：${completedTitle}` })).toBeVisible()
})

test('Review task navigation uses the existing editor and refreshes after save', async ({ page, request }) => {
  const title = uniqueName('E2E-回顾编辑')
  const editedTitle = `${title}-已更新`
  const task = await createTask(request, { title, planned_date: shiftDate(todayDate(), -1) })

  await page.goto('/#review')
  const reviewTask = page.getByRole('button', { name: `打开任务：${title}` }).first()
  await expect(reviewTask).toBeVisible()
  await reviewTask.click()

  const dialog = page.locator('.el-dialog').filter({ hasText: '编辑任务' }).last()
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('任务标题').fill(editedTitle)
  await dialog.getByRole('button', { name: '保存任务', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('button', { name: `打开任务：${editedTitle}`, exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: `打开任务：${title}`, exact: true })).toHaveCount(0)
  expect(task.version).toBe(1)
})

test('Review project navigation enters the existing Project Detail view', async ({ page, request }) => {
  const projectName = uniqueName('E2E-回顾项目')
  const project = await createProject(request, projectName)
  await createTask(request, {
    title: uniqueName('E2E-回顾项目任务'),
    project_id: project.id,
    planned_date: todayDate(),
  })

  await page.goto('/#review')
  await page.getByRole('button', { name: `打开项目：${projectName}` }).click()
  await expect(page).toHaveURL(/#project:/)
  await expect(page.getByRole('heading', { name: projectName, exact: true })).toBeVisible()
})

test('Review error provides retry and recovers without exposing implementation details', async ({ page }) => {
  let calls = 0
  await page.route('**/api/v1/review*scope=today*', async (route) => {
    calls += 1
    if (calls === 1) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'service_unavailable', message: 'temporary' } }),
      })
      return
    }
    await route.continue()
  })

  await page.goto('/#review')
  await expect(page.getByRole('heading', { name: '回顾加载失败', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('temporary')
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByRole('heading', { name: '今天完成的任务', exact: true })).toBeVisible()
  expect(calls).toBe(2)
})

test('Review empty state and desktop viewport layouts remain usable', async ({ page }) => {
  const emptyResponse = JSON.stringify({
    scope: 'today',
    local_timezone: 'Asia/Shanghai',
    local_date: todayDate(),
    range_start_utc: '2026-01-01T00:00:00.000000Z',
    range_end_utc: '2026-01-02T00:00:00.000000Z',
    generated_at_utc: '2026-01-01T12:00:00.000000Z',
    completed: { count: 0, tasks: [] },
    overdue: { count: 0, tasks: [] },
    carryover: { count: 0, tasks: [] },
    projects: [],
  })
  await page.route('**/api/v1/review*scope=today*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: emptyResponse,
  }))

  await page.goto('/#review')
  await expect(page.getByText('今天还没有完成的任务', { exact: true })).toBeVisible()
  await expect(page.getByText('目前没有逾期任务', { exact: true })).toBeVisible()
  await expect(page.getByText('没有需要处理的遗留任务', { exact: true })).toBeVisible()
  await expect(page.getByText('暂无项目', { exact: true })).toBeVisible()

  for (const width of [1440, 1024, 900]) {
    await page.setViewportSize({ width, height: 700 })
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scrollWidth, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(dimensions.clientWidth)
  }
})
