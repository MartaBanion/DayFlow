<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { projectApi, taskApi } from '../api'
import {
  calendarRange,
  formatCalendarDayTitle,
  formatCalendarMonthTitle,
  formatCalendarWeekSubtitle,
  formatCalendarWeekTitle,
  shiftAnchor,
  type CalendarMode,
} from '../calendar'
import { getCalendarErrorMessage } from '../constants/labels'
import { createTaskWithConflict, updateTaskWithConflict } from '../taskSave'
import type {
  Category,
  Project,
  Tag,
  Task,
  TaskCreatePayload,
  TaskUpdatePayload,
  RuntimeInfo,
} from '../types'
import CalendarDayView from './CalendarDayView.vue'
import CalendarMonthView from './CalendarMonthView.vue'
import CalendarWeekView from './CalendarWeekView.vue'
import TaskEditor from './TaskEditor.vue'

type CalendarLoadState = 'loading' | 'loaded' | 'error'

const mode = ref<CalendarMode>('week')
const anchorDate = ref('')
const runtime = ref<RuntimeInfo | null>(null)
const tasks = ref<Task[]>([])
const loadState = ref<CalendarLoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const isEditorOpen = ref(false)
const editingTask = ref<Task | null>(null)
const editorInitialDate = ref('')
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const projects = ref<Project[]>([])
const metadataLoaded = ref(false)

const range = computed(() => calendarRange(mode.value, anchorDate.value || '2000-01-01'))
const headerTitle = computed(() => {
  if (mode.value === 'day') return formatCalendarDayTitle(range.value.start)
  if (mode.value === 'week') return formatCalendarWeekTitle(range.value.start)
  return formatCalendarMonthTitle(anchorDate.value || range.value.start)
})
const headerSubtitle = computed(() => {
  if (mode.value === 'week') return formatCalendarWeekSubtitle(range.value.start, range.value.end)
  if (mode.value === 'day') return '按小时查看当天安排。'
  return '按日期查看本月任务。'
})

function showError(error: unknown): void {
  errorMessage.value = getCalendarErrorMessage(error)
}

async function loadCalendar(): Promise<void> {
  if (!runtime.value || !anchorDate.value) return
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    tasks.value = await taskApi.listCalendar(range.value.start, range.value.end)
    loadState.value = 'loaded'
  } catch (error) {
    loadState.value = 'error'
    showError(error)
  } finally {
    isLoading.value = false
  }
}

async function initializeCalendar(): Promise<void> {
  loadState.value = 'loading'
  errorMessage.value = ''
  try {
    runtime.value = await taskApi.getRuntime()
    anchorDate.value = runtime.value.local_date
    await loadCalendar()
  } catch (error) {
    loadState.value = 'error'
    showError(error)
  }
}

async function retryCalendar(): Promise<void> {
  if (runtime.value && anchorDate.value) {
    await loadCalendar()
  } else {
    await initializeCalendar()
  }
}

async function changeMode(nextMode: CalendarMode): Promise<void> {
  if (mode.value === nextMode) return
  mode.value = nextMode
  await loadCalendar()
}

async function moveAnchor(amount: number): Promise<void> {
  anchorDate.value = shiftAnchor(mode.value, anchorDate.value, amount)
  await loadCalendar()
}

async function goToToday(): Promise<void> {
  if (!runtime.value) return initializeCalendar()
  anchorDate.value = runtime.value.local_date
  await loadCalendar()
}

async function loadMetadata(): Promise<boolean> {
  if (metadataLoaded.value) return true
  try {
    const [loadedCategories, loadedTags, loadedProjects] = await Promise.all([
      taskApi.listCategories(),
      taskApi.listTags(),
      projectApi.list(),
    ])
    categories.value = loadedCategories
    tags.value = loadedTags
    projects.value = loadedProjects
    metadataLoaded.value = true
    return true
  } catch (error) {
    showError(error)
    return false
  }
}

async function openTask(task: Task): Promise<void> {
  if (!(await loadMetadata())) return
  editingTask.value = task
  editorInitialDate.value = task.planned_date ?? anchorDate.value
  isEditorOpen.value = true
}

