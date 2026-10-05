<script setup lang="ts">
import { computed } from 'vue'

import { formatCalendarDate, taskDeadlineLabel, taskTimeLabel } from '../calendar'
import type { Task } from '../types'

const props = defineProps<{
  days: string[]
  tasks: Task[]
  month: string
  today?: string
}>()

const emit = defineEmits<{
  select: [task: Task]
  selectDate: [date: string]
}>()

function tasksForDay(day: string): Task[] {
  return props.tasks.filter((task) => task.planned_date === day)
}

const dayLabels = computed(() => props.days.map((day) => ({
  day,
  number: formatCalendarDate(day, { day: 'numeric' }),
  weekday: formatCalendarDate(day, { weekday: 'short' }),
})))
</script>

<template>
  <section class="calendar-month-view" aria-label="月视图">
    <div class="calendar-month-weekdays" aria-hidden="true">
      <span v-for="day in ['一', '二', '三', '四', '五', '六', '日']" :key="day">周{{ day }}</span>
    </div>
    <div class="calendar-month-grid">
      <section
        v-for="item in dayLabels"
        :key="item.day"
        class="calendar-month-day"
        :class="{
          'is-outside-month': !item.day.startsWith(month),
          'is-today': item.day === today,
        }"
      >
        <button
          class="calendar-month-day-header calendar-month-day-trigger"
          type="button"
          :disabled="!item.day.startsWith(month)"
          :aria-label="`查看 ${item.day} 的日视图`"
          @click="emit('selectDate', item.day)"
          @keydown.enter.prevent="emit('selectDate', item.day)"
          @keydown.space.prevent="emit('selectDate', item.day)"
        >
          <span>{{ item.number }}</span>
          <small>{{ item.weekday }}</small>
        </button>
        <button
          v-for="task in tasksForDay(item.day).slice(0, 3)"
          :key="task.id"
          class="calendar-task calendar-month-task"
          :class="{ 'is-completed': task.status === 'completed' }"
          type="button"
          @click.stop="emit('select', task)"
        >
          <span>{{ task.title }}</span>
          <small v-if="task.start_at_utc">{{ taskTimeLabel(task) }}</small>
          <small v-if="task.project">{{ task.project.name }}</small>
          <small v-if="taskDeadlineLabel(task)">{{ taskDeadlineLabel(task) }}</small>
        </button>
        <button
          v-if="tasksForDay(item.day).length > 3 && item.day.startsWith(month)"
          class="calendar-more"
          type="button"
          :aria-label="`查看 ${item.day} 的全部任务`"
          @click.stop="emit('selectDate', item.day)"
          @keydown.enter.stop.prevent="emit('selectDate', item.day)"
          @keydown.space.stop.prevent="emit('selectDate', item.day)"
        >
          还有 {{ tasksForDay(item.day).length - 3 }} 项
        </button>
      </section>
    </div>
  </section>
</template>
