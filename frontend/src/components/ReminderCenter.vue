<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'

import { reminderApi, taskApi } from '../api'
import type { Reminder } from '../types'

const POLL_INTERVAL_MS = 45_000
const SESSION_KEY_PREFIX = 'dayflow.reminder-shown.'
let pollTimer: number | undefined

function wasShown(reminder: Reminder): boolean {
  try {
    return window.sessionStorage.getItem(`${SESSION_KEY_PREFIX}${reminder.id}`) === '1'
  } catch {
    return false
  }
}

function markShown(reminder: Reminder): void {
  try {
    window.sessionStorage.setItem(`${SESSION_KEY_PREFIX}${reminder.id}`, '1')
  } catch {
    // A session without storage should still receive the current reminder.
  }
}

function allowRetry(reminder: Reminder): void {
  try {
    window.sessionStorage.removeItem(`${SESSION_KEY_PREFIX}${reminder.id}`)
  } catch {
    // Ignore storage errors; the next poll can still retry in memory.
  }
}

async function showReminder(reminder: Reminder): Promise<void> {
  if (wasShown(reminder)) return
  markShown(reminder)
  let title = '任务提醒'
  try {
    const task = await taskApi.get(reminder.task_id)
    title = `任务提醒：${task.title}`
  } catch {
    // The reminder remains actionable even if its task title cannot be loaded.
  }

  let confirmed = false
  try {
    await ElMessageBox.confirm(
      '这条任务提醒已到时间。确认后会保留处理记录，关闭则标记为已关闭。',
      title,
      { confirmButtonText: '确认提醒', cancelButtonText: '关闭', distinguishCancelAndClose: true, type: 'warning' },
    )
    confirmed = true
  } catch {
    // The user explicitly closed the prompt, so this is the dismiss path.
  }

  if (confirmed) {
    try {
      await reminderApi.acknowledge(reminder.id, reminder.version)
    } catch {
      allowRetry(reminder)
    }
    return
  }

  try {
    await reminderApi.dismiss(reminder.id, reminder.version)
  } catch {
    allowRetry(reminder)
  }
}

async function checkDue(): Promise<void> {
  try {
    const reminders = await reminderApi.due()
    for (const reminder of reminders) await showReminder(reminder)
  } catch {
    // Polling is best-effort; the Task Editor still exposes pending reminders.
  }
}

onMounted(() => {
  void checkDue()
  pollTimer = window.setInterval(() => void checkDue(), POLL_INTERVAL_MS)
})

onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
})
</script>

<template>
  <span class="reminder-center" aria-live="polite" aria-hidden="true" />
</template>
