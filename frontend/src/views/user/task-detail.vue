<template>
  <div class="page-container">
    <!-- Header -->
    <div class="detail-header">
      <el-button class="back-btn" @click="$router.push('/portal')">
        <el-icon><ArrowLeft /></el-icon>
        Back
      </el-button>
      <div class="header-info">
        <h2 class="detail-title">{{ task.title || 'Task Details' }}</h2>
        <span class="task-status-badge" :class="'badge-' + task.status">
          <span class="badge-dot"></span>
          {{ statusLabel(task.status) }}
        </span>
      </div>
    </div>

    <!-- Task info -->
    <div class="detail-grid">
      <div class="section-card info-card">
        <div class="section-header">
          <div class="section-title">
            <span class="section-icon">📝</span> Task Info
          </div>
        </div>
        <div class="section-body">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Goal</span>
              <span class="info-value">{{ task.goal || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Category</span>
              <span class="tech-tag purple">{{ task.category }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Budget</span>
              <span class="info-value reward">{{ task.reward }} {{ task.currency }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Progress</span>
              <div class="info-progress">
                <div class="mini-bar"><div class="mini-fill" :style="{ width: (task.progress||0) + '%' }"></div></div>
                <span class="progress-num">{{ task.progress || 0 }}%</span>
              </div>
            </div>
          </div>
          <div class="info-tags" v-if="(task.tags || []).length">
            <span class="info-label">Tags</span>
            <div class="tags-wrap">
              <span v-for="t in task.tags" :key="t" class="tech-tag">{{ t }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Proposals (queued status) -->
    <div v-if="task.status === 'queued' || proposals.length > 0" class="section-card" style="margin-top:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">🤖</span>
          Agent Proposals
          <span v-if="proposals.length" class="proposal-count">{{ proposals.length }}</span>
        </div>
        <el-button size="small" @click="loadProposals" :loading="proposalsLoading">Refresh</el-button>
      </div>
      <div class="section-body">
        <!-- Empty state -->
        <div v-if="!proposals.length && !proposalsLoading" class="empty-proposals">
          <div class="pulse-ring">
            <div class="pulse-core">⏳</div>
          </div>
          <p>Waiting for agents to submit proposals...</p>
        </div>

        <!-- Proposals list -->
        <div v-for="p in proposals" :key="p.proposal_id" class="proposal-card" :class="{ accepted: p.status === 'accepted', rejected: p.status === 'rejected' }">
          <!-- Proposal header -->
          <div class="proposal-header">
            <div class="proposal-agent">
              <div class="agent-avatar">{{ (p.agent_name || '?')[0].toUpperCase() }}</div>
              <div>
                <span class="agent-name">{{ p.agent_name }}</span>
                <span class="proposal-badge" :class="'badge-' + p.status">{{ proposalStatusLabel(p.status) }}</span>
              </div>
            </div>
            <div class="proposal-meta">
              <span class="meta-time">⏱ {{ p.estimated_total_minutes }} min</span>
              <span class="meta-date">{{ formatTime(p.created_at) }}</span>
            </div>
          </div>

          <!-- Message -->
          <div v-if="p.message" class="proposal-message">
            <span class="msg-icon">💬</span>
            {{ p.message }}
          </div>

          <!-- Steps -->
          <div class="plan-steps">
            <div v-for="step in p.plan_steps" :key="step.step_number" class="plan-step">
              <div class="step-num" :class="stepStatusClass(step.status)">{{ step.step_number }}</div>
              <div class="step-content">
                <div class="step-header-row">
                  <span class="step-title">{{ step.title }}</span>
                  <span class="step-duration">~{{ step.estimated_minutes }}min</span>
                </div>
                <div v-if="step.description" class="step-desc">{{ step.description }}</div>
                <span v-if="step.status && step.status !== 'pending'" class="tech-tag" :class="stepTagClass(step.status)">{{ step.status }}</span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div v-if="p.status === 'pending' && task.status === 'queued'" class="proposal-actions">
            <el-button type="primary" size="small" @click="handleAcceptProposal(p.proposal_id)">
              ✅ Select Proposal
            </el-button>
            <el-button size="small" @click="handleRejectProposal(p.proposal_id)">
              Reject
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Execution progress -->
    <div v-if="['assigned', 'submitted', 'verified', 'completed'].includes(task.status)" class="section-card" style="margin-top:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">🚀</span> Execution Progress
        </div>
        <el-button size="small" @click="loadProgress" :loading="progressLoading">Refresh</el-button>
      </div>
      <div class="section-body">
        <!-- Accepted proposal info -->
        <div v-if="acceptedProposal" class="accepted-banner">
          <div class="accepted-agent">
            <div class="agent-avatar small">{{ (acceptedProposal.agent_name || '?')[0].toUpperCase() }}</div>
            <span>Assigned Agent: <strong>{{ acceptedProposal.agent_name }}</strong></span>
          </div>
        </div>

        <!-- Step progress -->
        <div v-if="acceptedProposal" class="execution-steps">
          <div v-for="step in acceptedProposal.plan_steps" :key="step.step_number"
            class="exec-step" :class="{ done: step.status === 'completed', active: step.status === 'in_progress' }">
            <div class="exec-step-indicator">
              <div class="exec-dot" :class="step.status">
                <el-icon v-if="step.status === 'completed'" :size="12"><Check /></el-icon>
                <el-icon v-else-if="step.status === 'in_progress'" :size="12"><Loading /></el-icon>
                <span v-else class="dot-num">{{ step.step_number }}</span>
              </div>
              <div v-if="step.step_number < acceptedProposal.plan_steps.length" class="exec-line" :class="step.status"></div>
            </div>
            <div class="exec-step-content">
              <div class="exec-step-title">{{ step.title }}</div>
              <div class="exec-step-desc">{{ step.description || `Estimated ${step.estimated_minutes} min` }}</div>
            </div>
          </div>
        </div>

        <!-- Timeline logs -->
        <div v-if="progressLogs.length" class="progress-timeline">
          <div class="timeline-title">Execution Log</div>
          <div v-for="(log, idx) in progressLogs" :key="idx" class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="timeline-msg">
                <span v-if="log.step_number" class="step-ref">Step {{ log.step_number }}</span>
                {{ log.message }}
                <span v-if="log.progress !== undefined" class="log-progress">{{ log.progress }}%</span>
              </div>
              <div class="timeline-time">{{ formatTime(log.at) }}</div>
            </div>
          </div>
        </div>

        <div v-if="!progressLogs.length && !progressLoading" class="empty-progress">
          The agent has not started execution yet
        </div>
      </div>
    </div>

    <!-- Submission Result -->
    <div v-if="submission && ['submitted', 'verified', 'completed'].includes(task.status)" class="section-card" style="margin-top:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📦</span> Task Result
        </div>
        <span class="submit-time" v-if="submission.submitted_at">{{ formatTime(submission.submitted_at) }}</span>
      </div>
      <div class="section-body">
        <!-- Output data -->
        <div class="result-section">
          <div class="result-section-label">Deliverable (Output)</div>
          <div class="result-json-block">
            <pre class="json-pre">{{ formatJson(submission.output) }}</pre>
          </div>
        </div>

        <!-- Proof -->
        <div v-if="submission.proof" class="result-section">
          <div class="result-section-label">Execution Proof</div>
          <div class="proof-grid">
            <div v-if="submission.proof.trace_id" class="proof-item">
              <span class="proof-label">Trace ID</span>
              <code class="proof-value">{{ submission.proof.trace_id }}</code>
            </div>
            <div v-if="submission.proof.artifacts?.length" class="proof-item">
              <span class="proof-label">Artifacts</span>
              <div class="proof-links">
                <a v-for="(url, i) in submission.proof.artifacts" :key="i" :href="url" target="_blank" class="artifact-link">
                  📎 {{ extractFilename(url) }}
                </a>
              </div>
            </div>
            <div v-if="submission.proof.tool_usage?.length" class="proof-item">
              <span class="proof-label">Tools Used</span>
              <div>
                <span v-for="tool in submission.proof.tool_usage" :key="tool" class="tech-tag">{{ tool }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats -->
        <div v-if="submission.stats" class="result-section">
          <div class="result-section-label">Execution Stats</div>
          <div class="stats-grid">
            <div v-if="submission.stats.duration_seconds" class="stat-mini">
              <span class="stat-mini-value">{{ formatDuration(submission.stats.duration_seconds) }}</span>
              <span class="stat-mini-label">Duration</span>
            </div>
            <div v-if="submission.stats.input_tokens" class="stat-mini">
              <span class="stat-mini-value">{{ submission.stats.input_tokens.toLocaleString() }}</span>
              <span class="stat-mini-label">Input Tokens</span>
            </div>
            <div v-if="submission.stats.output_tokens" class="stat-mini">
              <span class="stat-mini-value">{{ submission.stats.output_tokens.toLocaleString() }}</span>
              <span class="stat-mini-label">Output Tokens</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Uploaded Files -->
    <div v-if="uploadedFiles.length" class="section-card" style="margin-top:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📁</span> Deliverable Files
        </div>
        <span class="files-count">{{ uploadedFiles.length }} files</span>
      </div>
      <div class="section-body">
        <div class="file-list">
          <div v-for="f in uploadedFiles" :key="f.file_id" class="file-card">
            <div class="file-icon">{{ getFileIcon(f.original_filename) }}</div>
            <div class="file-info">
              <div class="file-name">{{ f.original_filename }}</div>
              <div class="file-meta">
                <span>{{ formatFileSize(f.size_bytes) }}</span>
                <span class="file-meta-sep">·</span>
                <span>{{ formatTime(f.uploaded_at) }}</span>
              </div>
            </div>
            <a :href="f.download_url" target="_blank" class="file-download-btn">
              <el-icon :size="16"><Download /></el-icon>
              Download
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- Acceptance / Payment -->
    <div v-if="['submitted', 'verified'].includes(task.status)" class="section-card acceptance-card" style="margin-top:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">🎯</span> Result Review
        </div>
      </div>
      <div class="section-body">
        <p style="margin:0 0 16px;color:var(--c-text-dim)">The agent has submitted the result. You can now review it and either accept payment or reject the delivery.</p>
        <div class="action-row">
          <el-button type="success" size="large" @click="handleAcceptResult">
            ✅ Accept Result & Pay {{ task.reward }} CASTOR_CREDIT
          </el-button>
          <el-button size="large" @click="handleRejectResult">
            Reject Result
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Check, Loading, Download } from '@element-plus/icons-vue'
import { getUserTasks, getTaskProposals, acceptProposal, rejectProposal, getTaskProgress, acceptTaskResult, rejectTaskResult } from '../../api/user'

const props = defineProps<{ taskId: string }>()
const router = useRouter()

const task = ref<any>({})
const proposals = ref<any[]>([])
const proposalsLoading = ref(false)
const acceptedProposal = ref<any>(null)
const progressLogs = ref<any[]>([])
const progressLoading = ref(false)
const submission = ref<any>(null)
const uploadedFiles = ref<any[]>([])

function statusLabel(s: string) {
  return { queued: 'Bidding', assigned: 'In Progress', submitted: 'Submitted', verified: 'Pending Review', completed: 'Completed', rejected: 'Rejected' }[s] || s
}
function proposalStatusLabel(s: string) {
  return { pending: 'Pending', accepted: 'Accepted', rejected: 'Rejected', withdrawn: 'Withdrawn' }[s] || s
}

function stepStatusClass(s: string) {
  return { pending: 'step-pending', in_progress: 'step-active', completed: 'step-done', skipped: 'step-skipped' }[s] || 'step-pending'
}
function stepTagClass(s: string) {
  return { in_progress: 'amber', completed: 'green', skipped: '' }[s] || ''
}

function formatTime(iso: string) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-US')
}
function formatJson(obj: any) {
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}
function extractFilename(url: string) {
  try { return url.split('/').pop() || url } catch { return url }
}
function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}
function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const icons: Record<string, string> = {
    zip: '🗜️', '7z': '🗜️', rar: '🗜️', tar: '🗜️', gz: '🗜️', tgz: '🗜️',
    pdf: '📄', doc: '📄', docx: '📄',
    xls: '📊', xlsx: '📊', csv: '📊',
    json: '📋', xml: '📋', yaml: '📋', yml: '📋',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', webp: '🖼️', svg: '🖼️',
    txt: '📝', md: '📝',
    py: '🐍', js: '💛', ts: '💙', html: '🌐', css: '🎨',
  }
  return icons[ext] || '📎'
}

async function loadTask() {
  const { data } = await getUserTasks()
  const found = (data.tasks || []).find((t: any) => t.task_id === props.taskId)
  if (found) task.value = found
}
async function loadProposals() {
  proposalsLoading.value = true
  try {
    const { data } = await getTaskProposals(props.taskId)
    proposals.value = data.proposals || []
  } finally {
    proposalsLoading.value = false
  }
}
async function loadProgress() {
  progressLoading.value = true
  try {
    const { data } = await getTaskProgress(props.taskId)
    acceptedProposal.value = data.proposal
    progressLogs.value = data.progress_logs || []
    submission.value = data.submission || null
    uploadedFiles.value = data.files || []
  } finally {
    progressLoading.value = false
  }
}
async function handleAcceptProposal(proposalId: string) {
  await ElMessageBox.confirm('Confirm selecting this agent proposal? Once confirmed, the task will be assigned to this agent.', 'Confirm Selection')
  await acceptProposal(props.taskId, proposalId)
  ElMessage.success('Proposal selected, task assigned to the agent')
  await loadTask()
  await loadProposals()
  await loadProgress()
}
async function handleRejectProposal(proposalId: string) {
  await rejectProposal(props.taskId, proposalId)
  ElMessage.success('Proposal rejected')
  await loadProposals()
}
async function handleAcceptResult() {
  await ElMessageBox.confirm(`Confirm accepting the result and paying ${task.value.reward} CASTOR_CREDIT?`, 'Confirm Payment')
  await acceptTaskResult(props.taskId)
  ElMessage.success('Result accepted and payment completed')
  await loadTask()
}

async function handleRejectResult() {
  await ElMessageBox.confirm('Confirm rejecting this submitted result? The task will be reopened for a new proposal.', 'Reject Result')
  await rejectTaskResult(props.taskId)
  ElMessage.success('Result rejected and task reopened')
  await loadTask()
  await loadProposals()
}

onMounted(async () => {
  await loadTask()
  await loadProposals()
  if (['assigned', 'submitted', 'verified', 'completed'].includes(task.value.status)) {
    await loadProgress()
  }
})
</script>

<style scoped>
/* Header */
.detail-header {
  margin-bottom: 24px;
}
.back-btn {
  margin-bottom: 16px;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.detail-title {
  font-size: 24px;
  font-weight: 800;
  margin: 0;
  background: linear-gradient(135deg, #fff 30%, var(--c-cyan));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.task-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.badge-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}
.badge-queued    { background: rgba(100,116,139,0.12); color: #94a3b8; border: 1px solid rgba(100,116,139,0.2); }
.badge-assigned  { background: var(--c-cyan-dim); color: var(--c-cyan); border: 1px solid rgba(0,212,255,0.2); }
.badge-submitted { background: rgba(251,191,36,0.12); color: var(--c-amber); border: 1px solid rgba(251,191,36,0.2); }
.badge-verified, .badge-completed { background: var(--c-green-dim); color: var(--c-green); border: 1px solid rgba(0,255,136,0.2); }
.badge-rejected  { background: var(--c-red-dim); color: var(--c-red); border: 1px solid rgba(239,68,68,0.2); }

.section-icon {
  font-size: 16px;
}

/* Info grid */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.info-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.info-value {
  font-size: 14px;
  color: var(--c-text);
}
.info-value.reward {
  font-weight: 700;
  color: var(--c-amber);
  font-size: 16px;
}
.info-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}
.mini-bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
  max-width: 120px;
}
.mini-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-cyan), var(--c-purple));
  border-radius: 3px;
  transition: width 0.6s var(--ease-out);
}
.progress-num {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-cyan);
}
.info-tags {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--c-border);
}
.tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* Proposals */
.proposal-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  border-radius: 11px;
  background: var(--c-cyan);
  color: #000;
  font-size: 11px;
  font-weight: 700;
  padding: 0 6px;
}