async function createTask(): Promise<void> {
  if (!(await loadMetadata())) return
  editingTask.value = null
  editorInitialDate.value = anchorDate.value || runtime.value?.local_date || ''
  isEditorOpen.value = true
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

async function saveTask(payload: TaskUpdatePayload): Promise<void> {
  if (!payload.title?.trim()) {
    errorMessage.value = '请先填写任务标题。'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    let saved: Task | null
    if (editingTask.value) {
      saved = await updateTaskWithConflict(editingTask.value, payload, confirmScheduleConflict)
    } else {
      const createPayload: TaskCreatePayload = {
        title: payload.title,
        description: payload.description ?? null,
        planned_date: payload.planned_date ?? null,
        priority: payload.priority,
        category_id: payload.category_id,
        tag_ids: payload.tag_ids,
        project_id: payload.project_id,
        schedule: payload.schedule,
      }
      saved = await createTaskWithConflict(createPayload, confirmScheduleConflict)
    }
    if (!saved) return
    isEditorOpen.value = false
    await loadCalendar()
    ElMessage.success(editingTask.value ? '任务已更新' : '任务已创建')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

function handleMetadataUpdated(snapshot: { categories: Category[]; tags: Tag[] }): void {
  categories.value = snapshot.categories
  tags.value = snapshot.tags
}

onMounted(initializeCalendar)
</script>

<template>
  <header class="page-header calendar-header">
    <div>
      <p class="eyebrow">日历</p>
      <h2>{{ headerTitle }}</h2>
      <p class="muted">{{ headerSubtitle }}</p>
    </div>
  </header>

  <section class="calendar-toolbar" aria-label="日历导航">
    <div class="calendar-mode-switcher" role="group" aria-label="日历视图">
      <button
        v-for="item in ([['day', '日'], ['week', '周'], ['month', '月']] as const)"
        :key="item[0]"
        class="calendar-mode-button"
        :class="{ 'is-active': mode === item[0] }"
        type="button"
        :aria-pressed="mode === item[0]"
        @click="changeMode(item[0])"
      >
        {{ item[1] }}
      </button>
    </div>
    <div class="calendar-navigation">
      <el-button class="calendar-nav-button" plain aria-label="上一个时间段" title="上一个时间段" @click="moveAnchor(-1)">
        ‹
      </el-button>
      <el-button plain @click="goToToday">今天</el-button>
      <el-button class="calendar-nav-button" plain aria-label="下一个时间段" title="下一个时间段" @click="moveAnchor(1)">
        ›
      </el-button>
      <el-button class="calendar-refresh-button" :loading="isLoading" plain @click="retryCalendar">
        刷新
      </el-button>
      <el-button type="primary" @click="createTask">添加任务</el-button>
    </div>
  </section>

  <el-alert
    v-if="errorMessage && loadState !== 'error'"
    class="page-alert"
    :title="errorMessage"
    type="error"
    show-icon
    closable
    @close="errorMessage = ''"
  />

  <section v-if="loadState === 'loading'" class="calendar-state is-loading" aria-live="polite">
    <p class="eyebrow">加载中</p>
    <h3>正在加载日历</h3>
    <p>正在读取时间安排…</p>
  </section>

  <section v-else-if="loadState === 'error'" class="calendar-state is-error" role="alert">
    <p class="eyebrow">日历暂不可用</p>
    <h3>日历加载失败</h3>
    <p>{{ errorMessage || '日历加载失败，请稍后重试。' }}</p>
    <el-button type="primary" :loading="isLoading" @click="retryCalendar">重试</el-button>
  </section>

  <section v-else class="calendar-content">
    <el-empty v-if="tasks.length === 0" description="这个时间范围还没有任务">
      <template #image><div class="empty-mark">日</div></template>
    </el-empty>
    <CalendarDayView
      v-else-if="mode === 'day'"
      :date="range.start"
      :tasks="tasks"
      :today="runtime?.local_date ?? ''"
      @select="openTask"
    />
    <CalendarWeekView
      v-else-if="mode === 'week'"
      :days="range.days"
      :tasks="tasks"
      :today="runtime?.local_date ?? ''"
      @select="openTask"
    />
    <CalendarMonthView
      v-else
      :days="range.days"
      :tasks="tasks"
      :month="anchorDate.slice(0, 7)"
      :today="runtime?.local_date ?? ''"
      @select="openTask"
    />
  </section>

  <TaskEditor
    :open="isEditorOpen"
    :task="editingTask"
    :initial-date="editorInitialDate"
    :runtime-timezone="runtime?.timezone"
    :categories="categories"
    :tags="tags"
    :projects="projects"
    :saving="isSaving"
    @update:open="isEditorOpen = $event"
    @submit="saveTask"
  />

  <div class="calendar-sr-actions" aria-hidden="true">
    <span>{{ runtime?.timezone }}</span>
  </div>
</template>
