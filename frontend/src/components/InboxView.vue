<script setup lang="ts">
import { computed, h, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { projectApi, recurrenceApi, taskApi } from '../api'
import { getFeatureErrorMessage, getTaskErrorMessage } from '../constants/labels'
import { updateTaskWithConflict } from '../taskSave'
import type {
  Category,
  Project,
  Tag,
  Task,
  TaskListParams,
  TaskPlannedBucket,
  TaskPriority,
  TaskSort,
  TaskStatusFilter,
  TaskUpdatePayload,
} from '../types'
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
const projectFilter = ref('')
const statusFilter = ref<TaskStatusFilter | ''>('')
const overdueFilter = ref(false)
const plannedBucketFilter = ref<TaskPlannedBucket | ''>('')
const sortFilter = ref<TaskSort | ''>('')
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const projects = ref<Project[]>([])
const metadataLoaded = ref(false)
const isEditDialogOpen = ref(false)
const editingTask = ref<Task | null>(null)
const runtimeTimezone = ref('')
const filtersOpen = ref(true)
const staleData = ref(false)
let requestSequence = 0
const hasConditions = computed(() => Boolean(
  searchQuery.value.trim()
  || priorityFilter.value
  || categoryFilter.value
  || tagFilter.value
  || projectFilter.value
  || (props.searchOnly && (
    statusFilter.value
    || overdueFilter.value
    || plannedBucketFilter.value
    || sortFilter.value
  )),
))
const filterSummary = computed(() => [
  priorityFilter.value ? ({ low: '低', normal: '普通', high: '高' }[priorityFilter.value]) : '',
  categories.value.find(category => category.id === categoryFilter.value)?.name,
  tags.value.find(tag => tag.id === tagFilter.value)?.name,
  projects.value.find(project => project.id === projectFilter.value)?.name,
  props.searchOnly && statusFilter.value ? ({ pending: '待完成', completed: '已完成', all: '全部状态' }[statusFilter.value]) : '',
  props.searchOnly && overdueFilter.value ? '仅看逾期' : '',
  props.searchOnly && plannedBucketFilter.value ? ({ unscheduled: '未安排', today: '今天', past: '过去', future: '未来' }[plannedBucketFilter.value]) : '',
  props.searchOnly && sortFilter.value ? ({ default: '默认', planned: '计划日期', deadline: '截止日期', completed: '最近完成' }[sortFilter.value]) : '',
].filter(Boolean).join(' · ') || (props.searchOnly ? '全部未删除任务' : '未安排且待完成'))

async function clearFilters(): Promise<void> {
  searchQuery.value = ''
  priorityFilter.value = ''
  categoryFilter.value = ''
  tagFilter.value = ''
  projectFilter.value = ''
  statusFilter.value = ''
  overdueFilter.value = false
  plannedBucketFilter.value = ''
  sortFilter.value = ''
  await loadTasks(true)
}

function taskListParams(): TaskListParams {
  const params: TaskListParams = {
    inbox: !props.searchOnly,
    query: searchQuery.value.trim() || undefined,
    priority: priorityFilter.value || undefined,
    categoryId: categoryFilter.value || undefined,
    tagId: tagFilter.value || undefined,
    ...(projectFilter.value ? { projectId: projectFilter.value } : {}),
  }
  if (props.searchOnly) {
    if (statusFilter.value) params.status = statusFilter.value
    if (overdueFilter.value) params.overdue = true
    if (plannedBucketFilter.value) params.plannedBucket = plannedBucketFilter.value
    if (sortFilter.value) params.sort = sortFilter.value
  }
  return params
}

type RestoreTarget = Pick<Task, 'id' | 'version'>
type MetadataSnapshot = { categories: Category[]; tags: Tag[] }

function getErrorMessage(error: unknown): string {
  return getTaskErrorMessage(error, props.searchOnly ? 'search' : 'inbox')
}

function showError(error: unknown): void {
  errorMessage.value = getErrorMessage(error)
}

async function loadTasks(preserveList = false): Promise<void> {
  const requestId = ++requestSequence
  if (!preserveList) loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  staleData.value = false
  try {
    const loadedTasks = await taskApi.list(taskListParams())
    if (requestId !== requestSequence) return
    tasks.value = loadedTasks
    loadState.value = 'loaded'
  } catch (error) {
    if (requestId !== requestSequence) return
    loadState.value = 'error'
    showError(error)
    if (preserveList) {
      loadState.value = 'loaded'
      staleData.value = true
    }
  } finally {
    if (requestId === requestSequence) isLoading.value = false
  }
}

async function loadMetadata(): Promise<void> {
  if (metadataLoaded.value) return
  const [loadedCategories, loadedTags, loadedProjects] = await Promise.all([
    taskApi.listCategories(),
    taskApi.listTags(),
    projectApi.list(),
  ])
  categories.value = loadedCategories
  tags.value = loadedTags
  projects.value = loadedProjects
  metadataLoaded.value = true
}

async function handleMetadataUpdated(snapshot: MetadataSnapshot): Promise<void> {
  categories.value = snapshot.categories
  tags.value = snapshot.tags
  if (loadState.value === 'loaded') await loadTasks(true)
}

async function initializeInbox(): Promise<void> {
  const initializeId = ++requestSequence
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  staleData.value = false
  try {
    await loadMetadata()
    if (initializeId !== requestSequence) return
    await loadTasks(false)
  } catch (error) {
    if (initializeId !== requestSequence) return
    loadState.value = 'error'
    showError(error)
  } finally {
    if (initializeId === requestSequence) isLoading.value = false
  }
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
    await taskApi.create({ title, description: quickDescription.value.trim() || null, planned_date: null })
    quickTitle.value = ''
    quickDescription.value = ''
    await loadTasks(true)
    ElMessage.success('任务已记录到收件箱')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
    await nextTick()
    quickInput.value?.focus()
  }
}

