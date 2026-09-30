import { expect, test } from '@playwright/test'

import {
  chooseInboxFilter,
  createCategory,
  createTag,
  createTask,
  taskCard,
  uniqueName,
} from '../helpers/api'

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
  await expect(page.getByText('暂无匹配任务', { exact: true })).toBeVisible()
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
