<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElTooltip } from 'element-plus'

import { calendarTimeBlocks, formatCalendarDate, taskDeadlineLabel, taskLocalClockMinutes, taskTimeLabel } from '../calendar'
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

const blocks = computed(() => Object.assign({}, ...props.days.map((day) => calendarTimeBlocks(timedTasks(day)))) as ReturnType<typeof calendarTimeBlocks>)
const timelineScroll = ref<HTMLElement | null>(null)
watch(() => props.days.join(','), async () => {
  await nextTick()
  const first = props.tasks.filter((task) => task.start_at_utc && task.schedule_timezone).reduce((earliest, task) => Math.min(earliest, taskLocalClockMinutes(task.start_at_utc!, task.schedule_timezone!)), 1440)
  if (timelineScroll.value) timelineScroll.value.scrollTop = (first === 1440 ? 480 : first) / 1440 * timelineScroll.value.scrollHeight - 40
}, { immediate: true })

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

    <div ref="timelineScroll" class="calendar-time-scroll" role="region" tabindex="0" aria-label="全天时间轴，可滚动查看">
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
          <ElTooltip
            v-for="task in timedTasks(item.day)"
            :key="task.id"
            :content="`${task.title} · ${taskTimeLabel(task)}`"
            :trigger="['hover', 'focus']"
          >
          <button
            class="calendar-task calendar-week-task calendar-task-timed"
            :class="{ 'is-completed': task.status === 'completed', 'is-short': blocks[task.id]?.short }"
            type="button"
            :style="blocks[task.id]?.style"
            :title="`${task.title} · ${taskTimeLabel(task)}`"
            :aria-label="`${task.title} · ${taskTimeLabel(task)}`"
            @click="emit('select', task)"
          >
            <strong>{{ task.title }}</strong>
            <small>{{ taskTimeLabel(task) }}</small>
          </button>
          </ElTooltip>
        </div>
      </div>
    </section>
    </div>
  </section>
</template>
