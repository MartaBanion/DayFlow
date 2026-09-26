<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError, taskApi } from '../api'
import { calculateCompletionRate, formatDisplayDate, toDateInputValue } from '../date'
import type { Category, Tag, Task, TaskUpdatePayload } from '../types'
import MetadataManager from './MetadataManager.vue'
import TaskCard from './TaskCard.vue'
import TaskEditor from './TaskEditor.vue'

const selectedDate = ref(toDateInputValue(new Date()))
const tasks = ref<Task[]>([])
type TodayLoadState = 'loading' | 'loaded' | 'error'

const todayLoadState = ref<TodayLoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const quickTitle = ref('')
const quickDescription = ref('')
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const metadataLoaded = ref(false)

const pendingTasks = computed(() => tasks.value.filter((task) => task.status === 'pending'))
const completionRate = computed(() => calculateCompletionRate(tasks.value))
const formattedDate = computed(() => formatDisplayDate(selectedDate.value))

type RestoreTarget = Pick<Task, 'id' | 'version'>
type MetadataSnapshot = { categories: Category[]; tags: Tag[] }

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 409) {
      return 'This task changed elsewhere. Refresh the Today list and try again.'
    }
    return error.message
  }
  return 'DayFlow could not complete that action. Check that the Backend is running.'
}

function showError(error: unknown): void {
  errorMessage.value = getErrorMessage(error)
}

async function loadToday(): Promise<void> {
  todayLoadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    tasks.value = await taskApi.listToday(selectedDate.value)
    todayLoadState.value = 'loaded'
  } catch (error) {
    todayLoadState.value = 'error'
    showError(error)
  } finally {
    isLoading.value = false
  }
}

async function loadMetadata(): Promise<void> {
  if (metadataLoaded.value) return
  try {
    const [loadedCategories, loadedTags] = await Promise.all([
      taskApi.listCategories(),
      taskApi.listTags(),
    ])
    categories.value = loadedCategories
    tags.value = loadedTags
    metadataLoaded.value = true
  } catch (error) {
    showError(error)
  }
}

async function handleMetadataUpdated(snapshot: MetadataSnapshot): Promise<void> {
  categories.value = snapshot.categories
  tags.value = snapshot.tags
  if (todayLoadState.value === 'loaded') await loadToday()
}

