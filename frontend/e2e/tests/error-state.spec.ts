import { expect, test } from '@playwright/test'

test('Today API 失败时显示中文错误和重试而不是空数据', async ({ page }) => {
  await page.route('**/api/v1/today*', (route) => route.abort('failed'))
  await page.goto('/#today')

  const errorState = page.locator('.today-state.is-error')
  await expect(errorState).toBeVisible()
  await expect(errorState).toContainText('今日任务加载失败')
  await expect(errorState.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  await expect(page.locator('.summary-grid')).toHaveCount(0)
  await expect(page.getByText('今天还没有安排任务', { exact: true })).toHaveCount(0)

  await page.unroute('**/api/v1/today*')
  await errorState.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.locator('.summary-grid')).toBeVisible()
})
