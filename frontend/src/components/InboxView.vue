<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { taskApi } from '../api'
import { getTaskErrorMessage } from '../constants/labels'
import { updateTaskWithConflict } from '../taskSave'
import type { Category, Tag, Task, TaskPriority, TaskUpdatePayload } from '../types'
import MetadataManager from './MetadataManager.vue'
import TaskCard from './TaskCard.vue'
import TaskEditor from './TaskEditor.vue'

type InboxLoadState = 'loading' | 'loaded' | 'error'

const props = defineProps<{ searchOnly?: boolean }>()

const loadState = ref<InboxLoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const tasks = ref<Task[]>([])
const searchQuery = ref('')
const priorityFilter = ref<TaskPriority | ''>('')
const categoryFilter = ref('')
const tagFilter = ref('')
const isSearchMode = computed(() => props.searchOnly || searchQuery.value.trim().length > 0)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const metadataLoaded = ref(false)
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)
const runtimeTimezone = ref('')

type RestoreTarget = Pick<Task, 'id' | 'version'>
type MetadataSnapshot = { categories: Category[]; tags: Tag[] }

function getErrorMessage(error: unknown): string {
  return getTaskErrorMessage(error, 'inbox')
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
    errorMessage.value = '请先填写任务标题。'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.create({ title, description: quickDescription.value.trim() || null, planned_date: null })
    quickTitle.value = ''
    quickDescription.value = ''
    await loadTasks()
    ElMessage.success('任务已记录到收件箱')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

const quickTitle = ref('')
const quickDescription = ref('')

async function openEditDialog(task: Task): Promise<void> {
  if (!runtimeTimezone.value) {
    try {
      runtimeTimezone.value = (await taskApi.getRuntime()).timezone
    } catch (error) {
      showError(error)
      return
    }
  }
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

async function saveEdit(payload: TaskUpdatePayload): Promise<void> {
  const task = editingTask.value
  if (!task || !payload.title?.trim()) {
    errorMessage.value = '任务标题不能为空。'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    const updated = await updateTaskWithConflict(task, payload, confirmScheduleConflict)
    if (!updated) return
    isEditDialogOpen.value = false
    await loadTasks()
    ElMessage.success('任务已更新')
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
    ElMessage.success('任务已完成')
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
    ElMessage.success('任务已恢复')
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
      h('span', '任务已删除'),
      h('button', { class: 'delete-undo', type: 'button', onClick: () => void undo() }, '撤销'),
    ]),
    type: 'success',
    duration: 8000,
    showClose: true,
  })
}

async function deleteTask(task: Task): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除“${task.title}”吗？删除后可点击“撤销”恢复。`,
      '删除任务',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
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
      <p class="eyebrow">{{ props.searchOnly ? '搜索' : '收件箱' }}</p>
      <h2>{{ props.searchOnly ? '搜索任务' : '收件箱' }}</h2>
      <p class="muted">
        {{ props.searchOnly ? '按标题或备注查找任务。' : '暂时还没安排日期的任务，可以先放在这里。' }}
      </p>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadTasks">刷新</el-button>
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
    <p class="eyebrow">加载中</p>
    <h3>正在加载收件箱</h3>
    <p class="today-state-detail">正在加载待安排任务…</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">收件箱暂不可用</p>
    <h3>收件箱加载失败</h3>
    <p class="today-state-detail">{{ errorMessage || '收件箱加载失败，请稍后重试。' }}</p>
    <el-button type="primary" :loading="isLoading" @click="initializeInbox">重试</el-button>
  </section>

  <template v-if="loadState === 'loaded'">
    <el-card v-if="!props.searchOnly" shadow="never" class="capture-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">快速记录</p>
          <h3>先记下来，稍后安排</h3>
        </div>
        <span class="capture-hint">可以稍后安排日期</span>
      </div>
      <form class="capture-form" @submit.prevent="createQuickTask">
        <el-input v-model="quickTitle" size="large" placeholder="想先记下什么？" aria-label="新收件箱任务标题" />
        <el-input v-model="quickDescription" placeholder="备注（可选）" aria-label="新收件箱任务备注" />
        <el-button type="primary" native-type="submit" :loading="isSaving">记录</el-button>
      </form>
    </el-card>

    <section class="search-panel">
      <form class="search-form" @submit.prevent="applySearch">
        <el-input v-model="searchQuery" clearable placeholder="搜索标题或备注" aria-label="搜索任务" />
        <el-button native-type="submit" :loading="isLoading">搜索</el-button>
      </form>
      <div class="filter-row">
        <el-select v-model="priorityFilter" clearable placeholder="优先级" @change="loadTasks">
          <el-option label="低" value="low" />
          <el-option label="普通" value="normal" />
          <el-option label="高" value="high" />
        </el-select>
        <el-select v-model="categoryFilter" clearable placeholder="分类" @change="loadTasks">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
        <el-select v-model="tagFilter" clearable placeholder="标签" @change="loadTasks">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </div>
    </section>

    <section class="task-section">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">{{ isSearchMode ? '搜索结果' : '收件箱' }}</p>
          <h3>{{ isSearchMode ? '匹配的任务' : '待安排任务' }}</h3>
        </div>
        <el-tag type="info" effect="plain">{{ tasks.length }}</el-tag>
      </div>

      <el-empty
        v-if="tasks.length === 0"
        :description="isSearchMode ? '没有找到相关任务' : '收件箱为空'"
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
    :runtime-timezone="runtimeTimezone"
    :saving="isSaving"
    @update:open="isEditDialogOpen = $event"
    @submit="saveEdit"
  />
</template>
