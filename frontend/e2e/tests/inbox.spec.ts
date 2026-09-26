import { expect, test } from '@playwright/test'

import {
  chooseTodayDate,
  clearTaskDate,
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  uniqueName,
} from '../helpers/api'

test('收件箱任务可以安排日期、清空日期并完成', async ({ page }) => {
  const title = uniqueName('E2E-收件箱')

  await page.goto('/#inbox')
  await expect(
    page.locator('.page-header').getByRole('heading', { name: '未安排日期的任务', exact: true }),
  ).toBeVisible()
  await page.getByLabel('新收件箱任务标题').fill(title)
  await page.getByRole('button', { name: '记录', exact: true }).click()
  await expect(taskCard(page, title)).toBeVisible()

  let dialog = await openTaskEditor(page, title)
  await chooseTodayDate(page, dialog)
  await saveTaskEditor(dialog)
  await expect(taskCard(page, title)).toHaveCount(0)

  await page.goto('/#today')
  await expect(taskCard(page, title)).toBeVisible()
  dialog = await openTaskEditor(page, title)
  await clearTaskDate(dialog)
  await saveTaskEditor(dialog)

  await page.goto('/#inbox')
  await expect(taskCard(page, title)).toBeVisible()
  const card = taskCard(page, title)
  await card.getByRole('button', { name: `完成任务：${title}` }).click()
  await expect(taskCard(page, title)).toHaveCount(0)
})
