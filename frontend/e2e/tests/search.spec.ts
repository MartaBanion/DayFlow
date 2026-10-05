import { expect, test } from '@playwright/test'

import {
  chooseInboxFilter,
  createCategory,
  createTag,
  createTask,
  chooseTodayDate,
  taskCard,
  openTaskEditor,
  saveTaskEditor,
  todayDate,
  uniqueName,
} from '../helpers/api'

function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00+08:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

test('搜索支持标题、备注和结构化筛选', async ({ page, request }) => {
  const title = uniqueName('E2E-搜索标题')
  const description = uniqueName('E2E-搜索备注')
  const category = await createCategory(request, uniqueName('E2E-搜索分类'))
  const tag = await createTag(request, uniqueName('E2E-搜索标签'))
  await createTask(request, {
    title,
    description,
    planned_date: null,
    priority: 'high',
    category_id: category.id,
    tag_ids: [tag.id],
  })
  await createTask(request, {
    title: uniqueName('E2E-其他任务'),
    description: '不应出现在目标搜索中',
    planned_date: null,
  })

  await page.goto('/#inbox')
  const query = page.getByLabel('搜索任务')
  const searchButton = page.getByRole('button', { name: '搜索', exact: true })

  await query.fill(title)
  await searchButton.click()
  await expect(taskCard(page, title)).toBeVisible()

  await query.fill(description)
  await searchButton.click()
  await expect(taskCard(page, title)).toBeVisible()

  await query.fill(title)
  await searchButton.click()
  await chooseInboxFilter(page, 0, '高')
  await expect(taskCard(page, title)).toBeVisible()

  await chooseInboxFilter(page, 1, category.name)
  await expect(taskCard(page, title)).toBeVisible()

  await chooseInboxFilter(page, 2, tag.name)
  await expect(taskCard(page, title)).toBeVisible()

  await query.fill(uniqueName('E2E-没有结果'))
  await searchButton.click()
  await expect(page.getByText('当前收件箱中没有匹配任务', { exact: true })).toBeVisible()
})

test('Inbox 查询保持 Inbox 范围并可清除回普通列表', async ({ page, request }) => {
  const query = uniqueName('V10-Inbox范围')
  const inboxTitle = `${query}-Inbox`
  const plannedTitle = `${query}-Today`
  const completedTitle = `${query}-Completed`

  await createTask(request, { title: inboxTitle })
  await createTask(request, { title: plannedTitle, planned_date: todayDate() })
  const completed = await createTask(request, { title: completedTitle })
  const completeResponse = await request.post(`/api/v1/tasks/${completed.id}/complete`, {
    data: { version: completed.version },
  })
  expect(completeResponse.ok(), await completeResponse.text()).toBeTruthy()

  await page.goto('/#inbox')
  const queryInput = page.getByLabel('搜索任务')
  await queryInput.fill(query)
  await page.getByRole('button', { name: '搜索', exact: true }).click()

  await expect(taskCard(page, inboxTitle)).toBeVisible()
  await expect(taskCard(page, plannedTitle)).toHaveCount(0)
  await expect(taskCard(page, completedTitle)).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '收件箱', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '待安排任务', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '搜索结果', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: '清除筛选', exact: true }).click()
  await expect(taskCard(page, inboxTitle)).toBeVisible()
  await expect(taskCard(page, plannedTitle)).toHaveCount(0)
  await expect(taskCard(page, completedTitle)).toHaveCount(0)
})

