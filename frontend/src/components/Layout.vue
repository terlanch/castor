<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <!-- Logo -->
      <div class="sidebar-logo" @click="isCollapsed = !isCollapsed">
        <div class="logo-icon">
          <img src="/images/logo.png" alt="Castor" class="logo-img" />
        </div>
        <transition name="fade">
          <span v-if="!isCollapsed" class="logo-text">CASTOR</span>
        </transition>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <!-- Admin section -->
        <div v-if="auth.isAdmin" class="nav-section">
          <div v-if="!isCollapsed" class="nav-section-label">Admin</div>
          <router-link to="/dashboard" class="nav-item" :class="{ active: route.path === '/dashboard' }">
            <div class="nav-icon"><el-icon><DataAnalysis /></el-icon></div>
            <span v-if="!isCollapsed" class="nav-label">Dashboard</span>
          </router-link>
          <router-link to="/agents" class="nav-item" :class="{ active: route.path === '/agents' }">
            <div class="nav-icon"><el-icon><Monitor /></el-icon></div>
            <span v-if="!isCollapsed" class="nav-label">Agents</span>
          </router-link>
          <router-link to="/tasks" class="nav-item" :class="{ active: route.path === '/tasks' }">
            <div class="nav-icon"><el-icon><List /></el-icon></div>
            <span v-if="!isCollapsed" class="nav-label">Tasks</span>
          </router-link>
        </div>

        <!-- User section -->
        <div class="nav-section">
          <div v-if="!isCollapsed" class="nav-section-label">{{ auth.isAdmin ? 'User' : 'Workspace' }}</div>
          <router-link to="/portal" class="nav-item" :class="{ active: route.path === '/portal' }">
            <div class="nav-icon"><el-icon><Wallet /></el-icon></div>
            <span v-if="!isCollapsed" class="nav-label">Portal</span>
          </router-link>
          <router-link to="/tasks/create" class="nav-item" :class="{ active: route.path === '/tasks/create' }">
            <div class="nav-icon"><el-icon><Plus /></el-icon></div>
            <span v-if="!isCollapsed" class="nav-label">New Task</span>
          </router-link>
        </div>
      </nav>

      <!-- Bottom actions -->
      <div class="sidebar-bottom">
        <div class="nav-item logout-item" @click="handleLogout">
          <div class="nav-icon"><el-icon><SwitchButton /></el-icon></div>
          <span v-if="!isCollapsed" class="nav-label">Logout</span>
        </div>
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <!-- Top header bar -->
      <header class="top-header">
        <div class="header-left">
          <div class="breadcrumb-text">{{ pageTitle }}</div>
        </div>
        <div class="header-right">
          <div class="user-badge" :class="auth.isAdmin ? 'admin' : 'user'">
            <span class="badge-dot"></span>
            {{ auth.isAdmin ? 'ADMIN' : 'USER' }}
          </div>
        </div>
      </header>

      <!-- Content -->
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { DataAnalysis, Monitor, List, Plus, Wallet, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapsed = ref(false)

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    '/dashboard': 'Dashboard',
    '/agents': 'Agents',
    '/tasks': 'Tasks',
    '/tasks/create': 'New Task',
    '/portal': 'Portal',
  }
  return map[route.path] || ''
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--c-bg);
}

/* ---------- Sidebar ---------- */
.sidebar {
  width: 240px;
  min-height: 100vh;
  background: linear-gradient(180deg, #0c1024 0%, #080c18 100%);
  border-right: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  transition: width 0.3s var(--ease-out);
  position: relative;
  z-index: 20;
}
.sidebar::after {
  content: '';
  position: absolute;
  top: 0; right: -1px;
  width: 1px; height: 100%;
  background: linear-gradient(180deg, rgba(0,212,255,0.2) 0%, transparent 50%, rgba(124,58,237,0.2) 100%);
}
.sidebar.collapsed {
  width: 68px;
}

/* Logo */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px;
  cursor: pointer;
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 8px;
}
.logo-icon {
  width: 36px; height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(0,212,255,0.12), rgba(124,58,237,0.12));
  border: 1px solid rgba(0,212,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 0 16px rgba(0,212,255,0.08);
  overflow: hidden;
}
.logo-img {
  width: 28px;
  height: 28px;
  object-fit: contain;
}
.logo-text {
  font-size: 18px;
  font-weight: 900;
  letter-spacing: 0.14em;
  background: linear-gradient(135deg, #fff 30%, #00d4ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
}

/* Nav sections */
.sidebar-nav {
  flex: 1;
  padding: 0 8px;
  overflow-y: auto;
}
.nav-section {
  margin-bottom: 8px;
}
.nav-section-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--c-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 16px 12px 6px;
}

/* Nav items */
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin: 2px 0;
  border-radius: 10px;
  color: var(--c-text-dim);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  position: relative;
}
.nav-item:hover {
  background: rgba(0, 212, 255, 0.06);
  color: var(--c-text);
}
.nav-item.active {
  background: rgba(0, 212, 255, 0.10);
  color: #fff;
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 8px; bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--c-cyan);
  box-shadow: 0 0 12px rgba(0, 212, 255, 0.4);
}
.nav-icon {
  width: 32px; height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  flex-shrink: 0;
  transition: all 0.2s;
}
.nav-item.active .nav-icon {
  background: rgba(0, 212, 255, 0.12);
  color: var(--c-cyan);
  box-shadow: 0 0 12px rgba(0, 212, 255, 0.12);
}
.nav-label {
  white-space: nowrap;
}

/* Bottom */
.sidebar-bottom {
  padding: 8px;
  border-top: 1px solid var(--c-border);
}
.logout-item:hover {
  color: var(--c-red) !important;
  background: var(--c-red-dim) !important;
}

/* ---------- Main area ---------- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

/* Header */
.top-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  height: 60px;
  background: rgba(11, 15, 26, 0.80);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--c-border);
  position: sticky;
  top: 0;
  z-index: 10;
}
.breadcrumb-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-dim);
}

/* User badge */
.user-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.user-badge.admin {
  background: var(--c-purple-dim);
  color: #a78bfa;
  border: 1px solid rgba(124, 58, 237, 0.25);
}
.user-badge.user {
  background: var(--c-green-dim);
  color: var(--c-green);
  border: 1px solid rgba(0, 255, 136, 0.2);
}
.badge-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

/* Content */
.main-content {
  flex: 1;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

/* Transition */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