const quickTitle = ref('')
const quickDescription = ref('')
const quickNotesOpen = ref(false)
const quickInput = ref<{ focus: () => void } | null>(null)

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
    await loadTasks(true)
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
    await loadTasks(true)
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
    await loadTasks(true)
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
    await loadTasks(true)
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
  await loadTasks(true)
}

onMounted(initializeInbox)
</script>

<template>
  <header class="page-header">
    <div>
      <h2>{{ props.searchOnly ? '搜索任务' : '收件箱' }}</h2>
      <p class="muted">
        {{ props.searchOnly ? '搜索所有未删除任务，可组合筛选。' : '暂时还没安排日期的任务，可以先放在这里。' }}
      </p>
    </div>
    <div class="page-header-actions">
      <MetadataManager
        :categories="categories"
        :tags="tags"
        @updated="handleMetadataUpdated"
      />
      <el-button :loading="isLoading" plain @click="loadTasks(true)">刷新</el-button>
    </div>
  </header>

  <el-alert
    v-if="errorMessage && loadState !== 'error'"
    class="page-alert"
    :title="staleData ? `${errorMessage} 当前结果可能未更新。` : errorMessage"
    type="error"
    show-icon
    closable
    @close="errorMessage = ''"
  >
    <el-button v-if="staleData" text @click="loadTasks(true)">重试</el-button>
  </el-alert>

  <section v-if="loadState === 'loading'" class="today-state is-loading" aria-live="polite">
    <p class="eyebrow">加载中</p>
    <h3>{{ props.searchOnly ? '正在搜索' : '正在加载收件箱' }}</h3>
    <p class="today-state-detail">{{ props.searchOnly ? '正在查找匹配任务…' : '正在加载待安排任务…' }}</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">{{ props.searchOnly ? '搜索暂不可用' : '收件箱暂不可用' }}</p>
    <h3>{{ props.searchOnly ? '搜索失败' : '收件箱加载失败' }}</h3>
    <p class="today-state-detail">{{ errorMessage }}</p>
    <el-button type="primary" :loading="isLoading" @click="initializeInbox">重试</el-button>
  </section>

  <template v-if="loadState === 'loaded'">
    <el-card v-if="!props.searchOnly" shadow="never" class="capture-card">
      <div class="section-heading">
        <div>
          <h3>先记下来，稍后安排</h3>
        </div>
        <span class="capture-hint">可以稍后安排日期</span>
      </div>
      <form class="capture-form" @submit.prevent="createQuickTask">
        <el-input ref="quickInput" v-model="quickTitle" size="large" placeholder="想先记下什么？" aria-label="新收件箱任务标题" />
        <el-button text native-type="button" :aria-expanded="quickNotesOpen" @click="quickNotesOpen = !quickNotesOpen">{{ quickNotesOpen ? '收起备注' : '添加备注' }}</el-button>
        <el-button type="primary" native-type="submit" :loading="isSaving">记录</el-button>
        <el-input v-show="quickNotesOpen" v-model="quickDescription" class="quick-note" placeholder="备注（可选）" aria-label="新收件箱任务备注" />
      </form>
    </el-card>

    <section class="search-panel" :aria-busy="isLoading">
      <form class="search-form" @submit.prevent="applySearch">
        <label class="search-label" for="task-search">{{ props.searchOnly ? '搜索任务' : '查找任务' }}</label>
        <el-input id="task-search" v-model="searchQuery" clearable placeholder="搜索标题或备注" aria-label="搜索任务" />
        <el-button native-type="submit" :loading="isLoading">搜索</el-button>
      </form>
      <div class="filter-toolbar">
        <el-button text :aria-expanded="filtersOpen" aria-controls="task-filters" @click="filtersOpen = !filtersOpen">{{ filtersOpen ? '收起筛选' : '展开筛选' }}</el-button>
        <span class="filter-summary" :title="filterSummary">{{ filterSummary }}</span>
        <span v-if="isLoading" class="filter-loading" role="status" aria-live="polite">正在更新任务列表…</span>
        <el-button text :disabled="!hasConditions" @click="clearFilters">清除筛选</el-button>
      </div>
      <div v-show="filtersOpen" id="task-filters" class="filter-row">
        <div class="filter-field"><label for="priority-filter">优先级</label>
        <el-select id="priority-filter" v-model="priorityFilter" clearable placeholder="全部" aria-label="优先级" @change="loadTasks(true)">
          <el-option label="低" value="low" />
          <el-option label="普通" value="normal" />
          <el-option label="高" value="high" />
        </el-select>
        </div><div class="filter-field"><label for="category-filter">分类</label>
        <el-select id="category-filter" v-model="categoryFilter" clearable placeholder="全部" aria-label="分类" @change="loadTasks(true)">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
        </div><div class="filter-field"><label for="tag-filter">标签</label>
        <el-select id="tag-filter" v-model="tagFilter" clearable placeholder="全部" aria-label="标签" @change="loadTasks(true)">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
        </div><div class="filter-field"><label for="project-filter">项目</label>
        <el-select id="project-filter" v-model="projectFilter" clearable placeholder="全部" aria-label="项目" @change="loadTasks(true)">
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        </div>
        <template v-if="props.searchOnly">
          <div class="filter-field"><label for="status-filter">状态</label>
          <el-select id="status-filter" v-model="statusFilter" clearable placeholder="全部状态" aria-label="状态" @change="loadTasks(true)">
            <el-option label="待完成" value="pending" />
            <el-option label="已完成" value="completed" />
            <el-option label="全部状态" value="all" />
          </el-select>
          </div>
          <div class="filter-field filter-checkbox-field">
            <label class="filter-checkbox-label" for="overdue-filter">
              <input id="overdue-filter" v-model="overdueFilter" type="checkbox" @change="loadTasks(true)" />
              <span>仅看逾期</span>
            </label>
          </div>
          <div class="filter-field"><label for="planned-bucket-filter">计划日期</label>
          <el-select id="planned-bucket-filter" v-model="plannedBucketFilter" clearable placeholder="不限" aria-label="计划日期" @change="loadTasks(true)">
            <el-option label="未安排" value="unscheduled" />
            <el-option label="今天" value="today" />
            <el-option label="过去" value="past" />
            <el-option label="未来" value="future" />
          </el-select>
          </div>
          <div class="filter-field"><label for="sort-filter">排序</label>
          <el-select id="sort-filter" v-model="sortFilter" clearable placeholder="默认" aria-label="排序" @change="loadTasks(true)">
            <el-option label="默认" value="default" />
            <el-option label="计划日期" value="planned" />
            <el-option label="截止日期" value="deadline" />
            <el-option label="最近完成" value="completed" />
          </el-select>
          </div>
        </template>
      </div>
    </section>

    <section class="task-section">
      <div class="section-heading task-heading">
        <div>
          <h3>{{ props.searchOnly ? '搜索结果' : '待安排任务' }}</h3>
        </div>
        <el-tag type="info" effect="plain">{{ tasks.length }}</el-tag>
      </div>

      <el-empty
        v-if="tasks.length === 0"
        :description="hasConditions ? (props.searchOnly ? '暂无匹配任务' : '当前收件箱中没有匹配任务') : props.searchOnly ? '还没有可搜索的任务' : '收件箱为空'"
      >
        <template #image>
          <div class="empty-mark">✓</div>
        </template>
        <p v-if="hasConditions">试试修改关键词或清除筛选。</p>
        <el-button v-if="hasConditions" @click="clearFilters">清除筛选</el-button>
      </el-empty>

      <div v-else class="task-list">
        <TaskCard
          v-for="task in tasks"
          :key="task.id"
          :task="task"
          :busy="isSaving"
          @complete="completeTask"
          @restore="restoreTask"
          @edit="openEditDialog"
          @delete="deleteTask"
          @skip="skipTask"
        />
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
    @submit="saveEdit"
    @changed="(task) => { if (task) editingTask = task; void loadTasks(true) }"
  />
</template>
