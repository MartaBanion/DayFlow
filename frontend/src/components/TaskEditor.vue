<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { recurrenceApi, reminderApi } from '../api'
import { getFeatureErrorMessage, priorityLabels } from '../constants/labels'
import { formatReminderTime, formatTaskTime } from '../calendar'
import type {
  Category,
  Project,
  RecurrenceCreatePayload,
  RecurrenceFrequency,
  RecurrenceRule,
  RecurrenceUpdatePayload,
  Reminder,
  ReminderPayload,
  Tag,
  Task,
  TaskDeadlinePayload,
  TaskPriority,
  TaskSchedulePayload,
  TaskUpdatePayload,
} from '../types'

const props = defineProps<{
  open: boolean
  task: Task | null
  categories: Category[]
  tags: Tag[]
  projects?: Project[]
  saving?: boolean
  initialDate?: string
  initialProjectId?: string | null
  runtimeTimezone?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [payload: TaskUpdatePayload]
  changed: []
}>()

const title = ref('')
const description = ref('')
const plannedDate = ref('')
const priority = ref<TaskPriority>('normal')
const categoryId = ref<string | null>(null)
const tagIds = ref<string[]>([])
const projectId = ref<string | null>(null)
const startTime = ref('')
const endTime = ref('')
const scheduleTouched = ref(false)
const deadlineDate = ref('')
const deadlineTime = ref('')
const deadlineTimezone = ref('')
const deadlineTouched = ref(false)
const formError = ref('')
const featureError = ref('')
const featureLoading = ref(false)
const featureSaving = ref(false)
const recurrenceRule = ref<RecurrenceRule | null>(null)
const repeatFrequency = ref<RecurrenceFrequency>('daily')
const repeatWeekdays = ref<number[]>([0])
const repeatMonthDay = ref(1)
const repeatStartsOn = ref('')
const repeatTimezone = ref('')
const reminders = ref<Reminder[]>([])
const reminderDate = ref('')
const reminderTime = ref('')
const reminderTimezone = ref('')
const editingReminderId = ref<string | null>(null)
const editingReminderVersion = ref(1)

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function syncForm(task: Task | null): void {
  title.value = task?.title ?? ''
  description.value = task?.description ?? ''
  plannedDate.value = task?.planned_date ?? props.initialDate ?? ''
  priority.value = task?.priority ?? 'normal'
  categoryId.value = task?.category?.id ?? null
  tagIds.value = task?.tags.map((tag) => tag.id) ?? []
  projectId.value = task?.project_id ?? task?.project?.id ?? props.initialProjectId ?? null
  startTime.value =
    task?.start_at_utc && task.schedule_timezone
      ? formatTaskTime(task.start_at_utc, task.schedule_timezone)
      : ''
  endTime.value =
    task?.end_at_utc && task.schedule_timezone
      ? formatTaskTime(task.end_at_utc, task.schedule_timezone)
      : ''
  deadlineDate.value = task?.deadline_date ?? ''
  deadlineTime.value =
    task?.deadline_at_utc && task.deadline_timezone
      ? formatTaskTime(task.deadline_at_utc, task.deadline_timezone)
      : ''
  deadlineTimezone.value = task?.deadline_timezone ?? props.runtimeTimezone ?? ''
  scheduleTouched.value = false
  deadlineTouched.value = false
  formError.value = ''
  featureError.value = ''
  recurrenceRule.value = null
  reminders.value = []
  repeatFrequency.value = 'daily'
  repeatWeekdays.value = [0]
  repeatMonthDay.value = 1
  repeatStartsOn.value = task?.planned_date ?? props.initialDate ?? ''
  repeatTimezone.value = task?.schedule_timezone ?? props.runtimeTimezone ?? ''
  reminderDate.value = task?.planned_date ?? props.initialDate ?? ''
  reminderTime.value = ''
  reminderTimezone.value = props.runtimeTimezone ?? ''
  editingReminderId.value = null
}

watch(
  [() => props.task, () => props.open, () => props.initialDate, () => props.initialProjectId],
  () => syncForm(props.task),
  {
  immediate: true,
  },
)

