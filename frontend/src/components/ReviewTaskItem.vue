<script setup lang="ts">
import { computed } from 'vue'

import { deadlineStatusLabel, taskDeadlineLabel, taskTimeLabel, formatReminderTime } from '../calendar'
import { priorityLabels } from '../constants/labels'
import type { Task } from '../types'

type ReviewTaskSection = 'completed' | 'overdue' | 'carryover'

const props = defineProps<{
  task: Task
  section: ReviewTaskSection
  timezone: string
}>()

const emit = defineEmits<{
  open: [task: Task]
}>()

const sectionLabel = computed(() => {
  if (props.section === 'completed') return '已完成'
  if (props.section === 'overdue') return '已逾期'
  return '遗留'
})

const completionLabel = computed(() => {
  if (props.section !== 'completed' || !props.task.completed_at_utc) return ''
  return `完成于 ${formatReminderTime(props.task.completed_at_utc, props.timezone)}`
})

const metadata = computed(() => [
  props.task.project?.name ? `项目：${props.task.project.name}` : '',
  props.task.category?.name ? `分类：${props.task.category.name}` : '',
  props.task.planned_date ? `计划：${props.task.planned_date}` : '',
  taskTimeLabel(props.task) ? `时间：${taskTimeLabel(props.task)}` : '',
  priorityLabels[props.task.priority],
].filter(Boolean).join(' · '))
</script>

<template>
  <article class="review-task-item">
    <button
      class="review-task-button"
      type="button"
      :aria-label="`打开任务：${task.title}`"
      @click="emit('open', task)"
    >
      <span class="review-task-copy">
        <span class="review-task-title" :title="task.title">{{ task.title }}</span>
        <span v-if="metadata" class="review-task-meta">{{ metadata }}</span>
        <span v-if="taskDeadlineLabel(task)" class="review-task-meta review-task-deadline">
          {{ taskDeadlineLabel(task) }}<template v-if="deadlineStatusLabel(task.deadline_status)"> · {{ deadlineStatusLabel(task.deadline_status) }}</template>
        </span>
        <span v-if="completionLabel" class="review-task-meta review-task-completed-at">{{ completionLabel }}</span>
      </span>
      <span class="review-task-side">
        <span class="review-status-label" :class="`is-${section}`">{{ sectionLabel }}</span>
        <span class="review-task-arrow" aria-hidden="true">›</span>
      </span>
    </button>
  </article>
</template>
