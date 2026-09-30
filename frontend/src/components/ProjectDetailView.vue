<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { projectApi, recurrenceApi, taskApi } from '../api'
import { getFeatureErrorMessage, getProjectErrorMessage, getProjectLoadErrorMessage } from '../constants/labels'
import { createTaskWithConflict, updateTaskWithConflict } from '../taskSave'
import type {
  Category,
  Project,
  Tag,
  Task,
  TaskCreatePayload,
  TaskUpdatePayload,
} from '../types'
import TaskCard from './TaskCard.vue'
import TaskEditor from './TaskEditor.vue'

type LoadState = 'loading' | 'loaded' | 'error'
type RestoreTarget = Pick<Task, 'id' | 'version'>

const props = defineProps<{ projectId: string }>()

const project = ref<Project | null>(null)
const tasks = ref<Task[]>([])
const loadState = ref<LoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const isEditorOpen = ref(false)
const editingTask = ref<Task | null>(null)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const projects = ref<Project[]>([])
const metadataLoaded = ref(false)
const runtimeTimezone = ref('')

function showProjectList(): void {
  window.location.hash = '#projects'
}

function showError(error: unknown): void {
  errorMessage.value = getProjectErrorMessage(error)
}

async function loadProject(): Promise<void> {
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    const [loadedProject, loadedTasks] = await Promise.all([
      projectApi.get(props.projectId),
      taskApi.list({ projectId: props.projectId }),
    ])
    project.value = loadedProject
    tasks.value = loadedTasks
    loadState.value = 'loaded'
  } catch (error) {
    loadState.value = 'error'
    errorMessage.value = getProjectLoadErrorMessage(error)
  } finally {
    isLoading.value = false
  }
}

async function loadMetadata(): Promise<boolean> {
  if (metadataLoaded.value) return true
  try {
    const [loadedCategories, loadedTags, loadedProjects, runtime] = await Promise.all([
      taskApi.listCategories(),
      taskApi.listTags(),
      projectApi.list(),
      taskApi.getRuntime(),
    ])
    categories.value = loadedCategories
    tags.value = loadedTags
    projects.value = loadedProjects
    runtimeTimezone.value = runtime.timezone
    metadataLoaded.value = true
    return true
  } catch (error) {
    showError(error)
    return false
  }
}

async function openCreateTask(): Promise<void> {
  if (!(await loadMetadata()) || !project.value) return
  editingTask.value = null
  isEditorOpen.value = true
}

async function openEditTask(task: Task): Promise<void> {
  if (!(await loadMetadata())) return
  editingTask.value = task
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
        project_id:
          payload.project_id === undefined
            ? project.value?.id ?? null
            : payload.project_id,
        schedule: payload.schedule,
        deadline: payload.deadline,
      }
      saved = await createTaskWithConflict(createPayload, confirmScheduleConflict)
    }
    if (!saved) return
    isEditorOpen.value = false
    await loadProject()
    ElMessage.success(editingTask.value ? '任务已更新' : '任务已创建')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function completeTask(task: Task): Promise<void> {
  isSaving.value = true
  try {
    await taskApi.complete(task.id, task.version)
    await loadProject()
    ElMessage.success('任务已完成')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function skipTask(task: Task): Promise<void> {
  if (!task.recurrence_rule_id) return
  isSaving.value = true
  try {
    await recurrenceApi.skip(task.id, task.version)
    await loadProject()
    ElMessage.success('本次任务已跳过，下一次任务已准备好')
  } catch (error) {
    errorMessage.value = getFeatureErrorMessage(error, '跳过本次任务')
  } finally {
    isSaving.value = false
  }
}

async function restoreTask(task: RestoreTarget): Promise<void> {
  isSaving.value = true
  try {
    await taskApi.restore(task.id, task.version)
    await loadProject()
    ElMessage.success('任务已恢复')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function deleteTask(task: Task): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除“${task.title}”吗？删除后可通过撤销恢复。`,
      '删除任务',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  isSaving.value = true
  try {
    await taskApi.remove(task.id, task.version)
    await loadProject()
    ElMessage.success('任务已删除')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

onMounted(loadProject)
</script>

<template>
  <header class="page-header project-detail-header">
    <div>
      <button class="back-link" type="button" @click="showProjectList">‹ 返回项目</button>
      <p class="eyebrow">项目详情</p>
      <h2>{{ project?.name || '项目' }}</h2>
      <p v-if="project?.description" class="muted">{{ project.description }}</p>
    </div>
    <div class="page-header-actions">
      <el-button plain :loading="isLoading" @click="loadProject">刷新</el-button>
      <el-button type="primary" :disabled="!project" @click="openCreateTask">新建任务</el-button>
    </div>
  </header>

  <section v-if="loadState === 'loading'" class="today-state is-loading" aria-live="polite">
    <p class="eyebrow">加载中</p>
    <h3>正在加载项目详情</h3>
    <p class="today-state-detail">正在读取项目任务…</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">项目暂不可用</p>
    <h3>项目详情加载失败</h3>
    <p class="today-state-detail">{{ errorMessage }}</p>
    <el-button type="primary" :loading="isLoading" @click="loadProject">重试</el-button>
  </section>

  <template v-else-if="project">
    <el-alert
      v-if="errorMessage"
      class="page-alert"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      @close="errorMessage = ''"
    />

    <section class="project-detail-summary">
      <div class="project-detail-status-row">
        <el-tag :type="project.status === 'completed' ? 'success' : 'info'" effect="plain">
          {{ project.status === 'completed' ? '已完成' : '进行中' }}
        </el-tag>
        <span>{{ project.completed_task_count }} / {{ project.task_count }} 个任务已完成</span>
        <strong>{{ project.progress_percent }}%</strong>
      </div>
      <el-progress :percentage="project.progress_percent" :stroke-width="10" />
    </section>

    <section class="task-section project-task-section">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">项目任务</p>
          <h3>关联任务</h3>
        </div>
        <el-tag type="info" effect="plain">{{ tasks.length }}</el-tag>
      </div>
      <el-empty v-if="tasks.length === 0" description="这个项目还没有任务">
        <el-button type="primary" @click="openCreateTask">新建任务</el-button>
      </el-empty>
      <div v-else class="task-list">
        <TaskCard
          v-for="task in tasks"
          :key="task.id"
          :task="task"
          @complete="completeTask"
          @restore="restoreTask"
          @edit="openEditTask"
          @delete="deleteTask"
          @skip="skipTask"
        />
      </div>
    </section>
  </template>

  <TaskEditor
    :open="isEditorOpen"
    :task="editingTask"
    :categories="categories"
    :tags="tags"
    :projects="projects"
    :initial-project-id="project?.id"
    :runtime-timezone="runtimeTimezone"
    :saving="isSaving"
    @update:open="isEditorOpen = $event"
    @submit="saveTask"
    @changed="loadProject"
  />
</template>