async function loadFeatures(): Promise<void> {
  if (!props.open || !props.task) return
  featureLoading.value = true
  featureError.value = ''
  try {
    const loadedReminders = await reminderApi.list(props.task.id)
    reminders.value = loadedReminders
    if (props.task.recurrence_rule_id) {
      const rule = await recurrenceApi.get(props.task.recurrence_rule_id)
      recurrenceRule.value = rule
      repeatFrequency.value = rule.frequency
      repeatWeekdays.value = rule.weekdays ?? [0]
      repeatMonthDay.value = rule.month_day ?? 1
      repeatStartsOn.value = rule.starts_on
      repeatTimezone.value = rule.timezone
    }
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '重复任务或提醒')
  } finally {
    featureLoading.value = false
  }
}

watch(() => props.open, () => void loadFeatures())

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

function buildDeadline(): TaskDeadlinePayload | null | undefined {
  const hasExistingDeadline = Boolean(props.task?.deadline_date)
  if (!deadlineTouched.value && hasExistingDeadline) return undefined
  if (!deadlineDate.value) return deadlineTouched.value ? null : undefined
  return {
    date: deadlineDate.value,
    ...(deadlineTime.value ? { time: deadlineTime.value } : {}),
    ...(deadlineTimezone.value ? { timezone: deadlineTimezone.value.trim() } : {}),
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
  const deadline = buildDeadline()

  const payload: TaskUpdatePayload = {
    title: trimmedTitle,
    description: description.value.trim() || null,
    planned_date: plannedDate.value || null,
    priority: priority.value,
    category_id: categoryId.value ?? null,
    tag_ids: tagIds.value,
    project_id: projectId.value ?? null,
  }
  if (schedule !== undefined) payload.schedule = schedule
  if (deadline !== undefined) payload.deadline = deadline
  emit('submit', payload)
}

function repeatPayload(): RecurrenceCreatePayload {
  return {
    version: props.task?.version ?? 1,
    frequency: repeatFrequency.value,
    starts_on: repeatStartsOn.value,
    timezone: repeatTimezone.value.trim() || props.runtimeTimezone || undefined,
    weekdays: repeatFrequency.value === 'weekly' ? repeatWeekdays.value : null,
    month_day: repeatFrequency.value === 'monthly' ? repeatMonthDay.value : null,
  }
}

function repeatUpdatePayload(): RecurrenceUpdatePayload {
  const payload = repeatPayload()
  return {
    frequency: payload.frequency,
    starts_on: payload.starts_on,
    timezone: payload.timezone,
    weekdays: payload.weekdays,
    month_day: payload.month_day,
  }
}

async function saveRepeat(): Promise<void> {
  if (!props.task || !repeatStartsOn.value) {
    featureError.value = '请先为任务设置计划日期，再保存重复规则。'
    return
  }
  if (repeatFrequency.value === 'weekly' && repeatWeekdays.value.length === 0) {
    featureError.value = '每周重复至少需要选择一天。'
    return
  }
  featureSaving.value = true
  featureError.value = ''
  try {
    if (recurrenceRule.value) {
      recurrenceRule.value = await recurrenceApi.update(
        recurrenceRule.value.id,
        recurrenceRule.value.version,
        repeatUpdatePayload(),
      )
    } else {
      recurrenceRule.value = await recurrenceApi.create(props.task.id, repeatPayload())
    }
    ElMessage.success('重复规则已保存')
    emit('changed')
    emit('update:open', false)
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '重复规则')
  } finally {
    featureSaving.value = false
  }
}

async function stopRepeat(): Promise<void> {
  if (!recurrenceRule.value) return
  try {
    await ElMessageBox.confirm(
      '停止重复后不会再生成新的任务，历史任务会保留。确定停止吗？',
      '停止重复',
      { confirmButtonText: '停止重复', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  featureSaving.value = true
  featureError.value = ''
  try {
    await recurrenceApi.stop(recurrenceRule.value.id, recurrenceRule.value.version)
    ElMessage.success('重复规则已停止')
    emit('changed')
    emit('update:open', false)
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '重复规则')
  } finally {
    featureSaving.value = false
  }
}

async function materializeRepeat(): Promise<void> {
  if (!recurrenceRule.value) return
  featureSaving.value = true
  featureError.value = ''
  try {
    await recurrenceApi.materialize(recurrenceRule.value.id)
    ElMessage.success('下一次任务已准备好')
    emit('changed')
    emit('update:open', false)
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '下一次任务')
  } finally {
    featureSaving.value = false
  }
}

async function skipCurrentOccurrence(): Promise<void> {
  if (!props.task?.recurrence_rule_id) return
  featureSaving.value = true
  featureError.value = ''
  try {
    await recurrenceApi.skip(props.task.id, props.task.version)
    ElMessage.success('本次任务已跳过，下一次任务已准备好')
    emit('changed')
    emit('update:open', false)
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '跳过本次任务')
  } finally {
    featureSaving.value = false
  }
}