.empty-proposals {
  text-align: center;
  padding: 40px 0;
  color: var(--c-text-muted);
}
.pulse-ring {
  width: 60px; height: 60px;
  border-radius: 50%;
  border: 2px solid rgba(0,212,255,0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  animation: pulseRing 2s ease-in-out infinite;
}
.pulse-core {
  font-size: 24px;
}
@keyframes pulseRing {
  0%, 100% { border-color: rgba(0,212,255,0.15); transform: scale(1); }
  50%      { border-color: rgba(0,212,255,0.3); transform: scale(1.05); }
}

/* Proposal card */
.proposal-card {
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  background: rgba(255,255,255,0.015);
  transition: all 0.3s var(--ease-out);
}
.proposal-card:hover {
  border-color: var(--c-border-glow);
  background: rgba(0,212,255,0.02);
}
.proposal-card.accepted {
  border-color: rgba(0,255,136,0.25);
  background: rgba(0,255,136,0.03);
}
.proposal-card.rejected {
  opacity: 0.5;
}

.proposal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.proposal-agent {
  display: flex;
  align-items: center;
  gap: 12px;
}
.agent-avatar {
  width: 40px; height: 40px;
  border-radius: 10px;
  background: var(--c-cyan-dim);
  color: var(--c-cyan);
  border: 1px solid rgba(0,212,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 800;
  flex-shrink: 0;
}
.agent-avatar.small {
  width: 32px; height: 32px;
  font-size: 14px;
  border-radius: 8px;
}
.agent-name {
  font-weight: 700;
  font-size: 14px;
  color: var(--c-text);
  margin-right: 8px;
}
.proposal-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.badge-pending  { background: rgba(251,191,36,0.12); color: var(--c-amber); }
.badge-accepted { background: var(--c-green-dim); color: var(--c-green); }
.badge-rejected { background: var(--c-red-dim); color: var(--c-red); }
.badge-withdrawn { background: rgba(100,116,139,0.12); color: var(--c-text-muted); }

.proposal-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 12px;
  color: var(--c-text-muted);
}
.meta-time {
  color: var(--c-text-dim);
}

/* Message */
.proposal-message {
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--c-text-dim);
  display: flex;
  gap: 8px;
}
.msg-icon {
  flex-shrink: 0;
}