test('中文核心导航和空结果界面可见', async ({ page }) => {
  await page.goto('/#today')
  await expect(page.getByRole('link', { name: /今天/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /收件箱/ })).toBeVisible()
  await expect(page.getByText('任务', { exact: true })).toBeVisible()
  await expect(page.getByText('完成率', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: /收件箱/ }).click()
  await expect(page.getByRole('heading', { name: '收件箱', exact: true })).toBeVisible()
  await expect(page.getByText('暂时还没安排日期的任务，可以先放在这里。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('搜索任务')).toBeVisible()
  await expect(page.getByRole('button', { name: '搜索', exact: true })).toBeVisible()
  await expect(page.getByText('优先级', { exact: true })).toBeVisible()
  await expect(page.getByText('分类', { exact: true })).toBeVisible()
  await expect(page.getByText('标签', { exact: true })).toBeVisible()
})

test('Search 使用状态、计划、逾期和排序筛选，并在编辑后刷新结果', async ({ page, request }) => {
  const today = todayDate()
  const yesterday = shiftDate(today, -1)
  const pastTitle = uniqueName('E2E-搜索过去计划')
  const overdueTitle = uniqueName('E2E-搜索逾期')
  const futureTitle = uniqueName('E2E-搜索未来计划')
  const olderCompletedTitle = uniqueName('E2E-搜索较早完成')
  const recentCompletedTitle = uniqueName('E2E-搜索最近完成')

  await createTask(request, { title: pastTitle, planned_date: yesterday })
  await createTask(request, {
    title: overdueTitle,
    planned_date: yesterday,
    deadline: { date: yesterday, timezone: 'Asia/Shanghai' },
  })
  await createTask(request, { title: futureTitle, planned_date: shiftDate(today, 1) })
  const olderCompleted = await createTask(request, { title: olderCompletedTitle })
  const olderCompletedResponse = await request.post(`/api/v1/tasks/${olderCompleted.id}/complete`, {
    data: { version: olderCompleted.version },
  })
  expect(olderCompletedResponse.ok(), await olderCompletedResponse.text()).toBeTruthy()
  const recentCompleted = await createTask(request, { title: recentCompletedTitle })
  const recentCompletedResponse = await request.post(`/api/v1/tasks/${recentCompleted.id}/complete`, {
    data: { version: recentCompleted.version },
  })
  expect(recentCompletedResponse.ok(), await recentCompletedResponse.text()).toBeTruthy()

  await page.goto('/#search')
  await expect(page.getByRole('heading', { name: '搜索任务', exact: true })).toBeVisible()
  await expect(page.getByText('搜索所有未删除任务，可组合筛选。', { exact: true })).toBeVisible()

  await chooseInboxFilter(page, 4, '待完成')
  await expect(taskCard(page, pastTitle)).toBeVisible()
  await expect(taskCard(page, olderCompletedTitle)).toHaveCount(0)

  await chooseInboxFilter(page, 5, '过去')
  await expect(taskCard(page, pastTitle)).toBeVisible()
  await expect(taskCard(page, futureTitle)).toHaveCount(0)

  const editor = await openTaskEditor(page, pastTitle)
  await chooseTodayDate(page, editor)
  await saveTaskEditor(editor)
  await expect(taskCard(page, pastTitle)).toHaveCount(0)

  const clearSearch = page.locator('.search-panel .filter-toolbar').getByRole('button', { name: '清除筛选', exact: true })
  await clearSearch.click()
  await expect(taskCard(page, pastTitle)).toBeVisible()

  await chooseInboxFilter(page, 4, '待完成')
  await page.locator('#overdue-filter').check()
  await expect(taskCard(page, overdueTitle)).toBeVisible()
  await expect(taskCard(page, futureTitle)).toHaveCount(0)
  await expect(taskCard(page, pastTitle)).toHaveCount(0)

  await clearSearch.click()
  await chooseInboxFilter(page, 4, '已完成')
  await chooseInboxFilter(page, 6, '最近完成')
  await expect(taskCard(page, olderCompletedTitle)).toBeVisible()
  await expect(taskCard(page, recentCompletedTitle)).toBeVisible()
  const completedTitles = await page.locator('.task-list article.task-card h4').allTextContents()
  expect(completedTitles.indexOf(recentCompletedTitle)).toBeLessThan(completedTitles.indexOf(olderCompletedTitle))

  await clearSearch.click()
  await expect(taskCard(page, pastTitle)).toBeVisible()
  await expect(taskCard(page, olderCompletedTitle)).toBeVisible()
})

test('Search 错误可重试且 900px 筛选工具栏不横向溢出', async ({ page }) => {
  let calls = 0
  await page.route('**/api/v1/tasks*', async (route) => {
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

  await page.setViewportSize({ width: 900, height: 700 })
  await page.goto('/#search')
  await expect(page.getByRole('heading', { name: '搜索失败', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('temporary')

  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByRole('heading', { name: '搜索结果', exact: true })).toBeVisible()
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
  expect(calls).toBe(2)
})
