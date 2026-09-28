<script setup lang="ts">
import { computed } from 'vue'

import { formatCalendarDate, taskLocalClockMinutes, taskTimeLabel } from '../calendar'
import type { Task } from '../types'

const props = defineProps<{
  date: string
  tasks: Task[]
  today?: string
}>()

const emit = defineEmits<{ select: [task: Task] }>()

const untimedTasks = computed(() => props.tasks.filter((task) => !task.start_at_utc))
const timedTasks = computed(() => props.tasks.filter((task) => task.start_at_utc && task.end_at_utc))

function taskStyle(task: Task): Record<string, string> {
  if (!task.start_at_utc || !task.end_at_utc || !task.schedule_timezone) return {}
  const start = taskLocalClockMinutes(task.start_at_utc, task.schedule_timezone)
  const end = taskLocalClockMinutes(task.end_at_utc, task.schedule_timezone)
  return {
    top: `${(start / 1440) * 100}%`,
    height: `${Math.max(((end - start) / 1440) * 100, 3)}%`,
  }
}
</script>

<template>
  <section
    class="calendar-day-view"
    :class="{ 'is-today': date === today }"
    aria-label="日视图"
  >
    <div class="calendar-day-heading">
      <div>
        <p class="eyebrow">{{ formatCalendarDate(date, { weekday: 'long' }) }}</p>
        <h3>{{ date }}</h3>
      </div>
      <span class="calendar-count">{{ tasks.length }} 项</span>
    </div>

    <section class="calendar-untimed" aria-label="未安排时间">
      <h4>未安排时间</h4>
      <button
        v-for="task in untimedTasks"
        :key="task.id"
        class="calendar-task calendar-task-untimed"
        :class="{ 'is-completed': task.status === 'completed' }"
        type="button"
        @click="emit('select', task)"
      >
        <span>{{ task.title }}</span>
        <small v-if="task.status === 'completed'">已完成</small>
      </button>
      <p v-if="untimedTasks.length === 0" class="calendar-muted">暂无未安排时间的任务</p>
    </section>

    <section class="calendar-timeline" aria-label="时间轴">
      <div class="timeline-hours" aria-hidden="true">
        <span v-for="hour in 24" :key="hour">{{ String(hour - 1).padStart(2, '0') }}:00</span>
      </div>
      <div class="timeline-canvas">
        <div v-for="hour in 24" :key="hour" class="timeline-line" :style="{ top: `${((hour - 1) / 24) * 100}%` }" />
        <button
          v-for="task in timedTasks"
          :key="task.id"
          class="calendar-task calendar-task-timed"
          :class="{ 'is-completed': task.status === 'completed' }"
          type="button"
          :style="taskStyle(task)"
          @click="emit('select', task)"
        >
          <strong>{{ task.title }}</strong>
          <small>{{ taskTimeLabel(task) }}<span v-if="task.status === 'completed'"> · 已完成</span></small>
        </button>
        <p v-if="timedTasks.length === 0" class="calendar-muted timeline-empty">暂无时间安排</p>
      </div>
    </section>
  </section>
</template>
