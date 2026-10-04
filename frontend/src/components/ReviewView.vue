<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError, projectApi, reviewApi, taskApi } from '../api'
import { formatReminderTime } from '../calendar'
import { updateTaskWithConflict } from '../taskSave'
import type { Category, Project, ReviewProject, ReviewResponse, ReviewScope, Tag, Task, TaskUpdatePayload } from '../types'
import ReviewTaskItem from './ReviewTaskItem.vue'
import TaskEditor from './TaskEditor.vue'

type LoadState = 'loading' | 'loaded' | 'error'
type ReviewTaskSection = 'completed' | 'overdue' | 'carryover'

const scope = ref<ReviewScope>('today')
const reviewData = ref<ReviewResponse | null>(null)
const loadState = ref<LoadState>('loading')
const isLoading = ref(false)
const errorMessage = ref('')
const metadataLoaded = ref(false)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const projects = ref<Project[]>([])
const runtimeTimezone = ref('')
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)
const isSaving = ref(false)
let requestSequence = 0

const scopeLabel = computed(() => scope.value === 'today' ? '今天' : '本周')
const completedEmptyLabel = computed(() => scope.value === 'today' ? '今天还没有完成的任务' : '本周还没有保留的完成记录')

function reviewLoadError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return `回顾加载失败，请稍后重试。（HTTP ${error.status}）`
  }
  return '回顾加载失败，请确认后端服务正在运行。'
}

async function loadReview(options: { preserveData?: boolean } = {}): Promise<void> {
  const requestId = ++requestSequence
  const preserveData = options.preserveData === true && reviewData.value !== null
  if (!preserveData) {
    reviewData.value = null
    loadState.value = 'loading'
  }
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await reviewApi.get(scope.value)
    if (requestId !== requestSequence) return
    reviewData.value = response
    runtimeTimezone.value = response.local_timezone
    loadState.value = 'loaded'
  } catch (error) {
    if (requestId !== requestSequence) return
    errorMessage.value = reviewLoadError(error)
    loadState.value = reviewData.value ? 'loaded' : 'error'
  } finally {
    if (requestId === requestSequence) isLoading.value = false
  }
}

async function selectScope(nextScope: ReviewScope): Promise<void> {
  if (scope.value === nextScope || isLoading.value) return
  scope.value = nextScope
  await loadReview()
}

async function retryReview(): Promise<void> {
  await loadReview({ preserveData: Boolean(reviewData.value) })
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
    errorMessage.value = reviewLoadError(error)
    return false
  }
}

async function openTask(task: Task): Promise<void> {
  if (!(await loadMetadata())) return
  editingTask.value = task
  isEditDialogOpen.value = true
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
  const task = editingTask.value
  if (!task || !payload.title?.trim()) {
    errorMessage.value = '任务标题不能为空。'
    return
  }
  if (isSaving.value) return

  isSaving.value = true
  errorMessage.value = ''
  try {
    const updated = await updateTaskWithConflict(task, payload, confirmScheduleConflict)
    if (!updated) return
    editingTask.value = updated
    isEditDialogOpen.value = false
    await loadReview()
    ElMessage.success('任务已更新')
  } catch (error) {
    errorMessage.value = reviewLoadError(error)
  } finally {
    isSaving.value = false
  }
}

async function refreshAfterEditorChange(task?: Task): Promise<void> {
  if (task) editingTask.value = task
  await loadReview({ preserveData: true })
}

function openProject(project: ReviewProject): void {
  window.location.hash = `#project:${project.id}`
}

function projectStatusLabel(project: ReviewProject): string {
  return project.status === 'completed' ? '已完成' : '进行中'
}

function latestCompletionLabel(project: ReviewProject): string {
  if (!project.latest_completed_at_utc) return ''
  return `最近保留完成：${formatReminderTime(project.latest_completed_at_utc, reviewData.value?.local_timezone ?? runtimeTimezone.value)}`
}

function tasksFor(section: ReviewTaskSection): Task[] {
  return reviewData.value?.[section].tasks ?? []
}

onMounted(() => void loadReview())
</script>

