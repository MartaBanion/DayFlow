<script setup lang="ts">
import { computed } from 'vue'

import { formatCalendarDate, taskTimeLabel } from '../calendar'
import type { Task } from '../types'

const props = defineProps<{
  days: string[]
  tasks: Task[]
  today: string
}>()

const emit = defineEmits<{ select: [task: Task] }>()

function tasksForDay(day: string): Task[] {
  return props.tasks.filter((task) => task.planned_date === day)
}

function timedTasks(day: string): Task[] {
  return tasksForDay(day).filter((task) => task.start_at_utc)
}

function untimedTasks(day: string): Task[] {
  return tasksForDay(day).filter((task) => !task.start_at_utc)
}

const dayLabels = computed(() => props.days.map((day) => ({
  day,
  label: formatCalendarDate(day, { weekday: 'short' }),
  date: formatCalendarDate(day, { month: 'numeric', day: 'numeric' }),
})))
</script>

<template>
  <section class="calendar-week-view" aria-label="周视图">
    <div class="calendar-week-grid">
      <section
        v-for="item in dayLabels"
        :key="item.day"
        class="calendar-week-day"
        :class="{ 'is-today': item.day === today }"
      >
        <header class="calendar-week-day-header">
          <span>{{ item.label }}</span>
          <strong>{{ item.date }}</strong>
        </header>
        <div class="calendar-week-untimed">
          <span class="calendar-section-label">未安排时间</span>
          <button
            v-for="task in untimedTasks(item.day)"
            :key="task.id"
            class="calendar-task calendar-week-task is-untimed"
            :class="{ 'is-completed': task.status === 'completed' }"
            type="button"
            @click="emit('select', task)"
          >
            {{ task.title }}
          </button>
        </div>
        <div class="calendar-week-timed">
          <button
            v-for="task in timedTasks(item.day)"
            :key="task.id"
            class="calendar-task calendar-week-task"
            :class="{ 'is-completed': task.status === 'completed' }"
            type="button"
            @click="emit('select', task)"
          >
            <strong>{{ task.title }}</strong>
            <small>{{ taskTimeLabel(task) }}</small>
          </button>
        </div>
        <p v-if="tasksForDay(item.day).length === 0" class="calendar-muted">暂无任务</p>
      </section>
    </div>
  </section>
</template>
