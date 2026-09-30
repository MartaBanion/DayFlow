import { expect, test, type Locator } from '@playwright/test'
import { createCategory, createProject, createTag, createTask, openTaskEditor, taskCard, todayDate, uniqueName } from '../helpers/api'

async function showGroup(dialog: Locator, name: string): Promise<void> {
  for (const group of ['基础信息', '日期与时间', '项目与分类', '重复与提醒']) {
    const summary = dialog.getByText(group, { exact: true })
    const opened = await summary.locator('..').getAttribute('open') !== null
    if (opened !== (group === name)) await summary.click()
  }
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
  test(`任务体验与草稿保存边界 ${viewport.width}×${viewport.height}`, async ({ page, request }, testInfo) => {
    await page.setViewportSize(viewport)
    const project = await createProject(request, uniqueName('学习计划'))
    const category = await createCategory(request, uniqueName('学习'))
    const tags = await Promise.all(['Linux', '网络', '实验', '复习'].map(name => createTag(request, uniqueName(name))))
    const title = uniqueName('整理学习笔记')
    const task = await createTask(request, { title, description: '记录重点与下一步行动。'.repeat(20), planned_date: todayDate(), project_id: project.id, category_id: category.id, tag_ids: tags.map(tag => tag.id), deadline: { date: '2099-01-01', time: '17:00', timezone: 'Asia/Shanghai' } })
    await createTask(request, { title: uniqueName('重要任务'), planned_date: todayDate(), priority: 'high', deadline: { date: '2000-01-01', timezone: 'Asia/Shanghai' } })
    await createTask(request, { title: uniqueName('今日到期'), planned_date: todayDate(), deadline: { date: todayDate(), timezone: 'Asia/Shanghai' } })
    const completed = await createTask(request, { title: uniqueName('已完成的练习'), planned_date: todayDate() })
    expect((await request.post(`/api/v1/tasks/${completed.id}/complete`, { data: { version: completed.version } })).ok()).toBeTruthy()
    await createTask(request, { title: uniqueName('稍后安排的想法') })
    await createTask(request, { title: uniqueName('专注学习'), planned_date: todayDate(), schedule: { start_time: viewport.width === 1440 ? '07:13' : '08:13', end_time: viewport.width === 1440 ? '07:43' : '08:43', timezone: 'Asia/Shanghai' } })

    for (const view of ['today', 'inbox', 'search']) {
      await page.goto(`/#${view}`)
      if (view === 'search') {
        await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill(title)
        await page.getByRole('main').getByRole('button', { name: '搜索', exact: true }).click()
      }
      await expect(page.locator('.task-card').first()).toBeVisible()
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ animations: 'disabled', path: testInfo.outputPath(`${view}-${viewport.width}x${viewport.height}.png`) })
    }
    await page.goto('/#today')
    const card = taskCard(page, title)
    await card.getByRole('button', { name: /更多操作/ }).press('Enter')
    await expect(page.getByRole('menuitem', { name: '删除', exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await card.getByRole('button', { name: /查看全部标签/ }).click()
    const allTags = page.getByRole('tooltip').filter({ hasText: '全部标签：' })
    await expect(allTags).toBeVisible()
    for (const tag of tags) await expect(allTags).toContainText(tag.name)
    await card.getByRole('button', { name: /查看全部标签/ }).click()
    const dialog = await openTaskEditor(page, title)
    const draft = uniqueName('尚未保存的标题')
    await dialog.getByRole('textbox', { name: '任务标题', exact: true }).fill(draft)
    await showGroup(dialog, '日期与时间')
    await showGroup(dialog, '基础信息')
    await expect(dialog.getByRole('textbox', { name: '任务标题', exact: true })).toHaveValue(draft)
    const basicSummary = dialog.getByText('基础信息', { exact: true })
    await basicSummary.press('Enter')
    await expect(dialog.getByRole('textbox', { name: '任务标题', exact: true })).toBeHidden()
    await basicSummary.press('Enter')
    await expect(dialog.getByRole('textbox', { name: '任务标题', exact: true })).toHaveValue(draft)

    for (const [group, file] of [['基础信息', 'editor-basic'], ['日期与时间', 'editor-date-time'], ['项目与分类', 'editor-organization'], ['重复与提醒', 'editor-repeat-reminder']]) {
      await showGroup(dialog, group!)
      await expect(dialog.getByRole('button', { name: '保存任务', exact: true })).toBeInViewport()
      await dialog.locator('.el-dialog__body').evaluate(element => { element.scrollTop = 0 })
      await page.screenshot({ animations: 'disabled', path: testInfo.outputPath(`${file}-${viewport.width}x${viewport.height}.png`) })
    }
    await dialog.getByRole('button', { name: '启用重复', exact: true }).click()
    await expect(dialog.getByRole('button', { name: '保存规则', exact: true })).toBeEnabled()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('textbox', { name: '提醒时间', exact: true }).fill('23:59')
    await dialog.getByRole('button', { name: '新增提醒', exact: true }).click()
    await expect(dialog.getByText('待处理', { exact: true })).toBeVisible()
    await dialog.getByRole('region', { name: '任务提醒', exact: true }).scrollIntoViewIfNeeded()
    await page.screenshot({ animations: 'disabled', path: testInfo.outputPath(`editor-reminder-${viewport.width}x${viewport.height}.png`) })
    await showGroup(dialog, '基础信息')
    await expect(dialog.getByRole('textbox', { name: '任务标题', exact: true })).toHaveValue(draft)
    const persisted = await (await request.get(`/api/v1/tasks/${task.id}`)).json()
    expect(persisted.title).toBe(title)
    expect(persisted.recurrence_rule_id).toBeTruthy()
    await page.route(`**/api/v1/tasks/${task.id}?*`, async route => {
      if (route.request().method() !== 'PATCH') return route.continue()
      const payload = route.request().postDataJSON()
      expect(payload).not.toHaveProperty('deadline')
      expect(payload).not.toHaveProperty('schedule')
      await route.fulfill({ status: 409, json: { error: { code: 'stale_version', message: 'stale' } } })
    })
    await dialog.getByRole('button', { name: '保存任务', exact: true }).click()
    await expect(dialog.getByRole('alert')).toContainText('其他操作更新')
    await expect(dialog.getByRole('textbox', { name: '任务标题', exact: true })).toHaveValue(draft)
    await page.unroute(`**/api/v1/tasks/${task.id}?*`)
    await dialog.getByRole('button', { name: '保存任务', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(taskCard(page, draft)).toBeVisible()
    const saved = await (await request.get(`/api/v1/tasks/${task.id}`)).json()
    expect(saved.title).toBe(draft)
    expect(saved.deadline_date).toBe('2099-01-01')
    expect(saved.category.id).toBe(category.id)
    expect(saved.tags).toHaveLength(4)
    await expect(taskCard(page, draft)).toContainText('重复任务')
    await page.reload()
    await expect(taskCard(page, draft)).toBeVisible()
    await page.evaluate(async () => { await document.fonts.ready; window.scrollTo({ top: 0, behavior: 'instant' }) })
    await page.screenshot({ animations: 'disabled', path: testInfo.outputPath(`today-${viewport.width}x${viewport.height}.png`) })
  })
}
