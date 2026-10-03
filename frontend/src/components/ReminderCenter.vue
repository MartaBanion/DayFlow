<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { reminderApi, taskApi } from '../api'
import type { Reminder } from '../types'

const POLL_INTERVAL_MS = 45_000
const SESSION_KEY_PREFIX = 'dayflow.reminder-shown.'
let pollTimer: number | undefined
let pollInFlight = false

const dueReminders = ref<Reminder[]>([])
const pollError = ref('')
const lastPollFailedAt = ref<string | null>(null)
const isPolling = ref(false)
const isRetrying = ref(false)

const failureTimeLabel = computed(() => {
  if (!lastPollFailedAt.value) return ''
  const parsed = new Date(lastPollFailedAt.value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(parsed)
})

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

function removeDueReminder(reminderId: string): void {
  dueReminders.value = dueReminders.value.filter((reminder) => reminder.id !== reminderId)
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
      removeDueReminder(reminder.id)
    } catch {
      allowRetry(reminder)
    }
    return
  }

  try {
    await reminderApi.dismiss(reminder.id, reminder.version)
    removeDueReminder(reminder.id)
  } catch {
    allowRetry(reminder)
  }
}

async function checkDue(): Promise<void> {
  if (pollInFlight) return
  pollInFlight = true
  isPolling.value = true
  try {
    const reminders = await reminderApi.due()
    dueReminders.value = reminders
    pollError.value = ''
    lastPollFailedAt.value = null
    for (const reminder of reminders) await showReminder(reminder)
  } catch {
    if (!pollError.value) lastPollFailedAt.value = new Date().toISOString()
    pollError.value = '提醒查询失败'
  } finally {
    pollInFlight = false
    isPolling.value = false
  }
}

async function retryPoll(): Promise<void> {
  if (isRetrying.value || pollInFlight) return
  isRetrying.value = true
  try {
    await checkDue()
  } finally {
    isRetrying.value = false
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
  <div v-if="pollError || dueReminders.length" class="reminder-center">
    <section v-if="pollError" class="reminder-poll-error" role="alert">
      <div class="reminder-poll-copy">
        <strong>提醒查询失败</strong>
        <p>部分提醒可能暂时无法更新。<time v-if="failureTimeLabel" :datetime="lastPollFailedAt ?? undefined">最近失败：{{ failureTimeLabel }}</time></p>
      </div>
      <button
        class="reminder-poll-retry"
        type="button"
        :disabled="isPolling || isRetrying"
        :aria-label="isRetrying ? '正在重试提醒查询' : '重试提醒查询'"
        @click="retryPoll"
      >
        {{ isRetrying ? '重试中…' : '重试' }}
      </button>
    </section>

    <section v-if="dueReminders.length" class="reminder-poll-summary" aria-label="待处理提醒">
      <span>待处理提醒</span>
      <strong>{{ dueReminders.length }} 条</strong>
    </section>
  </div>
</template>