<template>
  <header class="page-header review-page-header">
    <div>
      <p class="eyebrow">回顾</p>
      <h2>日常回顾</h2>
      <p class="muted">看看最近完成了什么，以及当前需要关注的事项。</p>
    </div>
    <div class="page-header-actions">
      <button
        class="review-refresh-button"
        type="button"
        :disabled="isLoading"
        :aria-label="isLoading ? '正在刷新回顾' : '刷新回顾'"
        @click="retryReview"
      >
        {{ isLoading ? '刷新中…' : '刷新' }}
      </button>
    </div>
  </header>

  <section class="review-scope-panel" aria-label="回顾范围">
    <div class="review-scope-copy">
      <span class="eyebrow">查看范围</span>
      <strong>{{ scopeLabel }}</strong>
    </div>
    <div class="review-scope-switch" role="group" aria-label="选择回顾范围">
      <button
        class="review-scope-button"
        :class="{ 'is-active': scope === 'today' }"
        type="button"
        :aria-pressed="scope === 'today'"
        :disabled="isLoading"
        @click="selectScope('today')"
      >今天</button>
      <button
        class="review-scope-button"
        :class="{ 'is-active': scope === 'week' }"
        type="button"
        :aria-pressed="scope === 'week'"
        :disabled="isLoading"
        @click="selectScope('week')"
      >本周</button>
    </div>
  </section>

  <p v-if="isLoading && reviewData" class="review-loading-note" aria-live="polite">正在加载回顾…</p>

  <section v-if="loadState === 'loading'" class="today-state is-loading review-state" aria-live="polite" aria-busy="true">
    <p class="eyebrow">加载中</p>
    <h3>正在加载回顾…</h3>
    <p class="today-state-detail">正在读取完成情况和需要关注的事项。</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error review-state" role="alert">
    <p class="eyebrow">回顾暂不可用</p>
    <h3>回顾加载失败</h3>
    <p class="today-state-detail">{{ errorMessage }}</p>
    <button class="review-primary-button" type="button" :disabled="isLoading" @click="retryReview">重试</button>
  </section>

  <template v-else-if="reviewData">
    <div v-if="errorMessage" class="review-error-banner" role="alert">
      <span>{{ errorMessage }} 当前显示的内容可能未更新。</span>
      <button type="button" :disabled="isLoading" @click="retryReview">重试</button>
    </div>

    <section class="review-summary-card" aria-labelledby="review-summary-title">
      <div>
        <p class="eyebrow">完成情况</p>
        <h3 id="review-summary-title">{{ scopeLabel }}完成了 {{ reviewData.completed.count }} 项任务</h3>
        <p class="review-summary-note">回顾基于当前保留的任务状态。</p>
      </div>
      <strong class="review-summary-count" aria-label="完成任务数量">{{ reviewData.completed.count }}</strong>
    </section>

    <section class="review-section" aria-labelledby="review-completed-title">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">完成记录</p>
          <h3 id="review-completed-title">{{ scopeLabel }}完成的任务</h3>
        </div>
        <span class="review-count-badge">{{ reviewData.completed.count }}</span>
      </div>
      <p v-if="reviewData.completed.tasks.length === 0" class="review-empty" role="status">{{ completedEmptyLabel }}</p>
      <div v-else class="review-task-list">
        <ReviewTaskItem
          v-for="task in tasksFor('completed')"
          :key="task.id"
          :task="task"
          section="completed"
          :timezone="reviewData.local_timezone"
          @open="openTask"
        />
      </div>
    </section>

    <section class="review-section review-attention" aria-labelledby="review-attention-title">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">下一步</p>
          <h3 id="review-attention-title">需要关注</h3>
        </div>
      </div>
      <div class="review-attention-grid">
        <section class="review-subsection" aria-labelledby="review-overdue-title">
          <div class="review-subsection-heading">
            <div>
              <h4 id="review-overdue-title">逾期任务</h4>
              <p>仍未完成且已超过截止时间。</p>
            </div>
            <span class="review-count-badge is-danger">{{ reviewData.overdue.count }}</span>
          </div>
          <p v-if="reviewData.overdue.tasks.length === 0" class="review-empty">目前没有逾期任务</p>
          <div v-else class="review-task-list">
            <ReviewTaskItem
              v-for="task in tasksFor('overdue')"
              :key="task.id"
              :task="task"
              section="overdue"
              :timezone="reviewData.local_timezone"
              @open="openTask"
            />
          </div>
        </section>

        <section class="review-subsection" aria-labelledby="review-carryover-title">
          <div class="review-subsection-heading">
            <div>
              <h4 id="review-carryover-title">遗留任务</h4>
              <p>之前计划但仍未完成。</p>
            </div>
            <span class="review-count-badge is-warning">{{ reviewData.carryover.count }}</span>
          </div>
          <p v-if="reviewData.carryover.tasks.length === 0" class="review-empty">没有需要处理的遗留任务</p>
          <div v-else class="review-task-list">
            <ReviewTaskItem
              v-for="task in tasksFor('carryover')"
              :key="task.id"
              :task="task"
              section="carryover"
              :timezone="reviewData.local_timezone"
              @open="openTask"
            />
          </div>
        </section>
      </div>
    </section>

    <section class="review-section" aria-labelledby="review-projects-title">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">当前快照</p>
          <h3 id="review-projects-title">项目回顾</h3>
        </div>
        <span class="review-count-badge">{{ reviewData.projects.length }}</span>
      </div>
      <p v-if="reviewData.projects.length === 0" class="review-empty" role="status">暂无项目</p>
      <div v-else class="review-project-list">
        <article v-for="project in reviewData.projects" :key="project.id" class="review-project-card">
          <button
            class="review-project-button"
            type="button"
            :aria-label="`打开项目：${project.name}`"
            @click="openProject(project)"
          >
            <span class="review-project-heading">
              <span class="review-project-name" :title="project.name">{{ project.name }}</span>
              <span class="review-project-status">{{ projectStatusLabel(project) }}</span>
            </span>
            <span class="review-project-progress-row">
              <span>项目进度</span>
              <strong>{{ project.progress_percent }}%</strong>
            </span>
            <progress
              class="review-project-progress"
              :value="project.progress_percent"
              max="100"
              :aria-label="`${project.name}项目进度 ${project.progress_percent}%`"
            >{{ project.progress_percent }}%</progress>
            <span class="review-project-meta">
              {{ project.task_count }} 个任务 · {{ project.completed_task_count }} 个完成 · {{ project.pending_task_count }} 个待完成
              <template v-if="project.overdue_task_count"> · {{ project.overdue_task_count }} 个逾期</template>
            </span>
            <span v-if="latestCompletionLabel(project)" class="review-project-meta">{{ latestCompletionLabel(project) }}</span>
          </button>
        </article>
      </div>
    </section>
  </template>

  <TaskEditor
    :open="isEditDialogOpen"
    :task="editingTask"
    :categories="categories"
    :tags="tags"
    :projects="projects"
    :runtime-timezone="runtimeTimezone"
    :saving="isSaving"
    :save-error="errorMessage"
    @update:open="isEditDialogOpen = $event"
    @submit="saveTask"
    @changed="refreshAfterEditorChange"
  />
</template>
