import { ApiRequestError } from '../api'
import type { TaskPriority } from '../types'

export const priorityLabels: Record<TaskPriority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
}

export function getTaskErrorMessage(
  error: unknown,
  area: 'today' | 'inbox',
): string {
  const areaLabel = area === 'today' ? '今天的任务' : '收件箱'
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
