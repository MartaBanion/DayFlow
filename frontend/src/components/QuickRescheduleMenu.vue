<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getCalendarErrorMessage } from '../constants/labels'
import {
  QuickRescheduleError,
  quickRescheduleTask,
  type QuickRescheduleAction,
} from '../quickReschedule'
import type { Task } from '../types'

const props = withDefaults(defineProps<{
  task: Task
  runtimeLocalDate?: string | null
  modelValue: boolean
  disabled?: boolean
}>(), {
  runtimeLocalDate: null,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: [task: Task]
  error: [error: unknown]
}>()

const selectedDate = ref('')
const chooseDateOpen = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')

const hasSchedule = () => Boolean(props.task.start_at_utc && props.task.end_at_utc && props.task.schedule_timezone)

function resetForm(): void {
  selectedDate.value = ''
  chooseDateOpen.value = false
  errorMessage.value = ''
}

watch(() => props.modelValue, (open) => {
  if (open) resetForm()
})

function close(): void {
  if (!isSaving.value) emit('update:modelValue', false)
}

function getErrorMessage(error: unknown): string {
  if (error instanceof QuickRescheduleError) {
    if (error.code === 'runtime_unavailable') return '无法读取 DayFlow 当前日期，请稍后重试。'
    if (error.code === 'selected_date_required') return '请选择一个有效的计划日期。'
    if (error.code === 'task_not_pending') return '已完成任务不能调整日期。'
    if (error.code === 'task_deleted') return '已删除任务不能调整日期。'
    return '计划日期不符合要求，请检查后重试。'
  }
  return getCalendarErrorMessage(error)
}

async function confirmScheduleConflict(): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      '该时间段与已有任务冲突，是否仍然保存？',
      '时间安排冲突',
      { confirmButtonText: '仍然保存', cancelButtonText: '取消', type: 'warning' },
    )
    return true
  } catch {
    return false
  }
}

async function confirmMoveToInbox(): Promise<boolean> {
  if (!hasSchedule()) return true
  try {
    await ElMessageBox.confirm(
      '移回收件箱会清除当前时间安排。是否继续？',
      '清除时间安排',
      { confirmButtonText: '移回收件箱', cancelButtonText: '取消', type: 'warning' },
    )
    return true
  } catch {
    return false
  }
}

async function submit(action: QuickRescheduleAction): Promise<void> {
  if (isSaving.value || props.disabled) return
  if (action === 'inbox' && !(await confirmMoveToInbox())) return

  isSaving.value = true
  errorMessage.value = ''
  try {
    const updated = await quickRescheduleTask({
      task: props.task,
      runtimeLocalDate: props.runtimeLocalDate,
      action,
      selectedDate: selectedDate.value || null,
      confirmScheduleConflict,
    })
    if (!updated) return
    emit('success', updated)
    emit('update:modelValue', false)
    ElMessage.success(action === 'inbox' ? '任务已移回收件箱' : '计划日期已调整')
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
    emit('error', error)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="调整日期"
    width="min(420px, calc(100vw - 32px))"
    :close-on-click-modal="false"
    :close-on-press-escape="!isSaving"
    destroy-on-close
    @update:model-value="(value: boolean) => !isSaving && emit('update:modelValue', value)"
  >
    <div class="quick-reschedule-dialog">
      <p class="quick-reschedule-task" :title="task.title">{{ task.title }}</p>
      <p class="quick-reschedule-help">只调整计划日期，不会修改截止时间、提醒或重复规则。</p>

      <el-alert
        v-if="errorMessage"
        class="quick-reschedule-error"
        :title="errorMessage"
        type="error"
        show-icon
        role="alert"
      />

      <div class="quick-reschedule-actions" aria-label="调整日期选项">
        <el-button :disabled="isSaving || disabled" @click="submit('today')">今天</el-button>
        <el-button :disabled="isSaving || disabled" @click="submit('tomorrow')">明天</el-button>
        <el-button :disabled="isSaving || disabled" @click="submit('next_monday')">下周一</el-button>
        <el-button :disabled="isSaving || disabled" @click="submit('inbox')">移回收件箱</el-button>
        <el-button :disabled="isSaving || disabled" @click="chooseDateOpen = !chooseDateOpen">
          选择日期
        </el-button>
      </div>

      <div v-if="chooseDateOpen" class="quick-reschedule-date-picker">
        <label for="quick-reschedule-date">新的计划日期</label>
        <el-date-picker
          id="quick-reschedule-date"
          v-model="selectedDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          :disabled="isSaving || disabled"
          aria-label="新的计划日期"
        />
        <div class="quick-reschedule-date-actions">
          <el-button text :disabled="isSaving" @click="chooseDateOpen = false">取消</el-button>
          <el-button
            type="primary"
            :loading="isSaving"
            :disabled="!selectedDate || disabled"
            @click="submit('choose_date')"
          >
            确认日期
          </el-button>
        </div>
      </div>

      <p v-if="hasSchedule()" class="quick-reschedule-warning" role="note">
        移回收件箱会清除当前时间安排。
      </p>
    </div>
    <template #footer>
      <el-button :disabled="isSaving" @click="close">取消</el-button>
    </template>
  </el-dialog>
</template>
