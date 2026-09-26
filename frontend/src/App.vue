<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError, taskApi } from './api'
import { calculateCompletionRate, formatDisplayDate, toDateInputValue } from './date'
import type { Task } from './types'

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
const editForm = ref({
  title: '',
  description: '',
  plannedDate: '',
})

const pendingTasks = computed(() => tasks.value.filter((task) => task.status === 'pending'))
const completionRate = computed(() => calculateCompletionRate(tasks.value))
const formattedDate = computed(() => formatDisplayDate(selectedDate.value))

type RestoreTarget = Pick<Task, 'id' | 'version'>

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

function openEditDialog(task: Task): void {
  editingTask.value = task
  editForm.value = {
    title: task.title,
    description: task.description ?? '',
    plannedDate: task.planned_date ?? '',
  }
  isEditDialogOpen.value = true
}

async function saveEdit(): Promise<void> {
  const task = editingTask.value
  const title = editForm.value.title.trim()
  if (!task || !title) {
    errorMessage.value = 'Task title cannot be empty.'
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await taskApi.update(task.id, task.version, {
      title,
      description: editForm.value.description.trim() || null,
      planned_date: editForm.value.plannedDate || null,
    })
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
    // Soft delete increments the optimistic-lock version before the restore action.
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
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-row">
        <div class="brand-mark">D</div>
        <div>
          <p class="eyebrow">PERSONAL WORKSPACE</p>
          <h1>DayFlow</h1>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Primary navigation">
        <a class="nav-item is-active" href="#today">Today <span>01</span></a>
        <span class="nav-item is-disabled">Inbox</span>
        <span class="nav-item is-disabled">Calendar</span>
        <span class="nav-item is-disabled">Projects</span>
      </nav>

      <div class="sidebar-note">
        <p class="eyebrow">FOCUS</p>
        <p>Small, reliable steps for a clearer day.</p>
      </div>

      <div class="sidebar-footer">
        <el-tag type="info" effect="plain">V0.1</el-tag>
        <span>Local first</span>
      </div>
    </aside>

    <main id="today" class="workspace">
      <header class="page-header">
        <div>
          <p class="eyebrow">TODAY</p>
          <h2>{{ formattedDate }}</h2>
          <p class="muted">A calm view of what deserves your attention.</p>
        </div>
        <el-button :loading="isLoading" plain @click="loadToday">Refresh</el-button>
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

      <section
        v-if="todayLoadState === 'loading'"
        class="today-state is-loading"
        aria-live="polite"
      >
        <p class="eyebrow">LOADING</p>
        <h3>Loading today</h3>
        <p class="today-state-detail">Loading today’s tasks…</p>
      </section>

      <section
        v-else-if="todayLoadState === 'error'"
        class="today-state is-error"
        role="alert"
      >
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
          <el-input
            v-model="quickTitle"
            size="large"
            placeholder="What needs your attention?"
            aria-label="New task title"
          />
          <el-input
            v-model="quickDescription"
            placeholder="Optional note"
            aria-label="New task description"
          />
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

        <el-empty
          v-if="tasks.length === 0"
          description="Nothing planned for this day"
        >
          <template #image>
            <div class="empty-mark">✓</div>
          </template>
        </el-empty>

        <div v-else class="task-list">
          <article
            v-for="task in tasks"
            :key="task.id"
            class="task-card"
            :class="{ 'is-completed': task.status === 'completed' }"
          >
            <div class="task-main">
              <button
                v-if="task.status === 'pending'"
                class="task-check"
                type="button"
                :aria-label="`Complete ${task.title}`"
                @click="completeTask(task)"
              >
                <span />
              </button>
              <button
                v-else
                class="task-check is-done"
                type="button"
                :aria-label="`Restore ${task.title}`"
                @click="restoreTask(task)"
              >
                ✓
              </button>
              <div class="task-copy">
                <h4>{{ task.title }}</h4>
                <p v-if="task.description" class="task-description">{{ task.description }}</p>
                <span class="task-meta">Planned for {{ task.planned_date ?? 'no date' }}</span>
              </div>
            </div>
            <div class="task-actions">
              <el-tag v-if="task.status === 'completed'" type="success" effect="plain">Done</el-tag>
              <el-button text @click="openEditDialog(task)">Edit</el-button>
              <el-button v-if="task.status === 'completed'" text @click="restoreTask(task)">Restore</el-button>
              <el-button type="danger" text @click="deleteTask(task)">Delete</el-button>
            </div>
          </article>
        </div>
      </section>
    </main>

    <el-dialog v-model="isEditDialogOpen" title="Edit task" width="520px">
      <el-form label-position="top" @submit.prevent="saveEdit">
        <el-form-item label="Title" required>
          <el-input v-model="editForm.title" autofocus />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="editForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="Planned date">
          <el-date-picker
            v-model="editForm.plannedDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="Choose a date"
            style="width: 100%"
          />
        </el-form-item>
        <div class="dialog-actions">
          <el-button @click="isEditDialogOpen = false">Cancel</el-button>
          <el-button type="primary" :loading="isSaving" @click="saveEdit">Save changes</el-button>
        </div>
      </el-form>
    </el-dialog>
  </div>
</template>
