import { expect, test } from '@playwright/test'

import {
  chooseTaskCategory,
  chooseTaskTags,
  clearTaskSelect,
  closeDialog,
  confirmDelete,
  openMetadataManager,
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  uniqueName,
} from '../helpers/api'

test('分类和标签支持创建、重命名、分配、清除和删除', async ({ page, request }) => {
  const categoryName = uniqueName('E2E-分类')
  const renamedCategory = `${categoryName}-新名称`
  const tagA = uniqueName('E2E-标签A')
  const renamedTagA = `${tagA}-新名称`
  const tagB = uniqueName('E2E-标签B')
  const title = uniqueName('E2E-组织任务')

  await page.goto('/#today')
  const metadata = await openMetadataManager(page)

  await metadata.getByLabel('新分类名称').fill(categoryName)
  await metadata.getByRole('button', { name: '新建分类', exact: true }).click()
  await expect(metadata.getByText(categoryName, { exact: true })).toBeVisible()

  await metadata.getByLabel('新分类名称').fill(categoryName)
  await metadata.getByRole('button', { name: '新建分类', exact: true }).click()
  await expect(metadata.locator('.metadata-alert')).toContainText('分类名称已存在')

  await metadata.getByLabel('新分类名称').fill('')
  await metadata.getByRole('button', { name: '新建分类', exact: true }).click()
  await expect(metadata.locator('.metadata-alert')).toContainText('分类名称不能为空')

  const categoryRow = metadata.locator('.metadata-row').filter({ hasText: categoryName })
  await categoryRow.getByRole('button', { name: '重命名', exact: true }).click()
  await metadata.getByLabel(`重命名分类：${categoryName}`).fill(renamedCategory)
  await metadata.getByRole('button', { name: '保存', exact: true }).click()
  await expect(metadata.getByText(renamedCategory, { exact: true })).toBeVisible()

  await metadata.getByLabel('新标签名称').fill(tagA)
  await metadata.getByRole('button', { name: '新建标签', exact: true }).click()
  await expect(metadata.getByText(tagA, { exact: true })).toBeVisible()
  await metadata.getByLabel('新标签名称').fill(tagB)
  await metadata.getByRole('button', { name: '新建标签', exact: true }).click()
  await expect(metadata.getByText(tagB, { exact: true })).toBeVisible()

  await metadata.getByLabel('新标签名称').fill(tagA)
  await metadata.getByRole('button', { name: '新建标签', exact: true }).click()
  await expect(metadata.locator('.metadata-alert')).toContainText('标签名称已存在')

  const tagRow = metadata.locator('.metadata-row').filter({ hasText: tagA })
  await tagRow.getByRole('button', { name: '重命名', exact: true }).click()
  await metadata.getByLabel(`重命名标签：${tagA}`).fill(renamedTagA)
  await metadata.getByRole('button', { name: '保存', exact: true }).click()
  await expect(metadata.getByText(renamedTagA, { exact: true })).toBeVisible()
  await closeDialog(metadata)

  await page.getByLabel('新任务标题').fill(title)
  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  await expect(taskCard(page, title)).toBeVisible()

  let dialog = await openTaskEditor(page, title)
  await chooseTaskCategory(page, dialog, renamedCategory)
  await chooseTaskTags(page, dialog, [renamedTagA, tagB])
  await saveTaskEditor(dialog)
  let card = taskCard(page, title)
  await expect(card.getByText(renamedCategory, { exact: true })).toBeVisible()
  await expect(card.getByText(renamedTagA, { exact: true })).toBeVisible()
  await expect(card.getByText(tagB, { exact: true })).toBeVisible()

  dialog = await openTaskEditor(page, title)
  await clearTaskSelect(dialog, '分类')
  await clearTaskSelect(dialog, '标签')
  await saveTaskEditor(dialog)
  card = taskCard(page, title)
  await expect(card.getByText(renamedCategory, { exact: true })).toHaveCount(0)
  await expect(card.getByText(renamedTagA, { exact: true })).toHaveCount(0)
  await expect(card.getByText(tagB, { exact: true })).toHaveCount(0)

  dialog = await openTaskEditor(page, title)
  await chooseTaskCategory(page, dialog, renamedCategory)
  await chooseTaskTags(page, dialog, [renamedTagA, tagB])
  await saveTaskEditor(dialog)

  const metadataForDelete = await openMetadataManager(page)
  const categoryDeleteRow = metadataForDelete.locator('.metadata-row').filter({ hasText: renamedCategory })
  await categoryDeleteRow.getByRole('button', { name: '删除', exact: true }).click()
  await confirmDelete(page)
  await expect(metadataForDelete.getByText(renamedCategory, { exact: true })).toHaveCount(0)

  const tagDeleteRowA = metadataForDelete.locator('.metadata-row').filter({ hasText: renamedTagA })
  await tagDeleteRowA.getByRole('button', { name: '删除', exact: true }).click()
  await confirmDelete(page)
  const tagDeleteRowB = metadataForDelete.locator('.metadata-row').filter({ hasText: tagB })
  await tagDeleteRowB.getByRole('button', { name: '删除', exact: true }).click()
  await confirmDelete(page)
  await closeDialog(metadataForDelete)

  await expect(taskCard(page, title)).toBeVisible()
  await expect(taskCard(page, title).getByText(renamedCategory, { exact: true })).toHaveCount(0)
  await expect(taskCard(page, title).getByText(renamedTagA, { exact: true })).toHaveCount(0)
  await expect(taskCard(page, title).getByText(tagB, { exact: true })).toHaveCount(0)

  // Ensure the task was a real persisted task rather than only a visual fixture.
  const response = await request.get('/api/v1/tasks')
  expect(response.ok()).toBeTruthy()
  const tasks = (await response.json()) as Array<{ title: string }>
  expect(tasks.some((task) => task.title === title)).toBe(true)
})

test('搜索失败时不显示正常空结果', async ({ page }) => {
  const responseError = '搜索服务暂不可用'
  await page.route('**/api/v1/tasks*', async (route) => {
    if (route.request().url().includes('q=')) {
      await route.abort('failed')
      return
    }
    await route.continue()
  })

  await page.goto('/#inbox')
  await page.getByLabel('搜索任务').fill(responseError)
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.locator('.today-state.is-error')).toBeVisible()
  await expect(page.locator('.today-state.is-error')).toContainText('收件箱操作失败')
  await expect(page.getByText('没有找到相关任务', { exact: true })).toHaveCount(0)
})