function localReminderParts(reminder: Reminder): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: reminder.reminder_timezone,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date(reminder.trigger_at_utc))
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return { date: `${value('year')}-${value('month')}-${value('day')}`, time: `${value('hour')}:${value('minute')}` }
}

function beginReminderEdit(reminder: Reminder): void {
  const parts = localReminderParts(reminder)
  editingReminderId.value = reminder.id
  editingReminderVersion.value = reminder.version
  reminderDate.value = parts.date
  reminderTime.value = parts.time
  reminderTimezone.value = reminder.reminder_timezone
}

function resetReminderForm(): void {
  editingReminderId.value = null
  editingReminderVersion.value = 1
  reminderDate.value = props.task?.planned_date ?? props.initialDate ?? ''
  reminderTime.value = ''
  reminderTimezone.value = props.runtimeTimezone ?? ''
}

function reminderPayload(): ReminderPayload | null {
  if (!reminderDate.value || !reminderTime.value) {
    featureError.value = '请填写提醒日期和时间。'
    return null
  }
  return {
    date: reminderDate.value,
    time: reminderTime.value,
    ...(reminderTimezone.value ? { timezone: reminderTimezone.value.trim() } : {}),
  }
}

async function saveReminder(): Promise<void> {
  if (!props.task) return
  const payload = reminderPayload()
  if (!payload) return
  featureSaving.value = true
  featureError.value = ''
  try {
    if (editingReminderId.value) {
      await reminderApi.update(editingReminderId.value, editingReminderVersion.value, payload)
    } else {
      await reminderApi.create(props.task.id, payload)
    }
    reminders.value = await reminderApi.list(props.task.id)
    resetReminderForm()
    ElMessage.success('提醒已保存')
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '提醒')
  } finally {
    featureSaving.value = false
  }
}

