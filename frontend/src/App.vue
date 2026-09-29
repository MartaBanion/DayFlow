<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import packageMetadata from '../package.json'

import InboxView from './components/InboxView.vue'
import TodayView from './components/TodayView.vue'
import CalendarView from './components/CalendarView.vue'
import ProjectDetailView from './components/ProjectDetailView.vue'
import ProjectsView from './components/ProjectsView.vue'

type ViewName = 'today' | 'inbox' | 'calendar' | 'search' | 'projects' | 'project-detail'

function viewFromHash(): ViewName {
  const hash = window.location.hash
  if (hash === '#inbox') return 'inbox'
  if (hash === '#calendar') return 'calendar'
  if (hash === '#search') return 'search'
  if (hash === '#projects') return 'projects'
  if (hash.startsWith('#project:')) return 'project-detail'
  return 'today'
}

function projectIdFromHash(): string | null {
  const prefix = '#project:'
  return window.location.hash.startsWith(prefix)
    ? window.location.hash.slice(prefix.length) || null
    : null
}

const currentView = ref<ViewName>(viewFromHash())
const currentProjectId = ref<string | null>(projectIdFromHash())
const applicationVersion = `v${packageMetadata.version}`

function syncViewFromHash(): void {
  currentView.value = viewFromHash()
  currentProjectId.value = projectIdFromHash()
}

onMounted(() => window.addEventListener('hashchange', syncViewFromHash))
onBeforeUnmount(() => window.removeEventListener('hashchange', syncViewFromHash))
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-row">
        <div class="brand-mark">D</div>
        <div>
          <p class="eyebrow">个人工作区</p>
          <h1>DayFlow</h1>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="主要导航">
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'today' }"
          href="#today"
          @click="currentView = 'today'"
        >
          今天 <span>01</span>
        </a>
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'inbox' }"
          href="#inbox"
          @click="currentView = 'inbox'"
        >
          收件箱 <span>02</span>
        </a>
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'calendar' }"
          href="#calendar"
          @click="currentView = 'calendar'"
        >
          日历 <span>03</span>
        </a>
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'search' }"
          href="#search"
          @click="currentView = 'search'"
        >
          搜索 <span>04</span>
        </a>
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'projects' || currentView === 'project-detail' }"
          href="#projects"
          @click="currentView = 'projects'"
        >
          项目 <span>05</span>
        </a>
      </nav>

      <div class="sidebar-note">
        <p class="eyebrow">专注</p>
        <p>稳定的小步，让每一天更清晰。</p>
      </div>

      <div class="sidebar-footer">
        <el-tag type="info" effect="plain">{{ applicationVersion }}</el-tag>
        <span>本地优先</span>
      </div>
    </aside>

    <main
      class="workspace"
      :class="{
        'workspace-calendar': currentView === 'calendar',
        'workspace-projects': currentView === 'projects' || currentView === 'project-detail',
      }"
    >
      <TodayView v-if="currentView === 'today'" />
      <InboxView v-else-if="currentView === 'inbox'" />
      <InboxView v-else-if="currentView === 'search'" search-only />
      <ProjectsView v-else-if="currentView === 'projects'" />
      <ProjectDetailView
        v-else-if="currentView === 'project-detail'"
        :project-id="currentProjectId ?? ''"
      />
      <CalendarView v-else />
    </main>
  </div>
</template>
