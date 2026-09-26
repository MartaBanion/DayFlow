import { expect, test } from '@playwright/test'

import {
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  uniqueName,
} from '../helpers/api'

test('今天页面支持任务完整生命周期和刷新持久化', async ({ page }) => {
  const originalTitle = uniqueName('E2E-今天')
  const editedTitle = `${originalTitle}-已编辑`

  await page.goto('/#today')
  await expect(page.getByRole('link', { name: /今天/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: '今日任务', exact: true })).toBeVisible()

  await page.getByLabel('新任务标题').fill(originalTitle)
  await page.getByLabel('新任务备注').fill('浏览器验收备注')
  await page.getByRole('button', { name: '添加任务', exact: true }).click()
  await expect(taskCard(page, originalTitle)).toBeVisible()

  const editDialog = await openTaskEditor(page, originalTitle)
  await editDialog.getByLabel('任务标题').fill(editedTitle)
  await editDialog.getByLabel('备注').fill('更新后的备注')
  await saveTaskEditor(editDialog)
  await expect(taskCard(page, editedTitle)).toBeVisible()

  let card = taskCard(page, editedTitle)
  await card.getByRole('button', { name: `完成任务：${editedTitle}` }).click()
  await expect(card.getByText('已完成', { exact: true })).toBeVisible()

  await card.getByRole('button', { name: `恢复任务：${editedTitle}` }).click()
  await expect(card.getByText('已完成', { exact: true })).toHaveCount(0)

  await card.getByRole('button', { name: '删除', exact: true }).click()
  const messageBox = page.locator('.el-message-box').last()
  await expect(messageBox).toContainText('点击“撤销”恢复')
  await messageBox.getByRole('button', { name: '删除', exact: true }).click()
  await expect(taskCard(page, editedTitle)).toHaveCount(0)

  await page.locator('.delete-undo').getByText('撤销', { exact: true }).click()
  await expect(taskCard(page, editedTitle)).toBeVisible()

  await page.reload()
  await expect(taskCard(page, editedTitle)).toBeVisible()
})
