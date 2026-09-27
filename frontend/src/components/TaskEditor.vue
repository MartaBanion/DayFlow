<script setup lang="ts">
import { ref, watch } from 'vue'

import { priorityLabels } from '../constants/labels'
import { formatTaskTime } from '../calendar'
import type {
  Category,
  Tag,
  Task,
  TaskPriority,
  TaskSchedulePayload,
  TaskUpdatePayload,
} from '../types'

const props = defineProps<{
  open: boolean
  task: Task | null
  categories: Category[]
  tags: Tag[]
  saving?: boolean
  initialDate?: string
  runtimeTimezone?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [payload: TaskUpdatePayload]
}>()

const title = ref('')
const description = ref('')
const plannedDate = ref('')
const priority = ref<TaskPriority>('normal')
const categoryId = ref<string | null>(null)
const tagIds = ref<string[]>([])
const startTime = ref('')
const endTime = ref('')
const scheduleTouched = ref(false)
const formError = ref('')

function syncForm(task: Task | null): void {
  title.value = task?.title ?? ''
  description.value = task?.description ?? ''
  plannedDate.value = task?.planned_date ?? props.initialDate ?? ''
  priority.value = task?.priority ?? 'normal'
  categoryId.value = task?.category?.id ?? null
  tagIds.value = task?.tags.map((tag) => tag.id) ?? []
  startTime.value =
    task?.start_at_utc && task.schedule_timezone
      ? formatTaskTime(task.start_at_utc, task.schedule_timezone)
      : ''
  endTime.value =
    task?.end_at_utc && task.schedule_timezone
      ? formatTaskTime(task.end_at_utc, task.schedule_timezone)
      : ''
  scheduleTouched.value = false
  formError.value = ''
}

watch([() => props.task, () => props.open, () => props.initialDate], () => syncForm(props.task), {
  immediate: true,
})

function clearSchedule(): void {
  startTime.value = ''
  endTime.value = ''
  scheduleTouched.value = true
  formError.value = ''
}

function buildSchedule(): TaskSchedulePayload | null | undefined {
  const hasExistingSchedule = Boolean(
    props.task?.start_at_utc && props.task.end_at_utc && props.task.schedule_timezone,
  )
  const hasAnyTime = Boolean(startTime.value || endTime.value)

  if (!plannedDate.value && (hasExistingSchedule || scheduleTouched.value || hasAnyTime)) {
    return null
  }
  if (!scheduleTouched.value && hasExistingSchedule) return undefined
  if (!startTime.value && !endTime.value) return scheduleTouched.value ? null : undefined

  if (!startTime.value || !endTime.value) {
    formError.value = '请同时填写开始时间和结束时间。'
    return undefined
  }
  if (startTime.value >= endTime.value) {
    formError.value = '结束时间必须晚于开始时间。'
    return undefined
  }

  return {
    start_time: startTime.value,
    end_time: endTime.value,
    timezone: props.task?.schedule_timezone ?? props.runtimeTimezone ?? undefined,
  }
}

function submit(): void {
  const trimmedTitle = title.value.trim()
  formError.value = ''
  if (!trimmedTitle) {
    formError.value = '请先填写任务标题。'
    return
  }
  const schedule = buildSchedule()
  if (formError.value) return

  const payload: TaskUpdatePayload = {
    title: trimmedTitle,
    description: description.value.trim() || null,
    planned_date: plannedDate.value || null,
    priority: priority.value,
    category_id: categoryId.value ?? null,
    tag_ids: tagIds.value,
  }
  if (schedule !== undefined) payload.schedule = schedule
  emit('submit', payload)
}
</script>

<template>
  <el-dialog
    :model-value="open"
    :title="task ? '编辑任务' : '新建任务'"
    width="560px"
    @update:model-value="emit('update:open', $event)"
  >
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="任务标题" required>
        <el-input v-model="title" placeholder="请输入任务标题" autofocus />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="description" type="textarea" :rows="4" placeholder="补充备注（可选）" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="计划日期">
          <el-date-picker
            v-model="plannedDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="未安排日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="priority" style="width: 100%">
            <el-option :label="priorityLabels.low" value="low" />
            <el-option :label="priorityLabels.normal" value="normal" />
            <el-option :label="priorityLabels.high" value="high" />
          </el-select>
        </el-form-item>
      </div>
      <div class="form-grid schedule-fields">
        <el-form-item label="开始时间">
          <input
            v-model="startTime"
            class="schedule-time-input"
            type="time"
            aria-label="开始时间"
            @input="scheduleTouched = true"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <input
            v-model="endTime"
            class="schedule-time-input"
            type="time"
            aria-label="结束时间"
            @input="scheduleTouched = true"
          />
        </el-form-item>
      </div>
      <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      <p v-if="plannedDate && !startTime && !endTime" class="schedule-hint">
        未安排时间
      </p>
      <el-button
        v-if="startTime || endTime || task?.start_at_utc"
        class="clear-schedule-button"
        text
        @click="clearSchedule"
      >
        清除时间安排
      </el-button>
      <el-form-item label="分类">
        <el-select v-model="categoryId" clearable placeholder="未分类" style="width: 100%">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="标签">
        <el-select v-model="tagIds" multiple clearable placeholder="无标签" style="width: 100%">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </el-form-item>
      <div class="dialog-actions">
        <el-button @click="emit('update:open', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ task ? '保存修改' : '创建任务' }}
        </el-button>
      </div>
    </el-form>
  </el-dialog>
</template>
