<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { projectApi } from '../api'
import { getProjectErrorMessage, getProjectLoadErrorMessage } from '../constants/labels'
import type { Project } from '../types'

type LoadState = 'loading' | 'loaded' | 'error'

const projects = ref<Project[]>([])
const loadState = ref<LoadState>('loading')
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const showDeletedProjects = ref(false)
const isEditorOpen = ref(false)
const editingProject = ref<Project | null>(null)
const projectName = ref('')
const projectDescription = ref('')
const formError = ref('')

const activeProjects = computed(() => projects.value.filter((project) => !project.deleted_at_utc))
const deletedProjects = computed(() => projects.value.filter((project) => Boolean(project.deleted_at_utc)))

function projectStatusLabel(project: Project): string {
  return project.status === 'completed' ? '已完成' : '进行中'
}

function openProject(project: Project): void {
  if (!project.deleted_at_utc) window.location.hash = `#project:${project.id}`
}

function showError(error: unknown): void {
  errorMessage.value = getProjectErrorMessage(error)
}

async function loadProjects(): Promise<void> {
  loadState.value = 'loading'
  isLoading.value = true
  errorMessage.value = ''
  try {
    projects.value = await projectApi.list({ includeDeleted: true })
    loadState.value = 'loaded'
  } catch (error) {
    loadState.value = 'error'
    errorMessage.value = getProjectLoadErrorMessage(error)
  } finally {
    isLoading.value = false
  }
}

function openCreateDialog(): void {
  editingProject.value = null
  projectName.value = ''
  projectDescription.value = ''
  formError.value = ''
  isEditorOpen.value = true
}

function openEditDialog(project: Project): void {
  editingProject.value = project
  projectName.value = project.name
  projectDescription.value = project.description ?? ''
  formError.value = ''
  isEditorOpen.value = true
}

function toggleDeletedProjects(): void {
  showDeletedProjects.value = !showDeletedProjects.value
}

async function saveProject(): Promise<void> {
  const name = projectName.value.trim()
  if (!name) {
    formError.value = '请填写项目名称。'
    return
  }

  isSaving.value = true
  formError.value = ''
  try {
    if (editingProject.value) {
      await projectApi.update(editingProject.value.id, editingProject.value.version, {
        name,
        description: projectDescription.value.trim() || null,
      })
      ElMessage.success('项目已更新')
    } else {
      await projectApi.create({
        name,
        description: projectDescription.value.trim() || null,
      })
      ElMessage.success('项目已创建')
    }
    isEditorOpen.value = false
    await loadProjects()
  } catch (error) {
    formError.value = getProjectErrorMessage(error)
  } finally {
    isSaving.value = false
  }
}

