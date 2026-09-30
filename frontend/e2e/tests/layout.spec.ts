import { expect, test } from '@playwright/test'

import { createProject, createTask, uniqueName } from '../helpers/api'

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
  test(`应用外壳在 ${viewport.width}×${viewport.height} 下无整页横向溢出`, async ({ page, request }, testInfo) => {
    await page.setViewportSize(viewport)
    const runtimeResponse = await request.get('/api/v1/runtime')
    expect(runtimeResponse.ok()).toBeTruthy()
    const runtime = await runtimeResponse.json() as { local_date: string }
    const project = await createProject(request, uniqueName('布局验收项目'))
    const todayTask = await createTask(request, {
      title: uniqueName('今日布局验收任务'),
      planned_date: runtime.local_date,
      project_id: project.id,
    })
    const inboxTask = await createTask(request, { title: uniqueName('收件箱布局验收任务') })

    for (const view of ['today', 'inbox', 'search', 'projects', 'calendar']) {
      await page.goto(`/#${view}`)
      const main = page.getByRole('main')
      if (view === 'today') await expect(main.getByRole('heading', { name: todayTask.title })).toBeVisible()
      if (view === 'inbox') await expect(main.getByRole('heading', { name: inboxTask.title })).toBeVisible()
      if (view === 'search') {
        await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill(todayTask.title)
        await main.getByRole('button', { name: '搜索', exact: true }).click()
        await expect(main.getByRole('heading', { name: todayTask.title })).toBeVisible()
      }
      if (view === 'projects') await expect(main.getByRole('heading', { name: project.name })).toBeVisible()
      if (view === 'calendar') {
        await expect(main.getByRole('region', { name: '周视图', exact: true })).toBeVisible()
        await expect(main.getByRole('button').filter({ hasText: todayTask.title })).toBeVisible()
      }

      const navigation = page.getByRole('navigation', { name: '主要导航' })
      const current = navigation.locator('[aria-current="page"]')
      await expect(current).toHaveCount(1)
      await expect(current).toHaveAttribute('href', `#${view}`)
      await page.keyboard.press('Tab')
      await current.focus()
      await expect(current).toBeFocused()
      await expect(current).toHaveCSS('outline-style', 'solid')
      await expect(current).toHaveCSS('outline-width', '2px')

      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await expect(page.locator('.sidebar')).toHaveCSS('width', viewport.width === 1440 ? '220px' : '192px')
      await expect(main).toHaveCSS('padding-left', viewport.width === 1440 ? '32px' : '20px')
      const contentBounds = await page.locator('.workspace-content').boundingBox()
      expect(contentBounds).not.toBeNull()
      expect(contentBounds!.x + contentBounds!.width).toBeLessThanOrEqual(viewport.width)

      if (view === 'calendar' && viewport.width === 1024) {
        const calendar = page.locator('.calendar-content')
        expect(await calendar.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
        await expect(calendar).toHaveCSS('overflow-x', 'auto')
      }
      await page.evaluate(async () => {
        await document.fonts.ready
        ;(document.activeElement as HTMLElement | null)?.blur()
        window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
      })
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
      await page.screenshot({ path: testInfo.outputPath(`${view}-${viewport.width}x${viewport.height}.png`) })
    }
  })
}
