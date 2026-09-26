import type { Task } from './types'

export function toDateInputValue(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatDisplayDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(`${value}T12:00:00`))
}

export function calculateCompletionRate(tasks: Task[]): number {
  if (tasks.length === 0) {
    return 0
  }
  return Math.round(
    (tasks.filter((task) => task.status === 'completed').length / tasks.length) * 100,
  )
}
