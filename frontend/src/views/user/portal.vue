<template>
  <div class="page-container">
    <h2 class="page-title">User Portal</h2>

    <!-- Stat cards -->
    <div class="user-stats stagger-grid">
      <div class="glass-card stat-card">
        <div class="stat-icon-wrap">
          <el-icon :size="20"><User /></el-icon>
        </div>
        <div>
          <div class="stat-label">Username</div>
          <div class="stat-value">{{ profile.username || '-' }}</div>
        </div>
      </div>
      <div class="glass-card stat-card">
        <div class="stat-icon-wrap green">
          <el-icon :size="20"><Coin /></el-icon>
        </div>
        <div>
          <div class="stat-label">Available Balance</div>
          <div class="stat-value green">{{ profile.balance ?? '-' }}</div>
        </div>
      </div>
      <div class="glass-card stat-card">
        <div class="stat-icon-wrap amber">
          <el-icon :size="20"><Lock /></el-icon>
        </div>
        <div>
          <div class="stat-label">Frozen Balance</div>
          <div class="stat-value amber">{{ profile.frozen_balance ?? '-' }}</div>
        </div>
      </div>
    </div>

    <!-- Top-up section -->
    <div class="section-card" style="margin-bottom:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">💰</span>
          Top Up
        </div>
      </div>
      <div class="section-body">
        <div class="topup-row">
          <el-input-number v-model="topupAmount" :min="1" :max="100000" />
          <el-button type="primary" @click="handleTopup">
            <el-icon style="margin-right:4px"><Coin /></el-icon>
            Add Funds
          </el-button>
        </div>
      </div>
    </div>

    <!-- My tasks -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📋</span>
          My Tasks
        </div>
        <el-button size="small" @click="loadTasks">Refresh</el-button>
      </div>
      <div class="section-body" style="padding:0">
        <el-table :data="tasks" v-loading="tasksLoading" style="width:100%">
          <el-table-column label="Task" min-width="180">
            <template #default="{ row }">
              <div class="task-cell">
                <span class="task-name">{{ row.title }}</span>
                <span class="task-id">{{ row.task_id?.slice(0, 8) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Tags" width="200">
            <template #default="{ row }">
              <span v-for="t in (row.tags||[]).slice(0,3)" :key="t" class="tech-tag">{{ t }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Status" width="120">
            <template #default="{ row }">
              <span class="task-status" :class="'s-' + row.status">
                <span class="s-dot" :class="row.status"></span>
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="reward" label="Budget" width="80">
            <template #default="{ row }">
              <span style="font-weight:700;color:var(--c-amber)">{{ row.reward }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Progress" width="110">
            <template #default="{ row }">
              <div class="progress-mini">
                <div class="progress-track">
                  <div class="progress-bar-fill" :style="{ width: (row.progress || 0) + '%' }"></div>
                </div>
                <span class="progress-label">{{ row.progress || 0 }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="220" fixed="right">
            <template #default="{ row }">
              <div class="action-group">
                <el-button size="small" type="primary" @click="$router.push(`/portal/task/${row.task_id}`)">
                  Details
                </el-button>
                <el-button v-if="['submitted', 'verified'].includes(row.status)" size="small" type="success" @click="handleAccept(row.task_id)">
                  Accept & Pay
                </el-button>
                <el-button v-if="['submitted', 'verified'].includes(row.status)" size="small" @click="handleReject(row.task_id)">
                  Reject Result
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- Empty state -->
        <div v-if="!tasksLoading && !tasks.length" class="empty-tasks">
          <div class="empty-icon">📭</div>
          <p>No tasks yet. <router-link to="/tasks/create" class="link">Create one</router-link></p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Coin, Lock } from '@element-plus/icons-vue'
import { getUserProfile, topupUser, getUserTasks, acceptTaskResult, rejectTaskResult } from '../../api/user'

const profile = ref<any>({})
const tasks = ref<any[]>([])
const tasksLoading = ref(true)
const topupAmount = ref(100)

function statusLabel(s: string) {
  const map: Record<string, string> = { queued: 'Bidding', assigned: 'In Progress', submitted: 'Submitted', verified: 'Pending Review', completed: 'Completed', rejected: 'Rejected' }
  return map[s] || s
}

async function loadProfile() {
  const { data } = await getUserProfile()
  profile.value = data
}
async function loadTasks() {
  tasksLoading.value = true
  try {
    const { data } = await getUserTasks()
    tasks.value = data.tasks
  } finally {
    tasksLoading.value = false
  }
}
async function handleTopup() {
  await topupUser(topupAmount.value)
  ElMessage.success('Top-up successful')
  loadProfile()
}
async function handleAccept(taskId: string) {
  await acceptTaskResult(taskId)
  ElMessage.success('Result accepted and payment completed')
  loadProfile()
  loadTasks()
}

async function handleReject(taskId: string) {
  await rejectTaskResult(taskId)
  ElMessage.success('Result rejected and task reopened')
  loadTasks()
}

onMounted(() => {
  loadProfile().catch(() => {})
  loadTasks()
})
</script>

<style scoped>
/* Stats */
.user-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stat-icon-wrap {
  width: 48px; height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  flex-shrink: 0;
}
.stat-icon-wrap.green { background: var(--c-green-dim); color: var(--c-green); }
.stat-icon-wrap.amber { background: rgba(251,191,36,0.12); color: var(--c-amber); }

.section-icon {
  font-size: 16px;
}

/* Topup */
.topup-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Task cells */
.task-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.task-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text);
}
.task-id {
  font-size: 11px;
  color: var(--c-text-muted);
  font-family: monospace;
}

.task-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
}
.s-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--c-text-muted);
}
.s-dot.queued { background: #64748b; }
.s-dot.assigned { background: var(--c-cyan); box-shadow: 0 0 6px var(--c-cyan); }
.s-dot.submitted { background: var(--c-amber); box-shadow: 0 0 6px var(--c-amber); }
.s-dot.verified, .s-dot.completed { background: var(--c-green); box-shadow: 0 0 6px var(--c-green); }
.s-dot.rejected { background: var(--c-red); box-shadow: 0 0 6px var(--c-red); }
.s-queued    { color: var(--c-text-muted); }
.s-assigned  { color: var(--c-cyan); }
.s-submitted { color: var(--c-amber); }
.s-verified, .s-completed { color: var(--c-green); }
.s-rejected  { color: var(--c-red); }

/* Progress */
.progress-mini {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-track {
  flex: 1;
  height: 5px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-cyan), var(--c-purple));
  border-radius: 3px;
  transition: width 0.6s var(--ease-out);
}
.progress-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-dim);
  min-width: 30px;
  text-align: right;
}

.action-group {
  display: flex;
  gap: 6px;
}

/* Empty */
.empty-tasks {
  text-align: center;
  padding: 48px 0;
  color: var(--c-text-muted);
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 10px;
}
.link {
  color: var(--c-cyan);
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}

@media (max-width: 900px) {
  .user-stats { grid-template-columns: 1fr; }
}
</style>
