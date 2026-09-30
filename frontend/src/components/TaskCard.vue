<script setup lang="ts">
import { priorityLabels } from '../constants/labels'
import { deadlineStatusLabel, taskDeadlineLabel, taskTimeLabel } from '../calendar'
import type { Task } from '../types'

defineProps<{
  task: Task
  contextDate?: string
}>()

const emit = defineEmits<{
  complete: [task: Task]
  restore: [task: Task]
  edit: [task: Task]
  delete: [task: Task]
  skip: [task: Task]
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
        <div class="task-badges task-primary-meta">
          <span v-if="taskTimeLabel(task)" class="task-meta">{{ taskTimeLabel(task) }}</span>
          <span v-else-if="task.planned_date !== contextDate" class="task-meta">
            {{ task.planned_date ? `计划日期：${task.planned_date}` : '暂未安排日期' }}
          </span>
          <el-tag
            v-if="taskDeadlineLabel(task)"
            :type="task.deadline_status === 'overdue' ? 'danger' : task.deadline_status === 'due_today' ? 'warning' : 'info'"
            effect="plain"
            size="small"
          >
            {{ taskDeadlineLabel(task) }}<span v-if="deadlineStatusLabel(task.deadline_status)"> · {{ task.deadline_status === 'due_today' ? '今天到期' : deadlineStatusLabel(task.deadline_status) }}</span>
          </el-tag>
          <el-tag :type="task.priority === 'high' ? 'danger' : 'info'" effect="plain" size="small">
            {{ priorityLabels[task.priority] }}
          </el-tag>
          <el-tag v-if="task.project" effect="plain" size="small">
            {{ task.project.name }}
          </el-tag>
        </div>
        <p v-if="task.description" class="task-description">{{ task.description }}</p>
        <div class="task-badges task-secondary-meta">
          <el-tag v-if="task.category" type="info" effect="plain" size="small">{{ task.category.name }}</el-tag>
          <el-tag v-for="tag in task.tags.slice(0, 2)" :key="tag.id" type="info" effect="plain" size="small">
            {{ tag.name }}
          </el-tag>
          <el-popover v-if="task.tags.length > 2" trigger="click" width="240">
            <template #reference><el-button text :aria-label="`查看全部标签：${task.title}`">+{{ task.tags.length - 2 }}</el-button></template>
            <p>全部标签：{{ task.tags.map(tag => tag.name).join('、') }}</p>
          </el-popover>
          <span v-if="task.recurrence_rule_id" class="task-meta">重复任务</span>
        </div>
      </div>
    </div>
    <div class="task-actions">
      <el-tag v-if="task.status === 'completed'" type="success" effect="plain">已完成</el-tag>
      <el-button text @click="emit('edit', task)">编辑</el-button>
      <el-button v-if="task.status === 'completed'" text @click="emit('restore', task)">
        恢复
      </el-button>
      <el-dropdown trigger="click" @command="(command: string) => command === 'delete' ? emit('delete', task) : emit('skip', task)">
        <el-button text :aria-label="`更多操作：${task.title}`">更多</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-if="task.status === 'pending' && task.recurrence_rule_id" command="skip">跳过本次</el-dropdown-item>
            <el-dropdown-item command="delete">删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </article>
</template>
