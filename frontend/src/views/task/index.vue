<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom:24px">
      <h2 class="page-title" style="margin-bottom:0">Task Management</h2>
      <el-button type="primary" @click="$router.push('/tasks/create')">
        <el-icon style="margin-right:6px"><Plus /></el-icon>
        New Task
      </el-button>
    </div>

    <!-- Task table in section card -->
    <div class="section-card">
      <div class="section-body" style="padding:0">
        <el-table :data="tasks" v-loading="loading" style="width:100%"
          :header-cell-style="{ background: 'rgba(0,212,255,0.04)', fontWeight: 700 }">
          <el-table-column label="Task" min-width="200">
            <template #default="{ row }">
              <div class="task-title-cell">
                <span class="task-title">{{ row.title }}</span>
                <span class="task-id">{{ row.task_id?.slice(0, 8) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Tags" width="220">
            <template #default="{ row }">
              <span v-for="t in (row.tags || []).slice(0,3)" :key="t" class="tech-tag">{{ t }}</span>
              <span v-if="(row.tags||[]).length > 3" class="more-count">+{{ row.tags.length-3 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="Category" width="140">
            <template #default="{ row }">
              <span class="tech-tag purple">{{ row.category }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Status" width="110">
            <template #default="{ row }">
              <span class="task-status" :class="'status-' + row.status">
                <span class="status-dot-sm" :class="row.status"></span>
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="reward" label="Budget" width="90">
            <template #default="{ row }">
              <span class="reward-value">{{ row.reward }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Progress" width="100">
            <template #default="{ row }">
              <div class="progress-mini">
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: (row.progress || 0) + '%' }"></div>
                </div>
                <span class="progress-text">{{ row.progress || 0 }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="220" fixed="right">
            <template #default="{ row }">
              <div class="action-btns">
                <el-button size="small" @click="viewCandidates(row)">
                  Candidates
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- Candidate pool dialog -->
    <el-dialog v-model="showCandidates" title="Candidate Agent Pool" width="680px" class="dark-dialog">
      <el-table :data="candidates" style="width:100%">
        <el-table-column prop="agent_name" label="Agent" width="160">
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.agent_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Score" width="100">
          <template #default="{ row }">
            <span class="score-badge">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Matched Tags">
          <template #default="{ row }">
            <span v-for="t in row.matched_tags" :key="t" class="tech-tag" style="margin:2px">{{ t }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getTasks, getTaskCandidates } from '../../api/admin'

const tasks = ref<any[]>([])
const loading = ref(true)
const showCandidates = ref(false)
const candidates = ref<any[]>([])

function statusLabel(s: string) {
  return { queued: 'Queued', assigned: 'Assigned', submitted: 'Submitted', verified: 'Verified', completed: 'Completed', rejected: 'Rejected' }[s] || s
}

async function load() {
  loading.value = true
  try {
    const { data } = await getTasks()
    tasks.value = data.tasks
  } finally {
    loading.value = false
  }
}

async function viewCandidates(row: any) {
  const { data } = await getTaskCandidates(row.task_id)
  candidates.value = data.candidates
  showCandidates.value = true
}

onMounted(load)
</script>

<style scoped>
.task-title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.task-title {
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
.status-dot-sm {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--c-text-muted);
}
.status-dot-sm.queued { background: #64748b; }
.status-dot-sm.assigned { background: var(--c-cyan); box-shadow: 0 0 6px var(--c-cyan); }
.status-dot-sm.submitted { background: var(--c-amber); box-shadow: 0 0 6px var(--c-amber); }
.status-dot-sm.verified, .status-dot-sm.completed { background: var(--c-green); box-shadow: 0 0 6px var(--c-green); }
.status-dot-sm.rejected { background: var(--c-red); box-shadow: 0 0 6px var(--c-red); }

.status-queued    { color: var(--c-text-muted); }
.status-assigned  { color: var(--c-cyan); }
.status-submitted { color: var(--c-amber); }
.status-verified, .status-completed { color: var(--c-green); }
.status-rejected  { color: var(--c-red); }

.reward-value {
  font-weight: 700;
  font-size: 13px;
  color: var(--c-amber);
}

.progress-mini {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-bar {
  flex: 1;
  height: 5px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-cyan), var(--c-purple));
  border-radius: 3px;
  transition: width 0.6s var(--ease-out);
}
.progress-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-dim);
  min-width: 30px;
  text-align: right;
}

.more-count {
  font-size: 11px;
  color: var(--c-text-muted);
  margin-left: 2px;
}

.action-btns {
  display: flex;
  gap: 6px;
}

.score-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 700;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  border: 1px solid rgba(0,212,255,0.2);
}
</style>
