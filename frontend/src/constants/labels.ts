import { ApiRequestError } from '../api'
import type { TaskPriority } from '../types'

export const priorityLabels: Record<TaskPriority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
}

export function getTaskErrorMessage(
  error: unknown,
  area: 'today' | 'inbox' | 'search',
): string {
  const areaLabel = area === 'today' ? '今天的任务' : area === 'search' ? '搜索' : '收件箱'
  if (error instanceof ApiRequestError) {
    if (error.status === 409) {
      return `任务内容可能已被其他操作更新，请刷新${areaLabel}后重试。`
    }
    if (error.status === 422) {
      return '提交内容不符合要求，请检查后重试。'
    }
    return `请求失败，请稍后重试。（HTTP ${error.status}）`
  }
  return `${areaLabel}操作失败，请确认后端服务正在运行。`
}

export function getCalendarErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 409 && error.code !== 'schedule_conflict') {
      return '任务内容可能已被其他操作更新，请刷新日历后重试。'
    }
    if (error.status === 422) return '时间安排不符合要求，请检查日期和时间后重试。'
    if (error.code === 'schedule_conflict') return '该时间段与已有任务冲突。'
    return `日历请求失败，请稍后重试。（HTTP ${error.status}）`
  }
  return '日历操作失败，请确认后端服务正在运行。'
}

export function getMetadataErrorMessage(
  error: unknown,
  subject: 'category' | 'tag',
): string {
  const subjectLabel = subject === 'category' ? '分类' : '标签'
  if (error instanceof ApiRequestError) {
    if (error.code === `${subject}_name_conflict` || error.status === 409) {
      return `${subjectLabel}名称已存在，请换一个名称。`
    }
    if (error.status === 422) {
      return `${subjectLabel}名称不能为空，且长度需符合要求。`
    }
    return `${subjectLabel}操作失败，请稍后重试。（HTTP ${error.status}）`
  }
  return `${subjectLabel}操作失败，请确认后端服务正在运行。`
}

export function getMetadataLoadErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return `分类和标签加载失败，请稍后重试。（HTTP ${error.status}）`
  }
  return '分类和标签加载失败，请确认后端服务正在运行。'
}

export function getProjectErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.code === 'project_name_conflict') {
      return '项目名称已存在，请换一个名称。'
    }
    if (error.code === 'project_version_conflict' || error.code === 'stale_version') {
      return '项目已被其他操作更新，请刷新后重试。'
    }
    if (error.status === 404) return '项目不存在或已被删除。'
    if (error.status === 422) return '项目信息不符合要求，请检查后重试。'
    if (error.status === 409) return '项目操作发生冲突，请刷新后重试。'
    return `项目操作失败，请稍后重试。（HTTP ${error.status}）`
  }
  return '项目操作失败，请确认后端服务正在运行。'
}

export function getProjectLoadErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return `项目加载失败，请稍后重试。（HTTP ${error.status}）`
  }
  return '项目加载失败，请确认后端服务正在运行。'
}

export function getFeatureErrorMessage(error: unknown, feature: string): string {
  if (error instanceof ApiRequestError) {
    if (error.code === 'recurrence_version_conflict' || error.code === 'reminder_version_conflict') {
      return `${feature}已被其他操作更新，请刷新后重试。`
    }
    if (error.code === 'recurrence_rule_conflict' || error.code === 'reminder_state_conflict') {
      return `${feature}状态已发生变化，请刷新后重试。`
    }
    if (error.status === 422) return `${feature}信息不符合要求，请检查后重试。`
    return `${feature}操作失败，请稍后重试。（HTTP ${error.status}）`
  }
  return `${feature}操作失败，请确认后端服务正在运行。`
}
