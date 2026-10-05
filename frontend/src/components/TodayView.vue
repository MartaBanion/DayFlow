<script setup lang="ts">
import { computed, h, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { projectApi, recurrenceApi, taskApi } from '../api'
import { getFeatureErrorMessage, getTaskErrorMessage } from '../constants/labels'
import { calculateCompletionRate, formatDisplayDate } from '../date'
import { updateTaskWithConflict } from '../taskSave'
import type { Category, Project, Tag, Task, TaskUpdatePayload } from '../types'
import MetadataManager from './MetadataManager.vue'
import TaskCard from './TaskCard.vue'
import TaskEditor from './TaskEditor.vue'

const selectedDate = ref('')
const runtimeTimezone = ref('')
const tasks = ref<Task[]>([])
type TodayLoadState = 'loading' | 'loaded' | 'error'

const todayLoadState = ref<TodayLoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const quickTitle = ref('')
const quickDescription = ref('')
const quickNotesOpen = ref(false)
const quickInput = ref<{ focus: () => void } | null>(null)
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const projects = ref<Project[]>([])
const metadataLoaded = ref(false)
const hasStaleTasks = ref(false)
let requestSequence = 0

const pendingTasks = computed(() => tasks.value.filter((task) => task.status === 'pending'))
const completionRate = computed(() => calculateCompletionRate(tasks.value))
const formattedDate = computed(() => selectedDate.value ? formatDisplayDate(selectedDate.value) : '今天')

type RestoreTarget = Pick<Task, 'id' | 'version'>
type MetadataSnapshot = { categories: Category[]; tags: Tag[] }

function getErrorMessage(error: unknown): string {
  return getTaskErrorMessage(error, 'today')
}

function showError(error: unknown): void {
  errorMessage.value = getErrorMessage(error)
}

async function loadToday(preserveList = false): Promise<void> {
  if (!selectedDate.value) return
  const requestId = ++requestSequence
  if (!preserveList) todayLoadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    const loadedTasks = await taskApi.listToday(selectedDate.value)
    if (requestId !== requestSequence) return
    tasks.value = loadedTasks
    todayLoadState.value = 'loaded'
    hasStaleTasks.value = false
  } catch (error) {
    if (requestId !== requestSequence) return
    showError(error)
    if (preserveList && todayLoadState.value === 'loaded') {
      hasStaleTasks.value = true
    } else {
      todayLoadState.value = 'error'
    }
  } finally {
    if (requestId === requestSequence) isLoading.value = false
  }
}

async function initializeToday(): Promise<void> {
  todayLoadState.value = 'loading'
  errorMessage.value = ''
  try {
    const runtime = await taskApi.getRuntime()
    runtimeTimezone.value = runtime.timezone
    selectedDate.value = runtime.local_date
    await loadToday()
  } catch (error) {
    todayLoadState.value = 'error'
    showError(error)
  }
}

async function retryToday(): Promise<void> {
  if (selectedDate.value) {
    await loadToday()
  } else {
    await initializeToday()
  }
}

async function loadMetadata(): Promise<void> {
  if (metadataLoaded.value) return
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
  } catch (error) {
    showError(error)
  }
}

async function handleMetadataUpdated(snapshot: MetadataSnapshot): Promise<void> {
  categories.value = snapshot.categories
  tags.value = snapshot.tags
  if (todayLoadState.value === 'loaded') await loadToday(true)
}

async function handleRescheduled(): Promise<void> {
  await loadToday(true)
}

async function createQuickTask(): Promise<void> {
  if (isSaving.value) return
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
    await loadToday(true)
    ElMessage.success('任务已创建')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
    await nextTick()
    quickInput.value?.focus()
  }
}

async function openEditDialog(task: Task): Promise<void> {
  await loadMetadata()
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

async function skipTask(task: Task): Promise<void> {
  if (!task.recurrence_rule_id) return
  isSaving.value = true
  errorMessage.value = ''
  try {
    await recurrenceApi.skip(task.id, task.version)
    await loadToday()
    ElMessage.success('本次任务已跳过，下一次任务已准备好')
  } catch (error) {
    errorMessage.value = getFeatureErrorMessage(error, '跳过本次任务')
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

onMounted(initializeToday)
</script>

<template>
  <header class="page-header">
    <div>
      <p class="eyebrow">今天</p>
      <h2>{{ formattedDate }}</h2>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadToday(true)">刷新</el-button>
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
  >
    <template v-if="hasStaleTasks">当前今日任务结果可能未更新，请点击刷新重试。</template>
  </el-alert>

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
    <el-button type="primary" :loading="isLoading" @click="retryToday">重试</el-button>
  </section>

  <section v-if="todayLoadState === 'loaded'" class="summary-grid summary-compact" aria-label="今日概览">
    <div class="today-overview">
      <div><span>任务</span><strong>{{ tasks.length }}</strong></div>
      <div><span>待完成</span><strong>{{ pendingTasks.length }}</strong></div>
      <div><span>完成率</span><strong>{{ completionRate }}%</strong></div>
    </div>
  </section>

  <el-card shadow="never" class="capture-card">
    <div class="section-heading">
      <div>
        <h3>添加今天要做的事</h3>
      </div>
      <span class="capture-hint">按回车创建</span>
    </div>
    <form class="capture-form" @submit.prevent="createQuickTask">
      <el-input ref="quickInput" v-model="quickTitle" size="large" placeholder="有什么需要关注的事？" aria-label="新任务标题" />
      <el-button text native-type="button" :aria-expanded="quickNotesOpen" @click="quickNotesOpen = !quickNotesOpen">{{ quickNotesOpen ? '收起备注' : '添加备注' }}</el-button>
      <el-button type="primary" native-type="submit" :loading="isSaving">添加任务</el-button>
      <el-input v-show="quickNotesOpen" v-model="quickDescription" class="quick-note" placeholder="备注（可选）" aria-label="新任务备注" />
    </form>
  </el-card>

  <section v-if="todayLoadState === 'loaded'" class="task-section">
    <div class="section-heading task-heading">
      <div>
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

    <p v-if="tasks.length && !pendingTasks.length" class="all-completed" role="status">今天的任务已全部完成。</p>

    <div v-if="tasks.length" class="task-list">
      <TaskCard
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        :busy="isSaving"
        :context-date="selectedDate"
        :quick-reschedule-enabled="true"
        :runtime-local-date="selectedDate"
        @complete="completeTask"
        @restore="restoreTask"
        @edit="openEditDialog"
        @delete="deleteTask"
        @skip="skipTask"
        @rescheduled="handleRescheduled"
      />
    </div>
  </section>

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
    @submit="saveEdit"
    @changed="(task) => { if (task) editingTask = task; void loadToday() }"
  />
</template>
