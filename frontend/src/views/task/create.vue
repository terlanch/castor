<template>
  <div class="page-container">
    <h2 class="page-title">Create Task</h2>

    <!-- Smart submit card -->
    <div class="section-card" style="margin-bottom:20px">
      <div class="section-header">
        <div class="section-title">
          <span class="icon-badge cyan">✨</span>
          Smart Submit
          <span class="badge-beta">AI</span>
        </div>
        <span class="section-subtitle">Describe your task in natural language, we'll structure it for you</span>
      </div>
      <div class="section-body">
        <el-form @submit.prevent="handleNLSubmit" label-position="top">
          <el-form-item>
            <el-input v-model="nlForm.description" type="textarea" :rows="4"
              placeholder="e.g. Find diesel engine buyers in Kazakhstan, include contact info and purchase volume" />
          </el-form-item>
          <div class="form-row">
            <el-form-item label="Max Budget (Credits)" class="budget-field">
              <el-input-number v-model="nlForm.max_budget" :min="1" :max="1000000" />
            </el-form-item>
            <el-button type="primary" native-type="submit" :loading="nlLoading" class="submit-btn">
              <el-icon v-if="!nlLoading" style="margin-right:6px"><MagicStick /></el-icon>
              {{ nlLoading ? 'Processing...' : 'Smart Submit' }}
            </el-button>
          </div>
        </el-form>

        <!-- Result -->
        <transition name="slide-up">
          <div v-if="nlResult" class="result-card">
            <div class="result-header">
              <span class="result-icon">🎉</span>
              <span>Task created: <code>{{ nlResult.task?.task_id?.slice(0, 12) }}...</code></span>
            </div>
            <div class="result-details">
              <div class="result-row">
                <span class="result-label">Category</span>
                <span class="tech-tag purple">{{ nlResult.structured_from?.category }}</span>
              </div>
              <div class="result-row">
                <span class="result-label">Region</span>
                <span class="tech-tag">{{ nlResult.structured_from?.region }}</span>
              </div>
              <div class="result-row">
                <span class="result-label">Tags</span>
                <div>
                  <span v-for="t in nlResult.structured_from?.tags||[]" :key="t" class="tech-tag green">{{ t }}</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <!-- Manual submit card -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="icon-badge purple">⚙️</span>
          Advanced Mode
        </div>
        <span class="section-subtitle">Manually fill in structured fields</span>
      </div>
      <div class="section-body">
        <el-form @submit.prevent="handleManualSubmit" label-position="top">
          <div class="form-grid-2">
            <el-form-item label="Category">
              <el-input v-model="manualForm.category" placeholder="e.g. buyer_discovery" />
            </el-form-item>
            <el-form-item label="Title">
              <el-input v-model="manualForm.title" placeholder="Task title" />
            </el-form-item>
          </div>
          <el-form-item label="Goal">
            <el-input v-model="manualForm.goal" type="textarea" :rows="3" placeholder="Describe the task goal and expected output in detail" />
          </el-form-item>
          <div class="form-grid-2">
            <el-form-item label="Budget (Credits)">
              <el-input-number v-model="manualForm.reward" :min="1" style="width:100%" />
            </el-form-item>
            <el-form-item label="SLA (seconds)">
              <el-input-number v-model="manualForm.sla_seconds" :min="60" style="width:100%" />
            </el-form-item>
          </div>
          <el-button type="primary" native-type="submit" :loading="manualLoading">
            Submit Task
          </el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { createNLTask, createUserTask } from '../../api/user'

const router = useRouter()

const nlForm = reactive({ description: '', max_budget: 100 })
const nlLoading = ref(false)
const nlResult = ref<any>(null)

const manualForm = reactive({ category: 'general', title: '', goal: '', reward: 100, sla_seconds: 3600 })
const manualLoading = ref(false)

async function handleNLSubmit() {
  if (!nlForm.description.trim()) return ElMessage.warning('Please enter a task description')
  nlLoading.value = true
  try {
    const { data } = await createNLTask(nlForm)
    nlResult.value = data
    ElMessage.success('🎉 Task created, redirecting to portal…')
    setTimeout(() => router.push('/portal'), 1500)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Submission failed')
  } finally {
    nlLoading.value = false
  }
}

async function handleManualSubmit() {
  if (!manualForm.title.trim()) return ElMessage.warning('Please enter a title')
  manualLoading.value = true
  try {
    await createUserTask(manualForm)
    ElMessage.success('🎉 Task created, redirecting to portal…')
    setTimeout(() => router.push('/portal'), 1500)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Submission failed')
  } finally {
    manualLoading.value = false
  }
}
</script>

<style scoped>
.section-subtitle {
  font-size: 12px;
  color: var(--c-text-muted);
}

.icon-badge {
  width: 28px; height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
}
.icon-badge.cyan {
  background: var(--c-cyan-dim);
}
.icon-badge.purple {
  background: var(--c-purple-dim);
}

.badge-beta {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: linear-gradient(135deg, var(--c-cyan), var(--c-purple));
  color: #000;
  letter-spacing: 0.05em;
}

.form-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}
.budget-field {
  flex: 0 0 auto;
}
.submit-btn {
  height: 40px !important;
  padding: 0 28px !important;
}

.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* Result card */
.result-card {
  margin-top: 20px;
  padding: 18px 20px;
  border-radius: 12px;
  background: rgba(0, 255, 136, 0.04);
  border: 1px solid rgba(0, 255, 136, 0.15);
}
.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-green);
  margin-bottom: 14px;
}
.result-header code {
  font-size: 12px;
  background: rgba(0, 255, 136, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--c-text);
}
.result-icon {
  font-size: 20px;
}
.result-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.result-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-label {
  font-size: 12px;
  color: var(--c-text-muted);
  min-width: 40px;
}

/* Transition */
.slide-up-enter-active {
  transition: all 0.4s var(--ease-out);
}
.slide-up-leave-active {
  transition: all 0.2s;
}
.slide-up-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.slide-up-leave-to {
  opacity: 0;
}
</style>