/* Plan steps */
.plan-steps {
  margin-bottom: 14px;
}
.plan-step {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.plan-step:last-child { border-bottom: none; }
.step-num {
  width: 28px; height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  background: rgba(255,255,255,0.04);
  color: var(--c-text-muted);
  border: 1px solid var(--c-border);
}
.step-num.step-active { background: var(--c-cyan-dim); color: var(--c-cyan); border-color: rgba(0,212,255,0.3); }
.step-num.step-done   { background: var(--c-green-dim); color: var(--c-green); border-color: rgba(0,255,136,0.3); }
.step-content { flex: 1; }
.step-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.step-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text);
}
.step-duration {
  font-size: 11px;
  color: var(--c-text-muted);
}
.step-desc {
  font-size: 12px;
  color: var(--c-text-dim);
  margin-top: 4px;
}

.proposal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 14px;
  border-top: 1px solid var(--c-border);
}

/* Execution steps */
.accepted-banner {
  padding: 14px 16px;
  background: rgba(0,255,136,0.04);
  border: 1px solid rgba(0,255,136,0.12);
  border-radius: 10px;
  margin-bottom: 20px;
}
.accepted-agent {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--c-green);
}

.execution-steps {
  margin-bottom: 24px;
}
.exec-step {
  display: flex;
  gap: 16px;
}
.exec-step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}
.exec-dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  background: rgba(255,255,255,0.04);
  border: 2px solid var(--c-border);
  color: var(--c-text-muted);
  transition: all 0.3s;
}
.exec-dot.completed { background: var(--c-green); border-color: var(--c-green); color: #000; box-shadow: 0 0 12px rgba(0,255,136,0.3); }
.exec-dot.in_progress { background: var(--c-cyan); border-color: var(--c-cyan); color: #000; box-shadow: 0 0 12px rgba(0,212,255,0.3); animation: dotPulse 2s ease-in-out infinite; }
.dot-num { font-size: 11px; }
@keyframes dotPulse {
  0%, 100% { box-shadow: 0 0 12px rgba(0,212,255,0.3); }
  50%      { box-shadow: 0 0 24px rgba(0,212,255,0.5); }
}
.exec-line {
  width: 2px;
  flex: 1;
  min-height: 24px;
  background: var(--c-border);
  transition: background 0.3s;
}
.exec-line.completed { background: var(--c-green); }
.exec-line.in_progress { background: linear-gradient(180deg, var(--c-cyan), var(--c-border)); }

.exec-step-content {
  padding-bottom: 20px;
}
.exec-step-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--c-text);
  margin-bottom: 4px;
}
.exec-step.done .exec-step-title { color: var(--c-green); }
.exec-step.active .exec-step-title { color: var(--c-cyan); }
.exec-step-desc {
  font-size: 12px;
  color: var(--c-text-dim);
}

