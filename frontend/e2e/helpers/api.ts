import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test'

import type {
  Category,
  Project,
  Tag,
  Task,
  TaskDeadlinePayload,
  TaskPriority,
  TaskSchedulePayload,
} from '../../src/types'

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function todayDate(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

async function responseJson<T>(response: Awaited<ReturnType<APIRequestContext['post']>>): Promise<T> {
  if (!response.ok()) {
    throw new Error(`${response.status()} ${await response.text()}`)
  }
  return (await response.json()) as T
}

export async function createTask(
  request: APIRequestContext,
  payload: {
    title: string
    description?: string | null
    planned_date?: string | null
    priority?: TaskPriority
    category_id?: string | null
    tag_ids?: string[]
    project_id?: string | null
    schedule?: TaskSchedulePayload | null
    deadline?: TaskDeadlinePayload | null
  },
): Promise<Task> {
  const response = await request.post('/api/v1/tasks', {
    data: {
      description: null,
      planned_date: null,
      priority: 'normal',
      category_id: null,
      tag_ids: [],
      project_id: null,
      schedule: null,
      deadline: null,
      ...payload,
    },
  })
  return responseJson<Task>(response)
}

export async function createProject(
  request: APIRequestContext,
  name: string,
  description: string | null = null,
): Promise<Project> {
  const response = await request.post('/api/v1/projects', { data: { name, description } })
  return responseJson<Project>(response)
}

export async function createCategory(
  request: APIRequestContext,
  name: string,
): Promise<Category> {
  const response = await request.post('/api/v1/categories', { data: { name } })
  return responseJson<Category>(response)
}

export async function createTag(request: APIRequestContext, name: string): Promise<Tag> {
  const response = await request.post('/api/v1/tags', { data: { name } })
  return responseJson<Tag>(response)
}

export function taskCard(page: Page, title: string): Locator {
  return page.locator('article.task-card').filter({ hasText: title })
}

export async function openTaskEditor(page: Page, title: string): Promise<Locator> {
  const card = taskCard(page, title)
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: '编辑', exact: true }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '编辑任务' }).last()
  await expect(dialog).toBeVisible()
  for (const group of ['项目与分类', '重复与提醒']) {
    const summary = dialog.getByText(group, { exact: true })
    if (await summary.locator('xpath=ancestor::details[1]').getAttribute('open') === null) await summary.click()
  }
  return dialog
}

export async function saveTaskEditor(dialog: Locator): Promise<void> {
  await dialog.getByRole('button', { name: '保存任务', exact: true }).click()
  await expect(dialog).toBeHidden()
}

export async function chooseTaskPriority(
  page: Page,
  dialog: Locator,
  label: string,
): Promise<void> {
  const item = dialog.locator('.el-form-item').filter({ hasText: '优先级' })
  await item.locator('.el-select').click()
  await page.getByRole('option', { name: label, exact: true }).click()
}

export async function chooseTaskCategory(
  page: Page,
  dialog: Locator,
  name: string,
): Promise<void> {
  const item = dialog.locator('.el-form-item').filter({ hasText: '分类' })
  await item.locator('.el-select').click()
  await page.getByRole('option', { name, exact: true }).click()
}

export async function chooseTaskTags(
  page: Page,
  dialog: Locator,
  names: string[],
): Promise<void> {
  const item = dialog.locator('.el-form-item').filter({ hasText: '标签' })
  await item.locator('.el-select').click()
  for (const name of names) {
    await page.getByRole('option', { name, exact: true }).click()
  }
  await page.keyboard.press('Escape')
}

export async function chooseTaskProject(
  page: Page,
  dialog: Locator,
  name: string,
): Promise<void> {
  const summary = dialog.getByText('项目与分类', { exact: true })
  if (await summary.locator('xpath=ancestor::details[1]').getAttribute('open') === null) await summary.click()
  const item = dialog.locator('.el-form-item').filter({ hasText: '项目' })
  await item.locator('.el-select').click()
  await page.getByRole('option', { name, exact: true }).click()
}

export async function clearTaskSelect(dialog: Locator, label: string): Promise<void> {
  const item = dialog.locator('.el-form-item').filter({ hasText: label })
  await item.locator('.el-select').hover()
  await item.locator('.el-select__clear').click()
}

export async function chooseTodayDate(page: Page, dialog: Locator): Promise<void> {
  const editor = dialog.locator('.el-form-item').filter({ hasText: '计划日期' }).locator('.el-date-editor')
  await editor.click()
  const picker = page.locator('.el-picker-panel:visible').last()
  await expect(picker).toBeVisible()
  const day = String(Number(todayDate().slice(-2)))
  await picker
    .locator('td.available:not(.prev-month):not(.next-month)')
    .filter({ hasText: new RegExp(`^${day}$`) })
    .click()
}

export async function clearTaskDate(dialog: Locator): Promise<void> {
  const editor = dialog.locator('.el-form-item').filter({ hasText: '计划日期' }).locator('.el-date-editor')
  await editor.hover()
  await editor.locator('.clear-icon').click()
}

export async function openMetadataManager(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: '管理分类与标签', exact: true }).click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '管理分类与标签' }).last()
  await expect(dialog).toBeVisible()
  return dialog
}

export async function closeDialog(dialog: Locator): Promise<void> {
  await dialog.locator('.el-dialog__headerbtn').click()
  await expect(dialog).toBeHidden()
}

export async function confirmDelete(page: Page): Promise<void> {
  const messageBox = page.locator('.el-message-box').last()
  await expect(messageBox).toBeVisible()
  await messageBox.getByRole('button', { name: '删除', exact: true }).click()
  await expect(messageBox).toBeHidden()
}

export async function chooseInboxFilter(
  page: Page,
  index: number,
  option: string,
): Promise<void> {
  await page.locator('.filter-row .el-select').nth(index).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

export async function chooseProjectTaskFilter(
  page: Page,
  index: number,
  option: string,
): Promise<void> {
  await page.locator('.project-filter-row .el-select').nth(index).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}