async function deleteReminder(reminder: Reminder): Promise<void> {
  try {
    await ElMessageBox.confirm('确定删除这条提醒吗？', '删除提醒', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch {
    return
  }
  featureSaving.value = true
  featureError.value = ''
  try {
    await reminderApi.remove(reminder.id, reminder.version)
    reminders.value = await reminderApi.list(props.task?.id ?? '')
    if (editingReminderId.value === reminder.id) resetReminderForm()
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '提醒')
  } finally {
    featureSaving.value = false
  }
}

async function transitionReminder(reminder: Reminder, action: 'acknowledge' | 'dismiss'): Promise<void> {
  featureSaving.value = true
  featureError.value = ''
  try {
    const updated = action === 'acknowledge'
      ? await reminderApi.acknowledge(reminder.id, reminder.version)
      : await reminderApi.dismiss(reminder.id, reminder.version)
    reminders.value = reminders.value.map((item) => item.id === updated.id ? updated : item)
  } catch (error) {
    featureError.value = getFeatureErrorMessage(error, '提醒')
  } finally {
    featureSaving.value = false
  }
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
        native-type="button"
        @click="clearSchedule"
      >
        清除时间安排
      </el-button>
      <div class="form-grid deadline-fields">
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="deadlineDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="不设置截止日期"
            style="width: 100%"
            @change="deadlineTouched = true"
          />
        </el-form-item>
        <el-form-item label="截止时间（可选）">
          <input
            v-model="deadlineTime"
            class="schedule-time-input"
            type="time"
            aria-label="截止时间"
            @input="deadlineTouched = true"
          />
        </el-form-item>
      </div>
      <el-form-item label="截止时区">
        <el-input
          v-model="deadlineTimezone"
          placeholder="例如 Asia/Shanghai"
          aria-label="截止时区"
          @input="deadlineTouched = true"
        />
      </el-form-item>
      <p v-if="deadlineDate" class="schedule-hint">截止日期独立于计划日期和具体时间安排。</p>
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
      <el-form-item label="项目">
        <el-select
          v-model="projectId"
          clearable
          placeholder="未归属项目"
          style="width: 100%"
          aria-label="项目"
        >
          <el-option
            v-for="project in projects ?? []"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>
      </el-form-item>
      <section v-if="task" class="feature-panel" aria-label="重复任务">
        <div class="feature-panel-heading">
          <div>
            <p class="eyebrow">重复任务</p>
            <h4>{{ recurrenceRule ? '重复规则' : '设置重复' }}</h4>
          </div>
          <span v-if="recurrenceRule" class="feature-status">已启用</span>
        </div>
        <p v-if="!recurrenceRule && !featureLoading" class="schedule-hint">保存后可按天、按周或按月重复。不复制截止日期、提醒和时间安排。</p>
        <div class="form-grid">
          <el-form-item label="重复方式">
            <el-select v-model="repeatFrequency" style="width: 100%">
              <el-option label="每天" value="daily" />
              <el-option label="每周" value="weekly" />
              <el-option label="每月" value="monthly" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="repeatFrequency === 'monthly'" label="每月日期">
            <input v-model.number="repeatMonthDay" class="schedule-time-input" type="number" min="1" max="28" aria-label="每月日期" />
          </el-form-item>
        </div>
        <div v-if="repeatFrequency === 'weekly'" class="weekday-picker" aria-label="重复星期">
          <label v-for="(label, index) in weekdayLabels" :key="label">
            <input v-model="repeatWeekdays" type="checkbox" :value="index" /> {{ label }}
          </label>
        </div>
        <div class="form-grid">
          <el-form-item label="开始重复日期">
            <el-date-picker v-model="repeatStartsOn" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item label="重复时区">
            <el-input v-model="repeatTimezone" placeholder="例如 Asia/Shanghai" />
          </el-form-item>
        </div>
        <div class="feature-actions">
          <el-button type="primary" native-type="button" :loading="featureSaving" @click="saveRepeat">{{ recurrenceRule ? '保存规则' : '启用重复' }}</el-button>
          <el-button v-if="recurrenceRule" native-type="button" :loading="featureSaving" @click="materializeRepeat">手动生成下一次</el-button>
          <el-button v-if="recurrenceRule" text native-type="button" :loading="featureSaving" @click="stopRepeat">停止重复</el-button>
          <el-button v-if="recurrenceRule" text native-type="button" :loading="featureSaving" @click="skipCurrentOccurrence">跳过本次</el-button>
        </div>
      </section>
      <section v-if="task" class="feature-panel" aria-label="任务提醒">
        <div class="feature-panel-heading">
          <div>
            <p class="eyebrow">提醒</p>
            <h4>指定时间提醒我</h4>
          </div>
          <span class="feature-status">{{ reminders.length }} 条</span>
        </div>
        <div v-if="reminders.length" class="reminder-list">
          <div v-for="reminder in reminders" :key="reminder.id" class="reminder-row">
            <div>
              <strong>{{ formatReminderTime(reminder.trigger_at_utc, reminder.reminder_timezone) }}</strong>
              <span>{{ reminder.status === 'pending' ? '待处理' : reminder.status === 'acknowledged' ? '已确认' : '已关闭' }}</span>
            </div>
            <div class="feature-actions">
              <el-button text native-type="button" @click="beginReminderEdit(reminder)">修改</el-button>
              <el-button v-if="reminder.status === 'pending'" text native-type="button" @click="transitionReminder(reminder, 'acknowledge')">确认</el-button>
              <el-button v-if="reminder.status === 'pending'" text native-type="button" @click="transitionReminder(reminder, 'dismiss')">关闭</el-button>
              <el-button type="danger" text native-type="button" @click="deleteReminder(reminder)">删除</el-button>
            </div>
          </div>
        </div>
        <div class="form-grid reminder-form">
          <el-form-item :label="editingReminderId ? '修改日期' : '提醒日期'">
            <el-date-picker v-model="reminderDate" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item label="提醒时间">
            <input v-model="reminderTime" class="schedule-time-input" type="time" aria-label="提醒时间" />
          </el-form-item>
        </div>
        <el-form-item label="提醒时区">
          <el-input v-model="reminderTimezone" placeholder="例如 Asia/Shanghai" />
        </el-form-item>
        <div class="feature-actions">
          <el-button type="primary" native-type="button" :loading="featureSaving" @click="saveReminder">{{ editingReminderId ? '保存提醒' : '新增提醒' }}</el-button>
          <el-button v-if="editingReminderId" text native-type="button" @click="resetReminderForm">取消修改</el-button>
        </div>
      </section>
      <p v-if="featureLoading" class="schedule-hint">正在读取重复规则和提醒…</p>
      <p v-if="featureError" class="form-error" role="alert">{{ featureError }}</p>
      <div class="dialog-actions">
        <el-button @click="emit('update:open', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ task ? '保存修改' : '创建任务' }}
        </el-button>
      </div>
    </el-form>
  </el-dialog>
</template>
