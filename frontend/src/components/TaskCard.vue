<script setup lang="ts">
import { priorityLabels } from '../constants/labels'
import type { Task } from '../types'

defineProps<{
  task: Task
}>()

const emit = defineEmits<{
  complete: [task: Task]
  restore: [task: Task]
  edit: [task: Task]
  delete: [task: Task]
}>()
</script>

<template>
  <article
    class="task-card"
    :class="{ 'is-completed': task.status === 'completed' }"
  >
    <div class="task-main">
      <button
        v-if="task.status === 'pending'"
        class="task-check"
        type="button"
        :aria-label="`完成任务：${task.title}`"
        @click="emit('complete', task)"
      >
        <span />
      </button>
      <button
        v-else
        class="task-check is-done"
        type="button"
        :aria-label="`恢复任务：${task.title}`"
        @click="emit('restore', task)"
      >
        ✓
      </button>
      <div class="task-copy">
        <h4>{{ task.title }}</h4>
        <p v-if="task.description" class="task-description">{{ task.description }}</p>
        <div class="task-badges">
          <span class="task-meta">
            {{ task.planned_date ? `计划日期：${task.planned_date}` : '暂未安排日期' }}
          </span>
          <el-tag :type="task.priority === 'high' ? 'danger' : task.priority === 'low' ? 'info' : 'warning'" effect="plain" size="small">
            {{ priorityLabels[task.priority] }}
          </el-tag>
          <el-tag v-if="task.category" effect="plain" size="small">
            {{ task.category.name }}
          </el-tag>
          <el-tag v-if="task.project" effect="plain" size="small">
            {{ task.project.name }}
          </el-tag>
          <el-tag v-for="tag in task.tags" :key="tag.id" effect="plain" size="small">
            {{ tag.name }}
          </el-tag>
        </div>
      </div>
    </div>
    <div class="task-actions">
      <el-tag v-if="task.status === 'completed'" type="success" effect="plain">已完成</el-tag>
      <el-button text @click="emit('edit', task)">编辑</el-button>
      <el-button v-if="task.status === 'completed'" text @click="emit('restore', task)">
        恢复
      </el-button>
      <el-button type="danger" text @click="emit('delete', task)">删除</el-button>
    </div>
  </article>
</template>
