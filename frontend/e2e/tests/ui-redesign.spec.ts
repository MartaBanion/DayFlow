import { expect, test } from '@playwright/test'

import { createCategory, createProject, createTag, createTask, openTaskEditor, taskCard, uniqueName } from '../helpers/api'
import type { Task } from '../../src/types'

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 900, height: 700 }]) {
  test(`任务工作台视觉与交互 ${viewport.width}×${viewport.height}`, async ({ page, request }, testInfo) => {
    test.setTimeout(120_000)
    await page.setViewportSize(viewport)
    const runtime = await (await request.get('/api/v1/runtime')).json() as { local_date: string }
    const project = await createProject(request, uniqueName('学习与实践：长期个人知识体系和开发项目'), '用明确的小任务推进项目，保留完整历史。')
    const category = await createCategory(request, uniqueName('学习'))
    const tags = await Promise.all(['阅读', '实践', '记录', '复习', '计划'].map((name) => createTag(request, uniqueName(name))))
    const task = await createTask(request, {
      title: uniqueName('整理学习笔记：梳理本周重点并完成一轮实践，检查较长标题的可读性'),
      description: '把复杂任务拆成可以完成的步骤。'.repeat(18),
      planned_date: runtime.local_date, priority: 'high', project_id: project.id,
      category_id: category.id, tag_ids: tags.map((tag) => tag.id),
      deadline: { date: runtime.local_date, timezone: 'Asia/Shanghai' },
    })
    const repeating = await createTask(request, { title: uniqueName('每日阅读与回顾'), planned_date: runtime.local_date })
    const rule = await request.post(`/api/v1/tasks/${repeating.id}/recurrence`, { data: { version: repeating.version, frequency: 'daily', starts_on: runtime.local_date, timezone: 'Asia/Shanghai' } })
    expect(rule.ok(), await rule.text()).toBeTruthy()
    const reminder = await request.post(`/api/v1/tasks/${repeating.id}/reminders`, { data: { date: '2099-01-01', time: '09:00', timezone: 'Asia/Shanghai' } })
    expect(reminder.ok(), await reminder.text()).toBeTruthy()
    const inbox = await createTask(request, { title: uniqueName('先记下一个想法'), project_id: project.id })
    await createTask(request, { title: uniqueName('检查逾期状态'), planned_date: runtime.local_date, deadline: { date: '2020-01-01', timezone: 'Asia/Shanghai' } })
    const completed = await createTask(request, { title: uniqueName('已经完成的阶段总结'), planned_date: runtime.local_date, project_id: project.id })
    expect((await request.post(`/api/v1/tasks/${completed.id}/complete`, { data: { version: completed.version } })).ok()).toBeTruthy()
    const blocks: Task[] = []
    for (const [title, start, end] of [['专注学习', '10:00', '11:30'], ['重叠任务', '10:30', '11:00'], ['短时间回顾', '10:45', '11:00']]) {
      const response = await request.post('/api/v1/tasks?allow_schedule_conflict=true', { data: {
        title: uniqueName(title!), planned_date: runtime.local_date,
        schedule: { start_time: start, end_time: end, timezone: 'Asia/Shanghai' },
      } })
      expect(response.ok(), await response.text()).toBeTruthy()
      blocks.push(await response.json() as Task)
    }
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    const capture = async (name: string) => {
      if (!testInfo.config.rootDir.startsWith('/tmp/dayflow-ui-baseline-')) {
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      }
      await page.evaluate(async () => { await document.fonts.ready; (document.activeElement as HTMLElement | null)?.blur() })
      const filename = `${name}-${viewport.width}x${viewport.height}.png`
      await page.screenshot({ path: testInfo.outputPath(filename), animations: 'disabled' })
    }
    for (const view of ['today', 'inbox', 'search', 'projects', `project:${project.id}`, 'calendar']) {
      await page.goto(`/#${view}`)
      if (view === 'today') await expect(taskCard(page, task.title)).toBeVisible()
      if (view === 'inbox') await expect(taskCard(page, inbox.title)).toBeVisible()
      if (view === 'search') {
        await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill(task.title)
        await page.getByRole('button', { name: '搜索', exact: true }).click()
        await expect(taskCard(page, task.title)).toBeVisible()
      }
      if (view.startsWith('project')) await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible()
      if (view === 'calendar') await expect(page.getByRole('region', { name: '周视图', exact: true })).toBeVisible()
      await capture(view.startsWith('project:') ? 'project-detail' : view === 'calendar' ? 'calendar-week' : view)
    }
    for (const mode of ['日', '月']) {
      await page.getByRole('button', { name: mode, exact: true }).click()
      await expect(page.getByRole('region', { name: `${mode}视图`, exact: true })).toBeVisible()
      await capture(mode === '日' ? 'calendar-day' : 'calendar-month')
    }
    if (!testInfo.config.rootDir.startsWith('/tmp/dayflow-ui-baseline-')) {
      await page.getByRole('button', { name: '日', exact: true }).click()
      const buttons = blocks.map((block) => page.getByRole('button', { name: `${block.title} · ${block.title.includes('专注') ? '10:00–11:30' : block.title.includes('重叠') ? '10:30–11:00' : '10:45–11:00'}`, exact: true }))
      const bounds = await Promise.all(buttons.map((button) => button.boundingBox()))
      expect(bounds.every(Boolean)).toBe(true)
      expect(bounds[0]!.x + bounds[0]!.width).toBeLessThanOrEqual(bounds[1]!.x)
      expect(bounds[1]!.x + bounds[1]!.width).toBeLessThanOrEqual(bounds[2]!.x)
      expect(bounds[2]!.height).toBeLessThan(bounds[1]!.height)
      await expect(buttons[2]!).toHaveCSS('flex-direction', 'row')
      await buttons[2]!.focus()
      const tooltip = page.getByRole('tooltip').filter({ hasText: blocks[2]!.title })
      await expect(tooltip).toContainText('10:45–11:00')
      await page.keyboard.press('Escape')
      await buttons[2]!.blur()
      await expect(page.getByRole('region', { name: '日视图' }).locator('.calendar-time-scroll')).toHaveCSS('overflow-y', 'auto')
    }
    await page.goto('/#today')
    const dialog = await openTaskEditor(page, task.title)
    for (const [group, name] of [['基础信息', 'editor-basic'], ['日期与时间', 'editor-dates'], ['项目与分类', 'editor-organization'], ['重复与提醒', 'editor-features']]) {
      await dialog.locator('details').evaluateAll((elements, selected) => elements.forEach((element) => {
        (element as HTMLDetailsElement).open = element.querySelector('summary')?.textContent?.includes(selected as string) ?? false
      }), group)
      await dialog.locator('.el-dialog__body').evaluate((element) => { element.scrollTop = 0 })
      await expect(dialog.getByRole('button', { name: '保存任务', exact: true })).toBeInViewport()
      await capture(name!)
      if (group === '日期与时间') {
        await dialog.getByLabel('计划日期', { exact: true }).click()
        const picker = page.locator('.el-picker-panel:visible').last()
        await expect(picker).toBeInViewport()
        await page.keyboard.press('Escape')
        await expect(picker).toBeHidden()
      }
    }
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    const featureDialog = await openTaskEditor(page, repeating.title)
    await expect(featureDialog.getByRole('button', { name: '保存规则', exact: true })).toBeVisible()
    await featureDialog.locator('details').evaluateAll((elements) => elements.forEach((element) => {
      (element as HTMLDetailsElement).open = element.querySelector('summary')?.textContent?.includes('重复与提醒') ?? false
    }))
    await capture('editor-repeat-reminder')
    await featureDialog.getByRole('button', { name: '取消', exact: true }).click()
    await page.route(/\/api\/v1\/tasks(?:\?.*)?$/, (route) => route.fulfill({ json: [] }))
    await page.goto('/#search')
    await expect(page.getByText('暂无匹配任务').or(page.getByText('还没有可搜索的任务'))).toBeVisible()
    await capture('search-empty')
    await page.unroute(/\/api\/v1\/tasks(?:\?.*)?$/)
    await page.route('**/api/v1/calendar?*', (route) => route.fulfill({ status: 503, json: { detail: '临时网络错误' } }))
    await page.goto('/#calendar')
    await expect(page.getByText('日历加载失败', { exact: true })).toBeVisible()
    await capture('calendar-error')
    await page.unroute('**/api/v1/calendar?*')
    await page.getByRole('button', { name: '重试', exact: true }).click()
    await expect(page.getByRole('region', { name: '周视图', exact: true })).toBeVisible()
    let releaseLoading!: () => void
    const loading = new Promise<void>((resolve) => { releaseLoading = resolve })
    await page.route('**/api/v1/calendar?*', async (route) => { await loading; await route.continue() })
    await page.reload()
    await expect(page.getByText('正在加载日历', { exact: true })).toBeVisible()
    await capture('calendar-loading')
    releaseLoading()
    await expect(page.getByRole('region', { name: '周视图', exact: true })).toBeVisible()
    await page.unroute('**/api/v1/calendar?*')
    expect(errors).toEqual([])
  })
}
