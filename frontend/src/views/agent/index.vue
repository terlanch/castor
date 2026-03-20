<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 24px">
      <h2 class="page-title" style="margin-bottom:0">Agent Management</h2>
      <div class="agent-count">
        <span class="count-num">{{ agents.length }}</span>
        <span class="count-label">Registered</span>
      </div>
    </div>

    <!-- Agent cards grid -->
    <div class="agents-grid stagger-grid" v-loading="loading">
      <div v-for="agent in agents" :key="agent.agent_id" class="agent-card glass-card">
        <!-- Status indicator bar -->
        <div class="agent-status-bar" :class="agent.status"></div>

        <div class="agent-card-body">
          <!-- Header -->
          <div class="agent-header">
            <div class="agent-avatar" :class="agent.status">
              <span>{{ (agent.agent_name || '?')[0].toUpperCase() }}</span>
            </div>
            <div class="agent-info">
              <div class="agent-name">{{ agent.agent_name }}</div>
              <div class="agent-desc">{{ agent.description || 'No description' }}</div>
            </div>
          </div>

          <!-- Status & load -->
          <div class="agent-meta">
            <div class="meta-item">
              <span class="status-dot" :class="agent.status"></span>
              <span class="meta-label" :class="'status-' + agent.status">{{ statusLabel(agent.status) }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-icon">⚡</span>
              <span class="meta-label">{{ agent.current_load }} / {{ agent.max_load }}</span>
            </div>
            <div class="meta-item" v-if="agent.region">
              <span class="meta-icon">🌍</span>
              <span class="meta-label">{{ agent.region }}</span>
            </div>
          </div>

          <!-- Skills -->
          <div class="agent-skills" v-if="agent.skills?.length">
            <span v-for="s in agent.skills.slice(0, 5)" :key="s" class="tech-tag">{{ s }}</span>
            <span v-if="agent.skills.length > 5" class="more-badge">+{{ agent.skills.length - 5 }}</span>
          </div>

          <!-- Footer -->
          <div class="agent-footer">
            <div class="footer-item">
              <span class="footer-label">Balance</span>
              <span class="footer-value">{{ agent.balance ?? 0 }}</span>
            </div>
            <div class="footer-item">
              <span class="footer-label">Last Heartbeat</span>
              <span class="footer-value small">{{ formatTime(agent.last_heartbeat_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && !agents.length" class="empty-state">
      <div class="empty-icon">🤖</div>
      <p>No registered agents yet</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAgents } from '../../api/admin'

const agents = ref<any[]>([])
const loading = ref(true)

function statusLabel(s: string) {
  return { idle: 'Idle', busy: 'Busy', degraded: 'Degraded', offline: 'Offline' }[s] || s
}

function formatTime(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString('en-US')
}

onMounted(async () => {
  try {
    const { data } = await getAgents()
    agents.value = data.agents
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.agent-count {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.count-num {
  font-size: 28px;
  font-weight: 800;
  background: linear-gradient(135deg, #fff 30%, var(--c-cyan));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.count-label {
  font-size: 12px;
  color: var(--c-text-muted);
  font-weight: 500;
}

/* Grid */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

/* Card */
.agent-card {
  padding: 0 !important;
  position: relative;
  overflow: hidden;
}
.agent-status-bar {
  height: 3px;
  background: var(--c-text-muted);
  transition: background 0.3s;
}
.agent-status-bar.idle, .agent-status-bar.online {
  background: linear-gradient(90deg, var(--c-green), rgba(0,255,136,0.3));
  box-shadow: 0 0 12px rgba(0,255,136,0.3);
}
.agent-status-bar.busy {
  background: linear-gradient(90deg, var(--c-amber), rgba(251,191,36,0.3));
  box-shadow: 0 0 12px rgba(251,191,36,0.3);
}
.agent-status-bar.degraded {
  background: linear-gradient(90deg, var(--c-red), rgba(239,68,68,0.3));
  box-shadow: 0 0 12px rgba(239,68,68,0.3);
}

.agent-card-body {
  padding: 20px;
}

/* Header */
.agent-header {
  display: flex;
  gap: 14px;
  margin-bottom: 16px;
}
.agent-avatar {
  width: 44px; height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 800;
  flex-shrink: 0;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  border: 1px solid rgba(0,212,255,0.2);
}
.agent-avatar.idle, .agent-avatar.online {
  background: var(--c-green-dim);
  color: var(--c-green);
  border-color: rgba(0,255,136,0.2);
}
.agent-avatar.busy {
  background: rgba(251,191,36,0.12);
  color: var(--c-amber);
  border-color: rgba(251,191,36,0.2);
}
.agent-avatar.offline {
  background: rgba(100,116,139,0.12);
  color: var(--c-text-muted);
  border-color: rgba(100,116,139,0.2);
}
.agent-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text);
  margin-bottom: 3px;
}
.agent-desc {
  font-size: 12px;
  color: var(--c-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

/* Meta */
.agent-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-dim);
}
.meta-icon {
  font-size: 12px;
}
.status-idle   { color: var(--c-green); }
.status-busy   { color: var(--c-amber); }
.status-degraded { color: var(--c-red); }
.status-offline  { color: var(--c-text-muted); }

/* Skills */
.agent-skills {
  margin-bottom: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.more-badge {
  font-size: 11px;
  color: var(--c-text-muted);
  padding: 2px 6px;
}

/* Footer */
.agent-footer {
  display: flex;
  justify-content: space-between;
  padding-top: 14px;
  border-top: 1px solid var(--c-border);
}
.footer-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.footer-label {
  font-size: 10px;
  color: var(--c-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.footer-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text);
}
.footer-value.small {
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-dim);
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 60px 0;
  color: var(--c-text-muted);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
</style>
