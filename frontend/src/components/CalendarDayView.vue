<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElTooltip } from 'element-plus'

import { calendarTimeBlocks, formatCalendarDate, taskDeadlineLabel, taskLocalClockMinutes, taskTimeLabel } from '../calendar'
import type { Task } from '../types'
import QuickRescheduleMenu from './QuickRescheduleMenu.vue'

const props = defineProps<{
  date: string
  tasks: Task[]
  today?: string
  runtimeLocalDate?: string | null
}>()

const emit = defineEmits<{
  select: [task: Task]
  rescheduled: [task: Task]
}>()

const untimedTasks = computed(() => props.tasks.filter((task) => !task.start_at_utc))
const timedTasks = computed(() => props.tasks.filter((task) => task.start_at_utc && task.end_at_utc))

const blocks = computed(() => calendarTimeBlocks(timedTasks.value))
const timelineScroll = ref<HTMLElement | null>(null)
const rescheduleTask = ref<Task | null>(null)
const isRescheduleOpen = ref(false)

function openReschedule(task: Task): void {
  rescheduleTask.value = task
  isRescheduleOpen.value = true
}

function updateRescheduleOpen(value: boolean): void {
  isRescheduleOpen.value = value
  if (!value) rescheduleTask.value = null
}

function handleRescheduled(task: Task): void {
  updateRescheduleOpen(false)
  emit('rescheduled', task)
}
watch(() => props.date, async () => {
  await nextTick()
  const first = timedTasks.value.reduce((earliest, task) => Math.min(earliest, taskLocalClockMinutes(task.start_at_utc!, task.schedule_timezone!)), 1440)
  if (timelineScroll.value) timelineScroll.value.scrollTop = (first === 1440 ? 480 : first) / 1440 * timelineScroll.value.scrollHeight - 40
}, { immediate: true })
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
      <div v-for="task in untimedTasks" :key="task.id" class="calendar-task-row">
        <button
          class="calendar-task calendar-task-untimed"
          :class="{ 'is-completed': task.status === 'completed' }"
          type="button"
          @click="emit('select', task)"
        >
          <span>{{ task.title }}</span>
          <small v-if="task.project">{{ task.project.name }}</small>
          <small v-if="taskDeadlineLabel(task)">{{ taskDeadlineLabel(task) }}</small>
          <small v-if="task.status === 'completed'">已完成</small>
        </button>
        <button
          v-if="task.status === 'pending'"
          class="calendar-task-reschedule-trigger"
          type="button"
          :disabled="isRescheduleOpen"
          :aria-label="`调整日期：${task.title}`"
          @click.stop="openReschedule(task)"
        >
          调整日期
        </button>
      </div>
      <p v-if="untimedTasks.length === 0" class="calendar-muted">暂无未安排时间的任务</p>
    </section>

    <div ref="timelineScroll" class="calendar-time-scroll" role="region" tabindex="0" aria-label="全天时间轴，可滚动查看">
    <section class="calendar-timeline" aria-label="时间轴">
      <div class="timeline-hours" aria-hidden="true">
        <span v-for="hour in 24" :key="hour">{{ String(hour - 1).padStart(2, '0') }}:00</span>
      </div>
      <div class="timeline-canvas">
        <div v-for="hour in 24" :key="hour" class="timeline-line" :style="{ top: `${((hour - 1) / 24) * 100}%` }" />
        <ElTooltip
          v-for="task in timedTasks"
          :key="task.id"
          :content="`${task.title} · ${taskTimeLabel(task)}`"
          :trigger="['hover', 'focus']"
        >
          <div class="calendar-task-timed-wrapper" :style="blocks[task.id]?.style">
            <button
              class="calendar-task calendar-task-timed"
              :class="{ 'is-completed': task.status === 'completed', 'is-short': blocks[task.id]?.short }"
              type="button"
              :title="`${task.title} · ${taskTimeLabel(task)}`"
              :aria-label="`${task.title} · ${taskTimeLabel(task)}`"
              @click="emit('select', task)"
            >
              <strong>{{ task.title }}</strong>
              <small>{{ taskTimeLabel(task) }}</small>
            </button>
            <button
              v-if="task.status === 'pending'"
              class="calendar-task-reschedule-trigger calendar-task-reschedule-trigger-compact"
              type="button"
              :disabled="isRescheduleOpen"
              :aria-label="`调整日期：${task.title}`"
              @click.stop="openReschedule(task)"
            >
              调整
            </button>
          </div>
        </ElTooltip>
        <p v-if="timedTasks.length === 0" class="calendar-muted timeline-empty">暂无时间安排</p>
      </div>
    </section>
    </div>

    <QuickRescheduleMenu
      v-if="rescheduleTask"
      :model-value="isRescheduleOpen"
      :task="rescheduleTask"
      :runtime-local-date="runtimeLocalDate"
      @update:model-value="updateRescheduleOpen"
      @success="handleRescheduled"
    />
  </section>
</template>
