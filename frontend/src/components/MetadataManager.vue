<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { taskApi } from '../api'
import {
  getMetadataErrorMessage,
  getMetadataLoadErrorMessage,
} from '../constants/labels'
import type { Category, Tag } from '../types'

type MetadataSnapshot = {
  categories: Category[]
  tags: Tag[]
}

const props = defineProps<MetadataSnapshot>()

const emit = defineEmits<{
  updated: [snapshot: MetadataSnapshot]
}>()

const isOpen = ref(false)
const isLoading = ref(false)
const isMutating = ref(false)
const errorMessage = ref('')
const localCategories = ref<Category[]>([])
const localTags = ref<Tag[]>([])
const newCategoryName = ref('')
const newTagName = ref('')
const editingKind = ref<'category' | 'tag' | null>(null)
const editingId = ref('')
const editingName = ref('')

watch(
  () => props.categories,
  (categories) => {
    localCategories.value = categories
  },
  { immediate: true },
)
watch(
  () => props.tags,
  (tags) => {
    localTags.value = tags
  },
  { immediate: true },
)

function getErrorMessage(error: unknown, subject: 'category' | 'tag'): string {
  return getMetadataErrorMessage(error, subject)
}

function showError(error: unknown, subject: 'category' | 'tag'): void {
  errorMessage.value = getErrorMessage(error, subject)
}

function clearError(): void {
  errorMessage.value = ''
}

async function refreshMetadata(): Promise<boolean> {
  isLoading.value = true
  try {
    const [categories, tags] = await Promise.all([
      taskApi.listCategories(),
      taskApi.listTags(),
    ])
    localCategories.value = categories
    localTags.value = tags
    emit('updated', { categories, tags })
    return true
  } catch (error) {
    errorMessage.value = getMetadataLoadErrorMessage(error)
    return false
  } finally {
    isLoading.value = false
  }
}

async function openManager(): Promise<void> {
  isOpen.value = true
  clearError()
  await refreshMetadata()
}

async function createCategory(): Promise<void> {
  const name = newCategoryName.value.trim()
  if (!name) {
    errorMessage.value = '分类名称不能为空。'
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.createCategory(name)
    newCategoryName.value = ''
    if (await refreshMetadata()) ElMessage.success('分类已创建')
  } catch (error) {
    showError(error, 'category')
  } finally {
    isMutating.value = false
  }
}

async function createTag(): Promise<void> {
  const name = newTagName.value.trim()
  if (!name) {
    errorMessage.value = '标签名称不能为空。'
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.createTag(name)
    newTagName.value = ''
    if (await refreshMetadata()) ElMessage.success('标签已创建')
  } catch (error) {
    showError(error, 'tag')
  } finally {
    isMutating.value = false
  }
}

function startRename(kind: 'category' | 'tag', id: string, name: string): void {
  editingKind.value = kind
  editingId.value = id
  editingName.value = name
  clearError()
}

function cancelRename(): void {
  editingKind.value = null
  editingId.value = ''
  editingName.value = ''
}

async function saveRename(): Promise<void> {
  const kind = editingKind.value
  const name = editingName.value.trim()
  if (!kind) return
  if (!name) {
    errorMessage.value = `${kind === 'category' ? '分类' : '标签'}名称不能为空。`
    return
  }

  isMutating.value = true
  clearError()
  try {
    if (kind === 'category') {
      await taskApi.updateCategory(editingId.value, name)
    } else {
      await taskApi.updateTag(editingId.value, name)
    }
    cancelRename()
    if (await refreshMetadata()) {
      ElMessage.success(`${kind === 'category' ? '分类' : '标签'}已重命名`)
    }
  } catch (error) {
    showError(error, kind)
  } finally {
    isMutating.value = false
  }
}

async function deleteCategory(category: Category): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除分类“${category.name}”吗？任务不会被删除。`,
      '删除分类',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.removeCategory(category.id)
    if (await refreshMetadata()) ElMessage.success('分类已删除')
  } catch (error) {
    showError(error, 'category')
  } finally {
    isMutating.value = false
  }
}

async function deleteTag(tag: Tag): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除标签“${tag.name}”吗？任务不会被删除。`,
      '删除标签',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.removeTag(tag.id)
    if (await refreshMetadata()) ElMessage.success('标签已删除')
  } catch (error) {
    showError(error, 'tag')
  } finally {
    isMutating.value = false
  }
}
</script>

<template>
  <el-button plain @click="openManager">管理分类与标签</el-button>

  <el-dialog v-model="isOpen" title="管理分类与标签" width="640px">
    <el-alert
      v-if="errorMessage"
      class="metadata-alert"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      @close="clearError"
    />

    <section class="metadata-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">分类</p>
          <h3>每个任务选择一个分类</h3>
        </div>
      </div>
      <form class="metadata-create-form" @submit.prevent="createCategory">
        <el-input
          v-model="newCategoryName"
          maxlength="100"
          placeholder="新分类名称"
          aria-label="新分类名称"
        />
        <el-button type="primary" native-type="submit" :loading="isMutating">
          新建分类
        </el-button>
      </form>
      <p v-if="!localCategories.length && !errorMessage" class="metadata-empty">
        还没有分类。
      </p>
      <div v-else class="metadata-list">
        <div v-for="category in localCategories" :key="category.id" class="metadata-row">
          <template v-if="editingKind === 'category' && editingId === category.id">
            <el-input v-model="editingName" :aria-label="`重命名分类：${category.name}`" maxlength="100" />
            <el-button type="primary" text :loading="isMutating" @click="saveRename">保存</el-button>
            <el-button text :disabled="isMutating" @click="cancelRename">取消</el-button>
          </template>
          <template v-else>
            <el-tag effect="plain">{{ category.name }}</el-tag>
            <span class="metadata-row-actions">
              <el-button text :disabled="isMutating" @click="startRename('category', category.id, category.name)">
                重命名
              </el-button>
              <el-button type="danger" text :loading="isMutating" @click="deleteCategory(category)">
                删除
              </el-button>
            </span>
          </template>
        </div>
      </div>
    </section>

    <el-divider />

    <section class="metadata-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">标签</p>
          <h3>需要时添加多个标签</h3>
        </div>
      </div>
      <form class="metadata-create-form" @submit.prevent="createTag">
        <el-input
          v-model="newTagName"
          maxlength="50"
          placeholder="新标签名称"
          aria-label="新标签名称"
        />
        <el-button type="primary" native-type="submit" :loading="isMutating">
          新建标签
        </el-button>
      </form>
      <p v-if="!localTags.length && !errorMessage" class="metadata-empty">
        还没有标签。
      </p>
      <div v-else class="metadata-list">
        <div v-for="tag in localTags" :key="tag.id" class="metadata-row">
          <template v-if="editingKind === 'tag' && editingId === tag.id">
            <el-input v-model="editingName" :aria-label="`重命名标签：${tag.name}`" maxlength="50" />
            <el-button type="primary" text :loading="isMutating" @click="saveRename">保存</el-button>
            <el-button text :disabled="isMutating" @click="cancelRename">取消</el-button>
          </template>
          <template v-else>
            <el-tag effect="plain">{{ tag.name }}</el-tag>
            <span class="metadata-row-actions">
              <el-button text :disabled="isMutating" @click="startRename('tag', tag.id, tag.name)">
                重命名
              </el-button>
              <el-button type="danger" text :loading="isMutating" @click="deleteTag(tag)">
                删除
              </el-button>
            </span>
          </template>
        </div>
      </div>
    </section>
  </el-dialog>
</template>