async function completeProject(project: Project): Promise<void> {
  if (project.task_count > project.completed_task_count) {
    try {
      await ElMessageBox.confirm(
        '项目中还有未完成任务。完成项目不会自动完成这些任务，仍要继续吗？',
        '完成项目',
        { confirmButtonText: '继续完成', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await projectApi.complete(project.id, project.version)
    await loadProjects()
    ElMessage.success('项目已完成')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function reopenProject(project: Project): Promise<void> {
  isSaving.value = true
  errorMessage.value = ''
  try {
    await projectApi.reopen(project.id, project.version)
    await loadProjects()
    ElMessage.success('项目已重新打开')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function deleteProject(project: Project): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除项目“${project.name}”吗？关联任务会保留，但会变为未归属项目。`,
      '删除项目',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  isSaving.value = true
  errorMessage.value = ''
  try {
    await projectApi.remove(project.id, project.version)
    showDeletedProjects.value = true
    await loadProjects()
    ElMessage.success('项目已删除')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

async function restoreProject(project: Project): Promise<void> {
  isSaving.value = true
  errorMessage.value = ''
  try {
    await projectApi.restore(project.id, project.version)
    await loadProjects()
    ElMessage.success('项目已恢复')
  } catch (error) {
    showError(error)
  } finally {
    isSaving.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <header class="page-header">
    <div>
      <p class="eyebrow">项目</p>
      <h2>项目</h2>
      <p class="muted">把相关任务放在一起，持续看见项目进展。</p>
    </div>
    <div class="page-header-actions">
      <el-button plain :loading="isLoading" @click="loadProjects">刷新</el-button>
      <el-button type="primary" @click="openCreateDialog">新建项目</el-button>
    </div>
  </header>

  <section v-if="loadState === 'loading'" class="today-state is-loading" aria-live="polite">
    <p class="eyebrow">加载中</p>
    <h3>正在加载项目</h3>
    <p class="today-state-detail">正在读取项目列表…</p>
  </section>

  <section v-else-if="loadState === 'error'" class="today-state is-error" role="alert">
    <p class="eyebrow">项目暂不可用</p>
    <h3>项目加载失败</h3>
    <p class="today-state-detail">{{ errorMessage }}</p>
    <el-button type="primary" :loading="isLoading" @click="loadProjects">重试</el-button>
  </section>

  <template v-else>
    <el-alert
      v-if="errorMessage"
      class="page-alert"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      @close="errorMessage = ''"
    />

    <section class="project-section">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">进行中与已完成</p>
          <h3>我的项目</h3>
        </div>
        <el-tag type="info" effect="plain">{{ activeProjects.length }}</el-tag>
      </div>

      <el-empty v-if="activeProjects.length === 0" description="还没有项目">
        <el-button type="primary" @click="openCreateDialog">新建项目</el-button>
      </el-empty>
      <div v-else class="project-grid">
        <article
          v-for="project in activeProjects"
          :key="project.id"
          class="project-card"
          :class="{ 'is-completed': project.status === 'completed' }"
        >
          <button class="project-card-main" type="button" @click="openProject(project)">
            <div class="project-card-heading">
              <h4>{{ project.name }}</h4>
              <el-tag :type="project.status === 'completed' ? 'success' : 'info'" effect="plain" size="small">
                {{ projectStatusLabel(project) }}
              </el-tag>
            </div>
            <p v-if="project.description" class="project-description">{{ project.description }}</p>
            <div class="project-progress-row">
              <span>项目进度</span>
              <strong>{{ project.progress_percent }}%</strong>
            </div>
            <el-progress :percentage="project.progress_percent" :show-text="false" :stroke-width="8" />
            <p class="project-card-meta">
              {{ project.completed_task_count }} / {{ project.task_count }} 个任务已完成
            </p>
          </button>
          <div class="project-card-actions">
            <el-button text @click="openEditDialog(project)">编辑</el-button>
            <el-button v-if="project.status === 'active'" text @click="completeProject(project)">完成项目</el-button>
            <el-button v-else text @click="reopenProject(project)">重新打开</el-button>
            <el-button type="danger" text @click="deleteProject(project)">删除</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="project-section deleted-project-section">
      <div class="section-heading task-heading">
        <div>
          <p class="eyebrow">已删除项目</p>
          <h3>回收的项目</h3>
        </div>
        <el-button text @click="toggleDeletedProjects">
          {{ showDeletedProjects ? '收起' : `查看已删除项目（${deletedProjects.length}）` }}
        </el-button>
      </div>
      <div v-if="showDeletedProjects">
        <el-empty v-if="deletedProjects.length === 0" description="没有已删除项目" />
        <div v-else class="project-grid">
          <article v-for="project in deletedProjects" :key="project.id" class="project-card is-deleted">
            <div class="project-card-heading">
              <h4>{{ project.name }}</h4>
              <el-tag type="info" effect="plain" size="small">已删除</el-tag>
            </div>
            <p v-if="project.description" class="project-description">{{ project.description }}</p>
            <p class="project-card-meta">关联任务已解除项目归属，恢复后不会自动重新关联。</p>
            <div class="project-card-actions">
              <el-button type="primary" text @click="restoreProject(project)">恢复项目</el-button>
            </div>
          </article>
        </div>
      </div>
    </section>
  </template>

  <el-dialog v-model="isEditorOpen" :title="editingProject ? '编辑项目' : '新建项目'" width="520px">
    <el-form label-position="top" @submit.prevent="saveProject">
      <el-form-item label="项目名称" required>
        <el-input v-model="projectName" maxlength="200" placeholder="例如：学习 Linux" autofocus />
      </el-form-item>
      <el-form-item label="项目描述">
        <el-input v-model="projectDescription" type="textarea" :rows="4" placeholder="补充项目目标或说明（可选）" />
      </el-form-item>
      <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      <div class="dialog-actions">
        <el-button @click="isEditorOpen = false">取消</el-button>
        <el-button type="primary" :loading="isSaving" @click="saveProject">
          {{ editingProject ? '保存修改' : '创建项目' }}
        </el-button>
      </div>
    </el-form>
  </el-dialog>
</template>