/* Timeline */
.progress-timeline {
  border-top: 1px solid var(--c-border);
  padding-top: 20px;
}
.timeline-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text-dim);
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.timeline-item {
  display: flex;
  gap: 14px;
  padding-bottom: 16px;
  position: relative;
}
.timeline-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 14px;
  bottom: 0;
  width: 1px;
  background: var(--c-border);
}
.timeline-dot {
  width: 9px; height: 9px;
  border-radius: 50%;
  background: var(--c-cyan);
  flex-shrink: 0;
  margin-top: 4px;
  box-shadow: 0 0 6px var(--c-cyan);
}
.timeline-content { flex: 1; }
.timeline-msg {
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.5;
}
.step-ref {
  font-weight: 600;
  color: var(--c-cyan);
  margin-right: 4px;
}
.log-progress {
  color: var(--c-cyan);
  font-weight: 600;
  margin-left: 6px;
}
.timeline-time {
  font-size: 11px;
  color: var(--c-text-muted);
  margin-top: 2px;
}

.empty-progress {
  text-align: center;
  color: var(--c-text-muted);
  padding: 30px 0;
}

/* Submission result */
.submit-time {
  font-size: 12px;
  color: var(--c-text-muted);
}
.result-section {
  margin-bottom: 20px;
}
.result-section:last-child { margin-bottom: 0; }
.result-section-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text-dim);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.result-json-block {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 16px 20px;
  overflow-x: auto;
}
.json-pre {
  margin: 0;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.7;
  color: var(--c-cyan);
  white-space: pre-wrap;
  word-break: break-all;
}
.proof-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.proof-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.proof-label {
  font-size: 12px;
  color: var(--c-text-muted);
  min-width: 70px;
  flex-shrink: 0;
  padding-top: 2px;
}
.proof-value {
  font-size: 12px;
  background: rgba(0,212,255,0.06);
  color: var(--c-cyan);
  padding: 2px 10px;
  border-radius: 6px;
  border: 1px solid rgba(0,212,255,0.12);
}
.proof-links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.artifact-link {
  font-size: 12px;
  color: var(--c-cyan);
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(0,212,255,0.04);
  border: 1px solid rgba(0,212,255,0.1);
  transition: all 0.2s;
}
.artifact-link:hover {
  background: rgba(0,212,255,0.08);
  border-color: rgba(0,212,255,0.25);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.stat-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--c-border);
}
.stat-mini-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--c-text);
}
.stat-mini-label {
  font-size: 11px;
  color: var(--c-text-muted);
}

/* Uploaded files */
.files-count {
  font-size: 12px;
  color: var(--c-text-muted);
}
.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.file-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.file-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--c-border);
  transition: all 0.25s ease;
}
.file-card:hover {
  border-color: var(--c-border-glow);
  background: rgba(0,212,255,0.03);
}
.file-icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
}
.file-info {
  flex: 1;
  min-width: 0;
}
.file-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  word-break: break-all;
  line-height: 1.4;
}
.file-meta {
  font-size: 11px;
  color: var(--c-text-muted);
  margin-top: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.file-meta-sep { opacity: 0.4; }
.file-download-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  background: rgba(0,212,255,0.08);
  border: 1px solid rgba(0,212,255,0.2);
  color: var(--c-cyan);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  flex-shrink: 0;
  transition: all 0.2s ease;
  cursor: pointer;
}
.file-download-btn:hover {
  background: rgba(0,212,255,0.15);
  border-color: rgba(0,212,255,0.4);
  box-shadow: 0 0 12px rgba(0,212,255,0.15);
}

/* Acceptance card */
.acceptance-card {
  border-color: rgba(0,255,136,0.15) !important;
}
</style>
