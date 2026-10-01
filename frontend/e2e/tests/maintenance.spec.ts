import { expect, test } from '@playwright/test'

test('数据与备份：创建、验证、刷新保持，无恢复执行入口', async ({ page }) => {
  await page.goto('/#today')
  await page.getByRole('link', { name: '数据与备份', exact: true }).click()
  const main = page.getByRole('main')
  await expect(page.getByRole('link', { name: '数据与备份' })).toHaveAttribute('aria-current', 'page')
  await expect(main.getByText('还没有备份', { exact: true })).toBeVisible()
  await main.getByRole('button', { name: '创建备份', exact: true }).click()
  await expect(main.getByText('备份已创建', { exact: true })).toBeVisible()
  await expect(main.getByRole('article')).toHaveCount(1)
  await expect(main.getByRole('article').getByText('需要验证', { exact: true })).toBeVisible()
  await main.getByRole('button', { name: /^验证备份 / }).click()
  await expect(main.getByText('可用于当前版本恢复', { exact: true })).toBeVisible()
  await page.reload()
  await expect(main.getByRole('article')).toHaveCount(1)
  await expect(main.getByText('需要验证', { exact: true })).toBeVisible()
  await expect(main.getByRole('button', { name: /恢复/ })).toHaveCount(0)
  await expect(main.getByText(/当前版本仅支持创建和验证备份/)).toBeVisible()
})

test('数据与备份双尺寸及窄桌面状态截图', async ({ page, request }, testInfo) => {
  const listed = await request.get('/api/v1/backups')
  expect(listed.ok()).toBeTruthy()
  if (!(await listed.json()).length) {
    const created = await request.post('/api/v1/backups')
    expect(created.ok()).toBeTruthy()
  }
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 900, height: 700 }]) {
    await page.setViewportSize(viewport)
    for (const state of ['empty', 'backup', 'verified', 'error']) {
      await page.unroute('**/api/v1/backups')
      if (state === 'empty') await page.route('**/api/v1/backups', route => route.fulfill({ json: [] }))
      if (state === 'error') await page.route('**/api/v1/backups', route => route.fulfill({ status: 503, json: { error: { code: 'backup_timeout', message: 'busy' } } }))
      await page.goto('/#maintenance')
      await page.reload()
      const main = page.getByRole('main')
      if (state === 'empty') await expect(main.getByText('还没有备份')).toBeVisible()
      if (state === 'error') await expect(main.getByRole('button', { name: '重试备份列表' })).toBeVisible()
      if (state === 'backup' || state === 'verified') await expect(main.getByRole('article').first()).toBeVisible()
      if (state === 'verified') {
        await main.getByRole('button', { name: /^验证备份 / }).first().click()
        await expect(main.getByText('可用于当前版本恢复', { exact: true })).toBeVisible()
      }
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await page.evaluate(async () => {
        await document.fonts.ready
        ;(document.activeElement as HTMLElement | null)?.blur()
        window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
      })
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
      await page.screenshot({ path: testInfo.outputPath(`maintenance-${state}-${viewport.width}x${viewport.height}.png`), fullPage: true })
    }
  }
})
