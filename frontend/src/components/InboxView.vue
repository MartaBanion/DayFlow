<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError, taskApi } from '../api'
import type { Category, Tag, Task, TaskPriority, TaskUpdatePayload } from '../types'
import MetadataManager from './MetadataManager.vue'
import TaskCard from './TaskCard.vue'
import TaskEditor from './TaskEditor.vue'

type InboxLoadState = 'loading' | 'loaded' | 'error'

const loadState = ref<InboxLoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const tasks = ref<Task[]>([])
const searchQuery = ref('')
const priorityFilter = ref<TaskPriority | ''>('')
const categoryFilter = ref('')
const tagFilter = ref('')
const isSearchMode = computed(() => searchQuery.value.trim().length > 0)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const metadataLoaded = ref(false)
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)

type RestoreTarget = Pick<Task, 'id' | 'version'>
type MetadataSnapshot = { categories: Category[]; tags: Tag[] }

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 409) {
      return 'This task changed elsewhere. Refresh the Inbox and try again.'
    }
    return error.message
  }
  return 'DayFlow could not complete that action. Check that the Backend is running.'
}

function showError(error: unknown): void {
  errorMessage.value = getErrorMessage(error)
}

async function loadTasks(): Promise<void> {
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    tasks.value = await taskApi.list({
      inbox: !isSearchMode.value,
      query: searchQuery.value.trim() || undefined,
      priority: priorityFilter.value || undefined,
      categoryId: categoryFilter.value || undefined,
      tagId: tagFilter.value || undefined,
    })
    loadState.value = 'loaded'
  } catch (error) {
    loadState.value = 'error'
    showError(error)
  } finally {
    isLoading.value = false
  }
}

async function loadMetadata(): Promise<void> {
  if (metadataLoaded.value) return
  const [loadedCategories, loadedTags] = await Promise.all([
    taskApi.listCategories(),
    taskApi.listTags(),
  ])
  categories.value = loadedCategories
  tags.value = loadedTags
  metadataLoaded.value = true
}

async function handleMetadataUpdated(snapshot: MetadataSnapshot): Promise<void> {
  categories.value = snapshot.categories
  tags.value = snapshot.tags
  if (loadState.value === 'loaded') await loadTasks()
}

async function initializeInbox(): Promise<void> {
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    await loadMetadata()
    tasks.value = await taskApi.list({
      inbox: !isSearchMode.value,
      query: searchQuery.value.trim() || undefined,
      priority: priorityFilter.value || undefined,
      categoryId: categoryFilter.value || undefined,
      tagId: tagFilter.value || undefined,
    })
    loadState.value = 'loaded'
  } catch (error) {
    loadState.value = 'error'
    showError(error)
  } finally {
    isLoading.value = false
  }
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
    await taskApi.create({ title, description: quickDescription.value.trim() || null, planned_date: null })
    quickTitle.value = ''
    quickDescription.value = ''
    await loadTasks()
    ElMessage.success('Task captured in Inbox')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

const quickTitle = ref('')
const quickDescription = ref('')

async function openEditDialog(task: Task): Promise<void> {
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
    await loadTasks()
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
    await loadTasks()
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
    await loadTasks()
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
    if (await restoreTask(task)) messageHandler?.close()
  }

  messageHandler = ElMessage({
    message: h('span', { class: 'delete-message' }, [
      h('span', 'Task deleted'),
      h('button', { class: 'delete-undo', type: 'button', onClick: () => void undo() }, 'Undo'),
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
    await loadTasks()
    showDeleteUndo({ id: task.id, version: task.version + 1 })
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function applySearch(): Promise<void> {
  await loadTasks()
}

onMounted(initializeInbox)
</script>

<template>
  <header class="page-header">
    <div>
      <p class="eyebrow">INBOX</p>
      <h2>Unscheduled tasks</h2>
      <p class="muted">Capture first, decide when it belongs later.</p>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadTasks">Refresh</el-button>
    </div>
  </header>

  <el-alert
    v-if="errorMessage && loadState !== 'error'"
    class="page-alert"
    :title="errorMessage"
    type="error"
    show-icon
    closable
    @close="errorMessage = ''"
  />

  <section v-if="loadState === 'loading'" class="today-state is-loading" aria-live="polite">
    <p class="eyebrow">LOADING</p>
    <h3>Loading Inbox</h3>
    <p class="today-state-detail">Loading unscheduled tasks…</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">INBOX UNAVAILABLE</p>
    <h3>Could not load Inbox</h3>
    <p class="today-state-detail">{{ errorMessage || 'DayFlow could not load Inbox.' }}</p>
    <el-button type="primary" :loading="isLoading" @click="initializeInbox">Retry</el-button>
  </section>

  <template v-if="loadState === 'loaded'">
    <el-card shadow="never" class="capture-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">QUICK CAPTURE</p>
          <h3>Save it for later</h3>
        </div>
        <span class="capture-hint">No date required</span>
      </div>
      <form class="capture-form" @submit.prevent="createQuickTask">
        <el-input v-model="quickTitle" size="large" placeholder="What should you remember?" aria-label="New Inbox task title" />
        <el-input v-model="quickDescription" placeholder="Optional note" aria-label="New Inbox task description" />
        <el-button type="primary" native-type="submit" :loading="isSaving">Capture</el-button>
      </form>
    </el-card>

    <section class="search-panel">
      <form class="search-form" @submit.prevent="applySearch">
        <el-input v-model="searchQuery" clearable placeholder="Search title or description" aria-label="Search tasks" />
        <el-button native-type="submit" :loading="isLoading">Search</el-button>
      </form>
      <div class="filter-row">
        <el-select v-model="priorityFilter" clearable placeholder="Priority" @change="loadTasks">
          <el-option label="Low" value="low" />
          <el-option label="Normal" value="normal" />
          <el-option label="High" value="high" />
        </el-select>
        <el-select v-model="categoryFilter" clearable placeholder="Category" @change="loadTasks">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
        <el-select v-model="tagFilter" clearable placeholder="Tag" @change="loadTasks">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </div>
    </section>

    <section class="task-section">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">{{ isSearchMode ? 'SEARCH RESULTS' : 'INBOX' }}</p>
          <h3>{{ isSearchMode ? 'Matching tasks' : 'Unscheduled tasks' }}</h3>
        </div>
        <el-tag type="info" effect="plain">{{ tasks.length }}</el-tag>
      </div>

      <el-empty
        v-if="tasks.length === 0"
        :description="isSearchMode ? 'No tasks match your search' : 'Your Inbox is clear'"
      >
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
  </template>

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
