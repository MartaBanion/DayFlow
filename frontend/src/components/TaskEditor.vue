<script setup lang="ts">
import { ref, watch } from 'vue'

import { priorityLabels } from '../constants/labels'
import type { Category, Tag, Task, TaskPriority, TaskUpdatePayload } from '../types'

const props = defineProps<{
  open: boolean
  task: Task | null
  categories: Category[]
  tags: Tag[]
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [payload: TaskUpdatePayload]
}>()

const title = ref('')
const description = ref('')
const plannedDate = ref('')
const priority = ref<TaskPriority>('normal')
const categoryId = ref<string | null>(null)
const tagIds = ref<string[]>([])

function syncForm(task: Task | null): void {
  title.value = task?.title ?? ''
  description.value = task?.description ?? ''
  plannedDate.value = task?.planned_date ?? ''
  priority.value = task?.priority ?? 'normal'
  categoryId.value = task?.category?.id ?? null
  tagIds.value = task?.tags.map((tag) => tag.id) ?? []
}

watch(() => props.task, syncForm, { immediate: true })

function submit(): void {
  const trimmedTitle = title.value.trim()
  if (!trimmedTitle) return
  emit('submit', {
    title: trimmedTitle,
    description: description.value.trim() || null,
    planned_date: plannedDate.value || null,
    priority: priority.value,
    category_id: categoryId.value ?? null,
    tag_ids: tagIds.value,
  })
}
</script>

<template>
  <el-dialog
    :model-value="open"
    title="编辑任务"
    width="560px"
    @update:model-value="emit('update:open', $event)"
  >
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="任务标题" required>
        <el-input v-model="title" placeholder="请输入任务标题" autofocus />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="description" type="textarea" :rows="4" placeholder="补充备注（可选）" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="计划日期">
          <el-date-picker
            v-model="plannedDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="未安排日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="priority" style="width: 100%">
            <el-option :label="priorityLabels.low" value="low" />
            <el-option :label="priorityLabels.normal" value="normal" />
            <el-option :label="priorityLabels.high" value="high" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="分类">
        <el-select v-model="categoryId" clearable placeholder="未分类" style="width: 100%">
          <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="标签">
        <el-select v-model="tagIds" multiple clearable placeholder="无标签" style="width: 100%">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </el-form-item>
      <div class="dialog-actions">
        <el-button @click="emit('update:open', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存修改</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>
