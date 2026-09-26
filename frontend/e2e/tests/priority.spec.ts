import { expect, test } from '@playwright/test'

import {
  chooseTaskPriority,
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  uniqueName,
} from '../helpers/api'

test('优先级低、普通、高可以编辑并在刷新后保持', async ({ page }) => {
  const title = uniqueName('E2E-优先级')

  await page.goto('/#today')
  await page.getByLabel('新任务标题').fill(title)
  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  await expect(taskCard(page, title)).toBeVisible()

  for (const label of ['低', '普通', '高']) {
    const dialog = await openTaskEditor(page, title)
    await chooseTaskPriority(page, dialog, label)
    await saveTaskEditor(dialog)
    await expect(taskCard(page, title).getByText(label, { exact: true })).toBeVisible()
  }

  await page.reload()
  await expect(taskCard(page, title).getByText('高', { exact: true })).toBeVisible()
})
