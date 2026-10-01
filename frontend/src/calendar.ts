import type { Task } from './types'

export type CalendarMode = 'day' | 'week' | 'month'

export interface CalendarRange {
  start: string
  end: string
  days: string[]
}

function dateFromKey(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day, 12)
}

function keyFromDate(value: Date): string {
  return [value.getFullYear(), value.getMonth() + 1, value.getDate()]
    .map((part, index) => (index === 0 ? String(part) : String(part).padStart(2, '0')))
    .join('-')
}

export function addDays(value: string, amount: number): string {
  const result = dateFromKey(value)
  result.setDate(result.getDate() + amount)
  return keyFromDate(result)
}

export function startOfWeek(value: string): string {
  const date = dateFromKey(value)
  const mondayOffset = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - mondayOffset)
  return keyFromDate(date)
}

export function startOfMonth(value: string): string {
  const date = dateFromKey(value)
  return keyFromDate(new Date(date.getFullYear(), date.getMonth(), 1, 12))
}

export function endOfMonth(value: string): string {
  const date = dateFromKey(value)
  return keyFromDate(new Date(date.getFullYear(), date.getMonth() + 1, 0, 12))
}

export function listDays(start: string, end: string): string[] {
  const days: string[] = []
  for (let current = start; current <= end; current = addDays(current, 1)) {
    days.push(current)
  }
  return days
}

export function calendarRange(mode: CalendarMode, anchor: string): CalendarRange {
  if (mode === 'day') return { start: anchor, end: anchor, days: [anchor] }
  if (mode === 'week') {
    const start = startOfWeek(anchor)
    const end = addDays(start, 6)
    return { start, end, days: listDays(start, end) }
  }

  const first = startOfMonth(anchor)
  const last = endOfMonth(anchor)
  const start = startOfWeek(first)
  const end = addDays(startOfWeek(last), 6)
  return { start, end, days: listDays(start, end) }
}

export function shiftAnchor(mode: CalendarMode, anchor: string, amount: number): string {
  if (mode === 'day') return addDays(anchor, amount)
  if (mode === 'week') return addDays(anchor, amount * 7)
  const date = dateFromKey(anchor)
  return keyFromDate(new Date(date.getFullYear(), date.getMonth() + amount, 1, 12))
}

export function formatCalendarDate(value: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('zh-CN', options).format(dateFromKey(value))
}

export function formatCalendarDayTitle(value: string): string {
  const date = dateFromKey(value)
  const month = new Intl.DateTimeFormat('zh-CN', { month: 'numeric' }).format(date)
  const day = new Intl.DateTimeFormat('zh-CN', { day: 'numeric' }).format(date)
  const weekday = new Intl.DateTimeFormat('zh-CN', { weekday: 'long' }).format(date)
  return `${month}${day} ${weekday}`
}

export function isoWeekNumber(value: string): number {
  const date = dateFromKey(value)
  const day = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - day + 3)
  const firstThursday = new Date(date.getFullYear(), 0, 4, 12)
  return 1 + Math.round((date.getTime() - firstThursday.getTime()) / (7 * 86400000))
}

export function formatCalendarWeekTitle(value: string): string {
  const year = new Intl.DateTimeFormat('zh-CN', { year: 'numeric' }).format(dateFromKey(value))
  const month = new Intl.DateTimeFormat('zh-CN', { month: 'numeric' }).format(dateFromKey(value))
  return `${year}${month} · 第${isoWeekNumber(value)}周`
}

export function formatCalendarWeekSubtitle(start: string, end: string): string {
  const format = (value: string) => {
    const date = dateFromKey(value)
    const month = new Intl.DateTimeFormat('zh-CN', { month: 'numeric' }).format(date)
    const day = new Intl.DateTimeFormat('zh-CN', { day: 'numeric' }).format(date)
    return `${month}${day}`
  }
  return `${format(start)} - ${format(end)}`
}

export function formatCalendarMonthTitle(value: string): string {
  const date = dateFromKey(value)
  const year = new Intl.DateTimeFormat('zh-CN', { year: 'numeric' }).format(date)
  const month = new Intl.DateTimeFormat('zh-CN', { month: 'numeric' }).format(date)
  return `${year}${month}`
}

export function formatTaskTime(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    hourCycle: 'h23',
  }).format(new Date(value))
}

export function taskLocalClockMinutes(value: string, timezone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const hour = Number(parts.find((part) => part.type === 'hour')?.value ?? 0)
  const minute = Number(parts.find((part) => part.type === 'minute')?.value ?? 0)
  return hour * 60 + minute
}

export function taskTimeLabel(task: Task): string {
  if (!task.start_at_utc || !task.end_at_utc || !task.schedule_timezone) return ''
  return `${formatTaskTime(task.start_at_utc, task.schedule_timezone)}–${formatTaskTime(task.end_at_utc, task.schedule_timezone)}`
}

/** Display lanes only: never changes UTC instants or conflict policy. */
export function calendarTimeBlocks(tasks: Task[]): Record<string, { style: Record<string, string>; short: boolean }> {
  const blocks = tasks.flatMap((task) => {
    if (!task.start_at_utc || !task.end_at_utc || !task.schedule_timezone) return []
    return [{ id: task.id, start: taskLocalClockMinutes(task.start_at_utc, task.schedule_timezone), end: taskLocalClockMinutes(task.end_at_utc, task.schedule_timezone), lane: 0 }]
  }).sort((a, b) => a.start - b.start || b.end - a.end || a.id.localeCompare(b.id))
  const result: ReturnType<typeof calendarTimeBlocks> = {}
  let group: typeof blocks = []
  let groupEnd = -1
  const flush = () => {
    const laneEnds: number[] = []
    for (const block of group) {
      const available = laneEnds.findIndex((end) => end <= block.start)
      block.lane = available === -1 ? laneEnds.length : available
      laneEnds[block.lane] = block.end
    }
    for (const block of group) result[block.id] = {
      short: block.end - block.start <= 45,
      style: {
        top: `${block.start / 1440 * 100}%`,
        height: `${(block.end - block.start) / 1440 * 100}%`,
        left: `calc(${block.lane / laneEnds.length * 100}% + 3px)`,
        width: `calc(${100 / laneEnds.length}% - 6px)`,
      },
    }
  }
  for (const block of blocks) {
    if (block.start >= groupEnd) { flush(); group = []; groupEnd = -1 }
    group.push(block)
    groupEnd = Math.max(groupEnd, block.end)
  }
  flush()
  return result
}

export function taskDeadlineLabel(task: Task): string {
  if (!task.deadline_date) return ''
  if (task.deadline_at_utc && task.deadline_timezone) {
    return `截止：${task.deadline_date} ${formatTaskTime(task.deadline_at_utc, task.deadline_timezone)}`
  }
  return `截止：${task.deadline_date}`
}

export function deadlineStatusLabel(status: Task['deadline_status']): string {
  if (status === 'overdue') return '已逾期'
  if (status === 'due_today') return '今天截止'
  if (status === 'completed') return '已完成'
  return ''
}

export function formatReminderTime(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    hourCycle: 'h23',
  }).format(new Date(value))
}
