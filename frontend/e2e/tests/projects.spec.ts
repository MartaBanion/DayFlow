import { expect, test } from '@playwright/test'

import {
  chooseInboxFilter,
  clearTaskSelect,
  createTask,
  openTaskEditor,
  saveTaskEditor,
  taskCard,
  uniqueName,
} from '../helpers/api'

test('项目支持创建、关联任务、进度、删除和恢复', async ({ page, request }) => {
  const projectName = uniqueName('E2E-项目')
  const renamedProject = `${projectName}-新名称`
  const taskTitle = uniqueName('E2E-项目任务')
  const searchTaskTitle = uniqueName('E2E-项目筛选任务')

  await page.goto('/#projects')
  await expect(page.getByRole('heading', { name: '项目', exact: true })).toBeVisible()

  await page.getByRole('button', { name: '新建项目', exact: true }).first().click()
  const createDialog = page.locator('.el-dialog').filter({ hasText: '新建项目' }).last()
  await expect(createDialog).toBeVisible()
  await createDialog.getByLabel('项目名称').fill(projectName)
  await createDialog.getByLabel('项目描述').fill('浏览器验收项目')
  await createDialog.getByRole('button', { name: '创建项目', exact: true }).click()
  await expect(createDialog).toBeHidden()

  const projectCard = page.locator('.project-card').filter({ hasText: projectName }).first()
  await expect(projectCard).toBeVisible()

  await projectCard.getByRole('button', { name: '编辑', exact: true }).click()
  const editDialog = page.locator('.el-dialog').filter({ hasText: '编辑项目' }).last()
  await editDialog.getByLabel('项目名称').fill(renamedProject)
  await editDialog.getByRole('button', { name: '保存修改', exact: true }).click()
  await expect(editDialog).toBeHidden()
  await expect(page.locator('.project-card').filter({ hasText: renamedProject }).first()).toBeVisible()

  await page.locator('.project-card').filter({ hasText: renamedProject }).first().locator('.project-card-main').click()
  await expect(page).toHaveURL(/#project:/)
  await expect(page.getByRole('heading', { name: renamedProject, exact: true })).toBeVisible()

  await page.locator('.page-header-actions').getByRole('button', { name: '新建任务', exact: true }).click()
  const taskDialog = page.locator('.el-dialog').filter({ hasText: '新建任务' }).last()
  await taskDialog.getByLabel('任务标题').fill(taskTitle)
  await taskDialog.getByRole('button', { name: '保存任务', exact: true }).click()
  await expect(taskDialog).toBeHidden()
  await expect(taskCard(page, taskTitle)).toBeVisible()
  await expect(page.locator('.project-detail-summary')).toContainText('0%')

  await page.getByRole('link', { name: /项目/ }).click()
  const activeCard = page.locator('.project-card').filter({ hasText: renamedProject }).first()
  await activeCard.getByRole('button', { name: '完成项目', exact: true }).click()
  const completeBox = page.locator('.el-message-box').last()
  await expect(completeBox).toContainText('不会自动完成这些任务')
  await completeBox.getByRole('button', { name: '继续完成', exact: true }).click()
  await expect(activeCard.getByText('已完成', { exact: true })).toBeVisible()

  await activeCard.getByRole('button', { name: '重新打开', exact: true }).click()
  await expect(activeCard.getByText('进行中', { exact: true })).toBeVisible()

  await page.locator('.project-card-main').filter({ hasText: renamedProject }).click()
  const detailTask = taskCard(page, taskTitle)
  await detailTask.getByRole('button', { name: `完成任务：${taskTitle}` }).click()
  await expect(page.locator('.project-detail-summary')).toContainText('100%')

  const clearDialog = await openTaskEditor(page, taskTitle)
  await clearTaskSelect(clearDialog, '项目')
  await saveTaskEditor(clearDialog)
  await expect(taskCard(page, taskTitle)).toHaveCount(0)

  const project = await (await request.get('/api/v1/projects')).json() as Array<{ id: string; name: string }>
  const currentProject = project.find((item) => item.name === renamedProject)
  expect(currentProject).toBeDefined()
  const searchTask = await createTask(request, {
    title: searchTaskTitle,
    planned_date: null,
    project_id: currentProject!.id,
  })

  await page.goto('/#search')
  await expect(page.getByRole('heading', { name: '搜索任务', exact: true })).toBeVisible()
  await chooseInboxFilter(page, 3, renamedProject)
  await expect(taskCard(page, searchTaskTitle)).toBeVisible()

  await page.getByRole('link', { name: /项目/ }).click()
  const deleteCard = page.locator('.project-card').filter({ hasText: renamedProject }).first()
  await deleteCard.getByRole('button', { name: '更多项目操作' }).click()
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const deleteBox = page.locator('.el-message-box').last()
  await expect(deleteBox).toContainText('会保留，但会变为未归属项目')
  await deleteBox.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.locator('.project-card:not(.is-deleted)').filter({ hasText: renamedProject })).toHaveCount(0)

  const taskAfterDeleteResponse = await request.get(`/api/v1/tasks/${searchTask.id}`)
  expect(taskAfterDeleteResponse.ok()).toBeTruthy()
  const taskAfterDelete = await taskAfterDeleteResponse.json() as { project_id: string | null }
  expect(taskAfterDelete.project_id).toBeNull()

  const showDeletedButton = page.getByRole('button', { name: /查看已删除项目/ })
  if (await showDeletedButton.count()) await showDeletedButton.click()
  const deletedCard = page.locator('.project-card.is-deleted').filter({ hasText: renamedProject })
  await expect(deletedCard).toBeVisible()
  await deletedCard.getByRole('button', { name: '恢复项目', exact: true }).click()
  await expect(page.locator('.project-card').filter({ hasText: renamedProject }).first()).toBeVisible()

  const taskAfterRestoreResponse = await request.get(`/api/v1/tasks/${searchTask.id}`)
  expect(taskAfterRestoreResponse.ok()).toBeTruthy()
  const taskAfterRestore = await taskAfterRestoreResponse.json() as { project_id: string | null }
  expect(taskAfterRestore.project_id).toBeNull()

  await page.reload()
  await expect(page.locator('.project-card').filter({ hasText: renamedProject }).first()).toBeVisible()
})
