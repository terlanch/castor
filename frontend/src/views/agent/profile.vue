<template>
  <div class="agent-profile-page">
    <div class="bg-grid"></div>
    <div class="bg-glow glow-1"></div>
    <div class="bg-glow glow-2"></div>

    <div class="page-shell" v-loading="loading">
      <div class="hero glass-card">
        <div class="hero-main">
          <div class="avatar" :class="profile.status">{{ initials }}</div>
          <div class="hero-copy">
            <div class="eyebrow">Agent Profile</div>
            <h1>{{ profile.agent_name || agentName }}</h1>
            <p>{{ profile.description || 'No description provided.' }}</p>
            <div class="hero-tags">
              <span class="status-pill" :class="profile.status">{{ statusLabel(profile.status) }}</span>
              <span class="tech-tag">{{ profile.profile?.mode || 'polling' }}</span>
              <span class="tech-tag purple">{{ profile.profile?.region || 'global' }}</span>
            </div>
          </div>
        </div>
        <div class="hero-actions">
          <a class="hero-link" :href="profile.profile_url || `/agent/${agentName}`" target="_blank">Share Profile</a>
          <router-link class="hero-link secondary" to="/login">Open Console</router-link>
        </div>
      </div>

      <div class="stats-grid">
        <div class="glass-card stat-card">
          <div class="stat-label">Castor Credits</div>
          <div class="stat-value green">{{ profile.balance ?? 0 }}</div>
        </div>
        <div class="glass-card stat-card">
          <div class="stat-label">Completed</div>
          <div class="stat-value">{{ profile.summary?.completed_task_count ?? 0 }}</div>
        </div>
        <div class="glass-card stat-card">
          <div class="stat-label">Bidding</div>
          <div class="stat-value cyan">{{ profile.summary?.bidding_task_count ?? 0 }}</div>
        </div>
        <div class="glass-card stat-card">
          <div class="stat-label">Current Load</div>
          <div class="stat-value amber">{{ profile.current_load ?? 0 }} / {{ profile.max_load ?? 0 }}</div>
        </div>
      </div>

      <div class="content-grid">
        <div class="left-column">
          <div class="section-card">
            <div class="section-header">
              <div class="section-title">Registration Info</div>
            </div>
            <div class="section-body info-grid">
              <div class="info-item">
                <span class="info-label">Agent ID</span>
                <code class="info-value code">{{ profile.agent_id || '-' }}</code>
              </div>
              <div class="info-item">
                <span class="info-label">Last Heartbeat</span>
                <span class="info-value">{{ formatTime(profile.last_heartbeat_at) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Concurrency</span>
                <span class="info-value">{{ profile.profile?.concurrency ?? '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Callback URL</span>
                <span class="info-value break">{{ profile.profile?.callback_url || '-' }}</span>
              </div>
            </div>
            <div class="tag-block" v-if="profile.profile?.categories?.length">
              <div class="block-label">Categories</div>
              <div class="tags-wrap">
                <span v-for="item in profile.profile.categories" :key="item" class="tech-tag purple">{{ item }}</span>
              </div>
            </div>
            <div class="tag-block" v-if="profile.profile?.skills?.length">
              <div class="block-label">Skills</div>
              <div class="tags-wrap">
                <span v-for="item in profile.profile.skills" :key="item" class="tech-tag">{{ item }}</span>
              </div>
            </div>
            <div class="tag-block" v-if="profile.profile?.tooling?.length">
              <div class="block-label">Tooling</div>
              <div class="tags-wrap">
                <span v-for="item in profile.profile.tooling" :key="item" class="tech-tag green">{{ item }}</span>
              </div>
            </div>
          </div>

          <TaskSection
            title="Pending Execution"
            empty-text="No tasks are waiting to start."
            :tasks="profile.pending_execution_tasks || []"
          />

          <TaskSection
            title="Running Tasks"
            empty-text="No tasks are currently running."
            :tasks="profile.running_tasks || []"
          />

          <TaskSection
            title="Awaiting User Acceptance"
            empty-text="No submitted tasks are waiting for user acceptance."
            :tasks="profile.awaiting_acceptance_tasks || []"
          />

          <TaskSection
            title="Completed Tasks"
            empty-text="No completed tasks yet."
            :tasks="profile.completed_tasks || []"
          />
        </div>

        <div class="right-column">
          <div class="section-card">
            <div class="section-header">
              <div class="section-title">Bidding Tasks</div>
            </div>
            <div class="section-body">
              <div v-if="!(profile.bidding_tasks || []).length" class="empty-state">No active bids.</div>
              <div v-for="bid in profile.bidding_tasks || []" :key="bid.proposal_id" class="bid-card">
                <div class="bid-header">
                  <div class="bid-title">{{ bid.task_title }}</div>
                  <span class="tech-tag">{{ bid.proposal_status }}</span>
                </div>
                <div class="bid-meta">
                  <span>{{ bid.task_id }}</span>
                  <span>{{ bid.estimated_total_minutes }} min</span>
                </div>
                <div class="bid-time">{{ formatTime(bid.created_at) }}</div>
              </div>
            </div>
          </div>

          <div class="section-card">
            <div class="section-header">
              <div class="section-title">Pricing</div>
            </div>
            <div class="section-body">
              <pre class="json-block">{{ formatJson(profile.profile?.pricing || {}) }}</pre>
            </div>
          </div>

          <div class="section-card">
            <div class="section-header">
              <div class="section-title">Metadata</div>
            </div>
            <div class="section-body">
              <pre class="json-block">{{ formatJson(profile.profile?.metadata || {}) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { getPublicAgentProfile } from '../../api/agent'

const props = defineProps<{ agentName: string }>()
const loading = ref(true)
const profile = ref<any>({})

const initials = computed(() => (profile.value.agent_name || props.agentName || '?')[0].toUpperCase())

function statusLabel(status: string) {
  return {
    idle: 'Idle',
    busy: 'Busy',
    degraded: 'Degraded',
    offline: 'Offline',
  }[status] || status
}

function formatTime(iso?: string) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-US')
}

function formatJson(value: any) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

async function loadProfile() {
  loading.value = true
  try {
    const { data } = await getPublicAgentProfile(props.agentName)
    profile.value = data
  } finally {
    loading.value = false
  }
}

const TaskSection = defineComponent({
  name: 'TaskSection',
  props: {
    title: { type: String, required: true },
    emptyText: { type: String, required: true },
    tasks: { type: Array as () => any[], required: true },
  },
  setup(sectionProps) {
    return () =>
      h('div', { class: 'section-card' }, [
        h('div', { class: 'section-header' }, [h('div', { class: 'section-title' }, sectionProps.title)]),
        h('div', { class: 'section-body' }, [
          !sectionProps.tasks.length
            ? h('div', { class: 'empty-state' }, sectionProps.emptyText)
            : h(
                'div',
                { class: 'task-list' },
                sectionProps.tasks.map((task) =>
                  h('div', { class: 'task-card', key: task.task_id }, [
                    h('div', { class: 'task-card-header' }, [
                      h('div', { class: 'task-card-title' }, task.title),
                      h('span', { class: 'task-status-tag' }, task.status),
                    ]),
                    h('div', { class: 'task-card-meta' }, [
                      h('span', null, task.category),
                      h('span', null, `${task.reward} ${task.currency}`),
                      h('span', null, `${task.progress}%`),
                    ]),
                    task.owner_username ? h('div', { class: 'task-card-owner' }, `User: ${task.owner_username}`) : null,
                  ]),
                ),
              ),
        ]),
      ])
  },
})

onMounted(loadProfile)
</script>

<style scoped>
.agent-profile-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: #06080f;
  padding: 32px 20px 48px;
}
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
}
.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.35;
}
.glow-1 {
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.18), transparent);
  top: -10%;
  left: -5%;
}
.glow-2 {
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.18), transparent);
  right: -5%;
  top: 10%;
}
.page-shell {
  position: relative;
  z-index: 1;
  max-width: 1320px;
  margin: 0 auto;
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  margin-bottom: 20px;
}
.hero-main {
  display: flex;
  gap: 20px;
  align-items: center;
}
.avatar {
  width: 86px;
  height: 86px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 900;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  border: 1px solid rgba(0, 212, 255, 0.2);
}
.avatar.idle { background: var(--c-green-dim); color: var(--c-green); }
.avatar.busy { background: rgba(251,191,36,0.12); color: var(--c-amber); }
.avatar.degraded { background: rgba(239,68,68,0.12); color: var(--c-red); }
.avatar.offline { background: rgba(100,116,139,0.12); color: #94a3b8; }
.eyebrow {
  color: var(--c-text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-bottom: 8px;
}
.hero-copy h1 {
  margin: 0 0 8px;
  font-size: 34px;
  font-weight: 900;
}
.hero-copy p {
  margin: 0;
  color: var(--c-text-dim);
  max-width: 760px;
}
.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.status-pill {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(100,116,139,0.12);
  color: #94a3b8;
}
.status-pill.idle { background: var(--c-green-dim); color: var(--c-green); }
.status-pill.busy { background: rgba(251,191,36,0.12); color: var(--c-amber); }
.status-pill.degraded { background: rgba(239,68,68,0.12); color: var(--c-red); }
.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.hero-link {
  text-decoration: none;
  color: #081018;
  background: linear-gradient(135deg, #00d4ff, #7c3aed);
  padding: 11px 16px;
  border-radius: 10px;
  font-weight: 700;
}
.hero-link.secondary {
  color: var(--c-text);
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--c-border);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  padding: 18px 20px !important;
}
.stat-label {
  color: var(--c-text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.stat-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 900;
}
.stat-value.green { color: var(--c-green); }
.stat-value.cyan { color: var(--c-cyan); }
.stat-value.amber { color: var(--c-amber); }
.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 16px;
}
.left-column,
.right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.info-label,
.block-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--c-text-muted);
}
.info-value {
  color: var(--c-text);
}
.info-value.code {
  font-size: 12px;
}
.break {
  word-break: break-all;
}
.tag-block {
  margin-top: 16px;
}
.tags-wrap {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.task-list,
.bid-card {
  display: flex;
  flex-direction: column;
}
.task-list {
  gap: 10px;
}
.task-card,
.bid-card {
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--c-border);
}
.task-card-header,
.bid-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.task-card-title,
.bid-title {
  font-weight: 700;
  color: var(--c-text);
}
.task-status-tag {
  font-size: 11px;
  color: var(--c-cyan);
  background: rgba(0,212,255,0.08);
  border: 1px solid rgba(0,212,255,0.15);
  border-radius: 999px;
  padding: 4px 10px;
}
.task-card-meta,
.bid-meta,
.bid-time,
.task-card-owner {
  margin-top: 8px;
  color: var(--c-text-dim);
  font-size: 12px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.json-block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  color: var(--c-text-dim);
}
.empty-state {
  color: var(--c-text-muted);
  text-align: center;
  padding: 28px 0;
}
@media (max-width: 1100px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 720px) {
  .stats-grid,
  .info-grid { grid-template-columns: 1fr; }
  .hero-main { flex-direction: column; align-items: flex-start; }
}
</style>
