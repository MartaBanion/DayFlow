<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError, taskApi } from '../api'
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
  if (error instanceof ApiRequestError) {
    if (error.code === `${subject}_name_conflict` || error.status === 409) {
      return `A ${subject} with that name already exists.`
    }
    if (error.status === 422) {
      return `Enter a non-empty ${subject} name within the allowed length.`
    }
    return error.message
  }
  return `DayFlow could not update this ${subject}. Check that the Backend is running.`
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
    errorMessage.value = error instanceof ApiRequestError
      ? error.message
      : 'DayFlow could not load Categories and Tags.'
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
    errorMessage.value = 'Category name cannot be empty.'
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.createCategory(name)
    newCategoryName.value = ''
    if (await refreshMetadata()) ElMessage.success('Category created')
  } catch (error) {
    showError(error, 'category')
  } finally {
    isMutating.value = false
  }
}

async function createTag(): Promise<void> {
  const name = newTagName.value.trim()
  if (!name) {
    errorMessage.value = 'Tag name cannot be empty.'
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.createTag(name)
    newTagName.value = ''
    if (await refreshMetadata()) ElMessage.success('Tag created')
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
    errorMessage.value = `${kind === 'category' ? 'Category' : 'Tag'} name cannot be empty.`
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
      ElMessage.success(`${kind === 'category' ? 'Category' : 'Tag'} renamed`)
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
      `Delete category “${category.name}”? Tasks will be kept.`,
      'Delete category',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.removeCategory(category.id)
    if (await refreshMetadata()) ElMessage.success('Category deleted')
  } catch (error) {
    showError(error, 'category')
  } finally {
    isMutating.value = false
  }
}

async function deleteTag(tag: Tag): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Delete tag “${tag.name}”? Tasks will be kept.`,
      'Delete tag',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }

  isMutating.value = true
  clearError()
  try {
    await taskApi.removeTag(tag.id)
    if (await refreshMetadata()) ElMessage.success('Tag deleted')
  } catch (error) {
    showError(error, 'tag')
  } finally {
    isMutating.value = false
  }
}
</script>

<template>
  <el-button plain @click="openManager">Manage metadata</el-button>

  <el-dialog v-model="isOpen" title="Manage categories and tags" width="640px">
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
          <p class="eyebrow">CATEGORIES</p>
          <h3>Organize by one category</h3>
        </div>
      </div>
      <form class="metadata-create-form" @submit.prevent="createCategory">
        <el-input
          v-model="newCategoryName"
          maxlength="100"
          placeholder="New category name"
          aria-label="New category name"
        />
        <el-button type="primary" native-type="submit" :loading="isMutating">
          Add category
        </el-button>
      </form>
      <p v-if="!localCategories.length && !errorMessage" class="metadata-empty">
        No categories yet.
      </p>
      <div v-else class="metadata-list">
        <div v-for="category in localCategories" :key="category.id" class="metadata-row">
          <template v-if="editingKind === 'category' && editingId === category.id">
            <el-input v-model="editingName" :aria-label="`Rename category ${category.name}`" maxlength="100" />
            <el-button type="primary" text :loading="isMutating" @click="saveRename">Save</el-button>
            <el-button text :disabled="isMutating" @click="cancelRename">Cancel</el-button>
          </template>
          <template v-else>
            <el-tag effect="plain">{{ category.name }}</el-tag>
            <span class="metadata-row-actions">
              <el-button text :disabled="isMutating" @click="startRename('category', category.id, category.name)">
                Rename
              </el-button>
              <el-button type="danger" text :loading="isMutating" @click="deleteCategory(category)">
                Delete
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
          <p class="eyebrow">TAGS</p>
          <h3>Use multiple tags when useful</h3>
        </div>
      </div>
      <form class="metadata-create-form" @submit.prevent="createTag">
        <el-input
          v-model="newTagName"
          maxlength="50"
          placeholder="New tag name"
          aria-label="New tag name"
        />
        <el-button type="primary" native-type="submit" :loading="isMutating">
          Add tag
        </el-button>
      </form>
      <p v-if="!localTags.length && !errorMessage" class="metadata-empty">
        No tags yet.
      </p>
      <div v-else class="metadata-list">
        <div v-for="tag in localTags" :key="tag.id" class="metadata-row">
          <template v-if="editingKind === 'tag' && editingId === tag.id">
            <el-input v-model="editingName" :aria-label="`Rename tag ${tag.name}`" maxlength="50" />
            <el-button type="primary" text :loading="isMutating" @click="saveRename">Save</el-button>
            <el-button text :disabled="isMutating" @click="cancelRename">Cancel</el-button>
          </template>
          <template v-else>
            <el-tag effect="plain">{{ tag.name }}</el-tag>
            <span class="metadata-row-actions">
              <el-button text :disabled="isMutating" @click="startRename('tag', tag.id, tag.name)">
                Rename
              </el-button>
              <el-button type="danger" text :loading="isMutating" @click="deleteTag(tag)">
                Delete
              </el-button>
            </span>
          </template>
        </div>
      </div>
    </section>
  </el-dialog>
</template>
