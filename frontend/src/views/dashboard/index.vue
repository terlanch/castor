<template>
  <div class="page-container">
    <h2 class="page-title">Dashboard</h2>

    <!-- Stat cards -->
    <div class="stats-grid stagger-grid">
      <div class="glass-card stat-card" v-for="(card, idx) in statCards" :key="card.label">
        <div class="stat-icon" :class="card.color">
          <el-icon :size="22"><component :is="card.icon" /></el-icon>
        </div>
        <div>
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.color">{{ card.value }}</div>
        </div>
      </div>
    </div>

    <!-- Overview panels -->
    <div class="overview-grid">
      <!-- Agent overview -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon class="icon"><Monitor /></el-icon>
            Agent Status Overview
          </div>
        </div>
        <div class="section-body" v-if="dashboard.agents">
          <div class="metric-grid">
            <div class="metric-item">
              <span class="status-dot online"></span>
              <span class="metric-label">Online</span>
              <span class="metric-value green">{{ dashboard.agents.online }}</span>
            </div>
            <div class="metric-item">
              <span class="status-dot idle"></span>
              <span class="metric-label">Idle</span>
              <span class="metric-value">{{ dashboard.agents.idle }}</span>
            </div>
            <div class="metric-item">
              <span class="status-dot busy"></span>
              <span class="metric-label">Busy</span>
              <span class="metric-value amber">{{ dashboard.agents.busy }}</span>
            </div>
            <div class="metric-item">
              <span class="status-dot degraded"></span>
              <span class="metric-label">Degraded</span>
              <span class="metric-value red">{{ dashboard.agents.degraded }}</span>
            </div>
          </div>
        </div>
        <div v-else class="section-body" style="text-align:center;color:var(--c-text-muted);padding:40px">
          Loading...
        </div>
      </div>

      <!-- Task overview -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon class="icon"><List /></el-icon>
            Task Distribution
          </div>
        </div>
        <div class="section-body" v-if="dashboard.tasks">
          <div class="task-bar-grid">
            <div v-for="item in taskDistribution" :key="item.label" class="task-bar-item">
              <div class="task-bar-label">
                <span>{{ item.label }}</span>
                <span class="task-bar-count" :style="{ color: item.color }">{{ item.value }}</span>
              </div>
              <div class="task-bar-track">
                <div class="task-bar-fill" :style="{ width: barWidth(item.value) + '%', background: item.color }"></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="section-body" style="text-align:center;color:var(--c-text-muted);padding:40px">
          Loading...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Monitor, List, User, Coin, Connection, Ticket } from '@element-plus/icons-vue'
import { getDashboard } from '../../api/admin'

const dashboard = ref<any>({})

const statCards = computed(() => [
  { label: 'Total Agents', value: dashboard.value.agents?.total ?? '-', icon: Monitor, color: '' },
  { label: 'Online Agents', value: dashboard.value.agents?.online ?? '-', icon: Connection, color: 'green' },
  { label: 'Total Tasks', value: dashboard.value.tasks?.total ?? '-', icon: Ticket, color: 'purple' },
  { label: 'Settled Amount', value: dashboard.value.ledger?.total_credited ?? '-', icon: Coin, color: 'amber' },
])

const taskDistribution = computed(() => {
  const t = dashboard.value.tasks
  if (!t) return []
  return [
    { label: 'Queued', value: t.queued || 0, color: '#64748b' },
    { label: 'Assigned', value: t.assigned || 0, color: '#00d4ff' },
    { label: 'Submitted', value: t.submitted || 0, color: '#fbbf24' },
    { label: 'Completed', value: t.completed || 0, color: '#00ff88' },
  ]
})

function barWidth(val: number) {
  const t = dashboard.value.tasks
  if (!t) return 0
  const max = Math.max(t.queued || 0, t.assigned || 0, t.submitted || 0, t.completed || 0, 1)
  return (val / max) * 100
}

onMounted(async () => {
  try {
    const { data } = await getDashboard()
    dashboard.value = data
  } catch {}
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stat-icon {
  width: 48px; height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  flex-shrink: 0;
}
.stat-icon.green  { background: var(--c-green-dim); color: var(--c-green); }
.stat-icon.purple { background: var(--c-purple-dim); color: #a78bfa; }
.stat-icon.amber  { background: rgba(251,191,36,0.12); color: var(--c-amber); }

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* Metrics */
.metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.metric-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--c-border);
}
.metric-label {
  font-size: 13px;
  color: var(--c-text-dim);
  flex: 1;
}
.metric-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--c-text);
}
.metric-value.green { color: var(--c-green); }
.metric-value.amber { color: var(--c-amber); }
.metric-value.red   { color: var(--c-red); }

/* Task bars */
.task-bar-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.task-bar-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--c-text-dim);
  margin-bottom: 6px;
}
.task-bar-count {
  font-weight: 700;
  font-size: 15px;
}
.task-bar-track {
  height: 8px;
  background: rgba(255,255,255,0.04);
  border-radius: 4px;
  overflow: hidden;
}
.task-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.8s var(--ease-out);
  box-shadow: 0 0 10px currentColor;
}

@media (max-width: 1100px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .overview-grid { grid-template-columns: 1fr; }
}
</style>
