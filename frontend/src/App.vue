<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import InboxView from './components/InboxView.vue'
import TodayView from './components/TodayView.vue'

type ViewName = 'today' | 'inbox'

const currentView = ref<ViewName>(window.location.hash === '#inbox' ? 'inbox' : 'today')

function syncViewFromHash(): void {
  currentView.value = window.location.hash === '#inbox' ? 'inbox' : 'today'
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
          <p class="eyebrow">PERSONAL WORKSPACE</p>
          <h1>DayFlow</h1>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Primary navigation">
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'today' }"
          href="#today"
          @click="currentView = 'today'"
        >
          Today <span>01</span>
        </a>
        <a
          class="nav-item"
          :class="{ 'is-active': currentView === 'inbox' }"
          href="#inbox"
          @click="currentView = 'inbox'"
        >
          Inbox <span>02</span>
        </a>
        <span class="nav-item is-disabled">Calendar</span>
        <span class="nav-item is-disabled">Projects</span>
      </nav>

      <div class="sidebar-note">
        <p class="eyebrow">FOCUS</p>
        <p>Small, reliable steps for a clearer day.</p>
      </div>

      <div class="sidebar-footer">
        <el-tag type="info" effect="plain">V0.2</el-tag>
        <span>Local first</span>
      </div>
    </aside>

    <main class="workspace">
      <TodayView v-if="currentView === 'today'" />
      <InboxView v-else />
    </main>
  </div>
</template>
