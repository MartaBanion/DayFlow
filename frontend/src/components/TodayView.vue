<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { taskApi } from '../api'
import { getTaskErrorMessage } from '../constants/labels'
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
  return getTaskErrorMessage(error, 'today')
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
    errorMessage.value = '请先填写任务标题。'
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
    ElMessage.success('任务已创建')
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
    errorMessage.value = '任务标题不能为空。'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.update(task.id, task.version, payload)
    isEditDialogOpen.value = false
    await loadToday()
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
    await loadToday()
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
    await loadToday()
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
    if (await restoreTask(task)) {
      messageHandler?.close()
    }
  }

  messageHandler = ElMessage({
    message: h('span', { class: 'delete-message' }, [
      h('span', '任务已删除'),
      h(
        'button',
        {
          class: 'delete-undo',
          type: 'button',
          onClick: () => void undo(),
        },
        '撤销',
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
      <p class="eyebrow">今天</p>
      <h2>{{ formattedDate }}</h2>
      <p class="muted">清晰查看今天最值得关注的事项。</p>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadToday">刷新</el-button>
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
    <p class="eyebrow">加载中</p>
    <h3>正在加载今天</h3>
    <p class="today-state-detail">正在加载今日任务…</p>
  </section>

  <section v-else-if="todayLoadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">今天暂不可用</p>
    <h3>今日任务加载失败</h3>
    <p class="today-state-detail">
      {{ errorMessage || '今日任务加载失败，请稍后重试。' }}
    </p>
    <el-button type="primary" :loading="isLoading" @click="loadToday">重试</el-button>
  </section>

  <section v-if="todayLoadState === 'loaded'" class="summary-grid" aria-label="今日概览">
    <el-card shadow="never" class="summary-card">
      <div class="summary-content">
        <span class="summary-label">任务</span>
        <strong class="summary-value">{{ tasks.length }}</strong>
        <span class="summary-detail">{{ pendingTasks.length }} 待完成</span>
      </div>
    </el-card>
    <el-card shadow="never" class="summary-card">
      <div class="summary-content">
        <span class="summary-label">完成率</span>
        <strong class="summary-value">{{ completionRate }}%</strong>
        <span class="summary-detail">保持下一步清晰可见</span>
      </div>
    </el-card>
  </section>

  <el-card shadow="never" class="capture-card">
    <div class="section-heading">
      <div>
        <p class="eyebrow">快速记录</p>
        <h3>添加今天要做的事</h3>
      </div>
      <span class="capture-hint">按回车创建</span>
    </div>
    <form class="capture-form" @submit.prevent="createQuickTask">
      <el-input v-model="quickTitle" size="large" placeholder="有什么需要关注的事？" aria-label="新任务标题" />
      <el-input v-model="quickDescription" placeholder="备注（可选）" aria-label="新任务备注" />
      <el-button type="primary" native-type="submit" :loading="isSaving">添加任务</el-button>
    </form>
  </el-card>

  <section v-if="todayLoadState === 'loaded'" class="task-section">
    <div class="section-heading task-heading">
      <div>
        <p class="eyebrow">今日计划</p>
        <h3>今日任务</h3>
      </div>
      <el-tag v-if="pendingTasks.length" type="success" effect="plain">
        {{ pendingTasks.length }} 待完成
      </el-tag>
    </div>

    <el-empty v-if="tasks.length === 0" description="今天还没有安排任务">
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
