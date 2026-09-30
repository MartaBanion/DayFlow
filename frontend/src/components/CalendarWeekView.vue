<script setup lang="ts">
import { computed } from 'vue'

import { formatCalendarDate, taskDeadlineLabel, taskLocalClockMinutes, taskTimeLabel } from '../calendar'
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
  return tasksForDay(day).filter((task) => task.start_at_utc && task.end_at_utc)
}

function untimedTasks(day: string): Task[] {
  return tasksForDay(day).filter((task) => !task.start_at_utc)
}

function taskStyle(task: Task): Record<string, string> {
  if (!task.start_at_utc || !task.end_at_utc || !task.schedule_timezone) return {}
  const start = taskLocalClockMinutes(task.start_at_utc, task.schedule_timezone)
  const end = taskLocalClockMinutes(task.end_at_utc, task.schedule_timezone)
  return {
    top: `${(start / 1440) * 100}%`,
    height: `${Math.max(((end - start) / 1440) * 100, 3)}%`,
  }
}

const dayLabels = computed(() => props.days.map((day) => ({
  day,
  label: formatCalendarDate(day, { weekday: 'short' }),
  date: formatCalendarDate(day, { month: 'numeric', day: 'numeric' }),
})))
</script>

<template>
  <section class="calendar-week-view" aria-label="周视图">
    <div class="calendar-week-header-grid">
      <div class="calendar-week-time-gutter" aria-hidden="true" />
      <section
        v-for="item in dayLabels"
        :key="item.day"
        class="calendar-week-day calendar-week-day-header-cell"
        :class="{ 'is-today': item.day === today }"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.date }}</strong>
      </section>
    </div>

    <section class="calendar-week-untimed" aria-label="未安排时间">
      <div class="calendar-week-untimed-title">
        <span class="calendar-section-label">未安排时间</span>
        <span class="calendar-muted">按日期安排、尚未设置具体时间的任务</span>
      </div>
      <div class="calendar-week-untimed-grid">
        <div class="calendar-week-time-gutter" aria-hidden="true" />
        <div
          v-for="item in dayLabels"
          :key="item.day"
          class="calendar-week-untimed-day"
          :class="{ 'is-today': item.day === today }"
        >
          <button
            v-for="task in untimedTasks(item.day)"
            :key="task.id"
            class="calendar-task calendar-week-task is-untimed"
            :class="{ 'is-completed': task.status === 'completed' }"
            type="button"
            @click="emit('select', task)"
          >
            <strong>{{ task.title }}</strong>
            <small v-if="task.project">{{ task.project.name }}</small>
            <small v-if="taskDeadlineLabel(task)">{{ taskDeadlineLabel(task) }}</small>
            <small v-if="task.status === 'completed'">已完成</small>
          </button>
        </div>
      </div>
    </section>

    <section class="calendar-week-timeline" aria-label="时间轴">
      <div class="calendar-week-hours" aria-hidden="true">
        <span v-for="hour in 24" :key="hour">{{ String(hour - 1).padStart(2, '0') }}:00</span>
      </div>
      <div class="calendar-week-columns">
        <div
          v-for="item in dayLabels"
          :key="item.day"
          class="calendar-week-column"
          :class="{ 'is-today': item.day === today }"
        >
          <span
            v-for="hour in 24"
            :key="hour"
            class="timeline-line"
            :style="{ top: `${((hour - 1) / 24) * 100}%` }"
          />
          <button
            v-for="task in timedTasks(item.day)"
            :key="task.id"
            class="calendar-task calendar-week-task calendar-task-timed"
            :class="{ 'is-completed': task.status === 'completed' }"
            type="button"
            :style="taskStyle(task)"
            @click="emit('select', task)"
          >
            <strong>{{ task.title }}</strong>
            <small>{{ taskTimeLabel(task) }}<span v-if="task.project"> · {{ task.project.name }}</span><span v-if="taskDeadlineLabel(task)"> · {{ taskDeadlineLabel(task) }}</span><span v-if="task.status === 'completed'"> · 已完成</span></small>
          </button>
        </div>
      </div>
    </section>
  </section>
</template>