async function createQuickTask(): Promise<void> {
  const title = quickTitle.value.trim()
  if (!title) {
    errorMessage.value = 'Add a title before creating a task.'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.create({
      title,
      description: quickDescription.value.trim() || null,
      planned_date: selectedDate.value,
    })
    quickTitle.value = ''
    quickDescription.value = ''
    await loadToday()
    ElMessage.success('Task created')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function openEditDialog(task: Task): Promise<void> {
  await loadMetadata()
  editingTask.value = task
  isEditDialogOpen.value = true
}

async function saveEdit(payload: TaskUpdatePayload): Promise<void> {
  const task = editingTask.value
  if (!task || !payload.title?.trim()) {
    errorMessage.value = 'Task title cannot be empty.'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.update(task.id, task.version, payload)
    isEditDialogOpen.value = false
    await loadToday()
    ElMessage.success('Task updated')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function completeTask(task: Task): Promise<void> {
  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.complete(task.id, task.version)
    await loadToday()
    ElMessage.success('Task completed')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function restoreTask(task: RestoreTarget): Promise<boolean> {
  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.restore(task.id, task.version)
    await loadToday()
    ElMessage.success('Task restored')
    return true
  } catch (error) {
    showError(error)
    return false
  } finally {
    isSaving.value = false
  }
}

function showDeleteUndo(task: RestoreTarget): void {
  let messageHandler: ReturnType<typeof ElMessage> | undefined
  const undo = async (): Promise<void> => {
    if (await restoreTask(task)) {
      messageHandler?.close()
    }
  }

  messageHandler = ElMessage({
    message: h('span', { class: 'delete-message' }, [
      h('span', 'Task deleted'),
      h(
        'button',
        {
          class: 'delete-undo',
          type: 'button',
          onClick: () => void undo(),
        },
        'Undo',
      ),
    ]),
    type: 'success',
    duration: 8000,
    showClose: true,
  })
}

async function deleteTask(task: Task): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Delete “${task.title}”? You can undo this from the confirmation message.`,
      'Delete task',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.remove(task.id, task.version)
    await loadToday()
    showDeleteUndo({ id: task.id, version: task.version + 1 })
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

onMounted(loadToday)
</script>

<template>
  <header class="page-header">
    <div>
      <p class="eyebrow">TODAY</p>
      <h2>{{ formattedDate }}</h2>
      <p class="muted">A calm view of what deserves your attention.</p>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadToday">Refresh</el-button>
    </div>
  </header>

  <el-alert
    v-if="errorMessage && todayLoadState !== 'error'"
    class="page-alert"
    :title="errorMessage"
    type="error"
    show-icon
    closable
    @close="errorMessage = ''"
  />

  <section v-if="todayLoadState === 'loading'" class="today-state is-loading" aria-live="polite">
    <p class="eyebrow">LOADING</p>
    <h3>Loading today</h3>
    <p class="today-state-detail">Loading today’s tasks…</p>
  </section>

  <section v-else-if="todayLoadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">TODAY UNAVAILABLE</p>
    <h3>Could not load today</h3>
    <p class="today-state-detail">
      {{ errorMessage || 'DayFlow could not load today’s tasks.' }}
    </p>
    <el-button type="primary" :loading="isLoading" @click="loadToday">Retry</el-button>
  </section>

  <section v-if="todayLoadState === 'loaded'" class="summary-grid" aria-label="Today summary">
    <el-card shadow="never" class="summary-card">
      <div class="summary-content">
        <span class="summary-label">Tasks</span>
        <strong class="summary-value">{{ tasks.length }}</strong>
        <span class="summary-detail">{{ pendingTasks.length }} still open</span>
      </div>
    </el-card>
    <el-card shadow="never" class="summary-card">
      <div class="summary-content">
        <span class="summary-label">Completion</span>
        <strong class="summary-value">{{ completionRate }}%</strong>
        <span class="summary-detail">Keep the next step visible</span>
      </div>
    </el-card>
  </section>

  <el-card shadow="never" class="capture-card">
    <div class="section-heading">
      <div>
        <p class="eyebrow">QUICK CAPTURE</p>
        <h3>Add something to today</h3>
      </div>
      <span class="capture-hint">Enter to create</span>
    </div>
    <form class="capture-form" @submit.prevent="createQuickTask">
      <el-input v-model="quickTitle" size="large" placeholder="What needs your attention?" aria-label="New task title" />
      <el-input v-model="quickDescription" placeholder="Optional note" aria-label="New task description" />
      <el-button type="primary" native-type="submit" :loading="isSaving">Add task</el-button>
    </form>
  </el-card>

  <section v-if="todayLoadState === 'loaded'" class="task-section">
    <div class="section-heading task-heading">
      <div>
        <p class="eyebrow">YOUR PLAN</p>
        <h3>Today’s tasks</h3>
      </div>
      <el-tag v-if="pendingTasks.length" type="success" effect="plain">
        {{ pendingTasks.length }} open
      </el-tag>
    </div>

    <el-empty v-if="tasks.length === 0" description="Nothing planned for this day">
      <template #image>
        <div class="empty-mark">✓</div>
      </template>
    </el-empty>

    <div v-else class="task-list">
      <TaskCard
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        @complete="completeTask"
        @restore="restoreTask"
        @edit="openEditDialog"
        @delete="deleteTask"
      />
    </div>
  </section>

  <TaskEditor
    :open="isEditDialogOpen"
    :task="editingTask"
    :categories="categories"
    :tags="tags"
    :saving="isSaving"
    @update:open="isEditDialogOpen = $event"
    @submit="saveEdit"
  />
</template>
