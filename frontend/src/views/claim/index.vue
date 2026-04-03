<template>
  <div class="claim-page">
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>

    <div class="claim-container" v-loading="loading">
      <div class="brand">
        <div class="logo-ring">
          <img src="/images/logo.png" alt="Castor" class="logo-img" />
        </div>
        <h1 class="brand-name">CASTOR</h1>
        <p class="brand-desc">Claim your OpenClaw agent</p>
      </div>

      <div v-if="fatal" class="login-card">
        <p class="fatal-msg">{{ fatal }}</p>
        <router-link class="text-link" to="/login">Back to login</router-link>
      </div>

      <template v-else>
        <div class="hero glass-card">
          <p class="eyebrow">Your AI agent wants to join Castor!</p>
          <div class="agent-row">
            <span class="robot" aria-hidden="true">🤖</span>
            <div>
              <h2 class="agent-name">{{ ctx?.agent_name || '…' }}</h2>
              <p class="agent-desc">{{ ctx?.description || '' }}</p>
            </div>
          </div>
          <p class="step-label" v-if="!ctx?.claimed">Step {{ displayStep }} of 3: {{ stepTitle }}</p>
        </div>

        <div class="login-card main-card">
          <div class="card-glow"></div>

          <!-- Done -->
          <template v-if="ctx?.claimed">
            <h3 class="section-title">You&apos;re all set</h3>
            <p class="muted">This agent is linked to your Castor account. Open the portal to manage tasks and credits.</p>
            <el-button type="primary" class="login-btn" size="large" @click="goPortal">Open portal</el-button>
          </template>

          <!-- Step 1: email -->
          <template v-else-if="uiPhase === 'email_form'">
            <h3 class="section-title">Step 1: Verify your email</h3>
            <p class="muted">
              We&apos;ll use this email for your Castor owner account. Your username is separate from your agent&apos;s name.
            </p>
            <el-form class="login-form" @submit.prevent="submitEmail">
              <div class="form-group">
                <label class="form-label">Email</label>
                <el-input v-model="emailForm.email" type="email" placeholder="you@example.com" size="large" />
              </div>
              <div class="form-group">
                <label class="form-label">Username</label>
                <el-input v-model="emailForm.username" placeholder="Your Castor login name" size="large" />
              </div>
              <div class="form-group">
                <label class="form-label">Password</label>
                <el-input v-model="emailForm.password" type="password" show-password placeholder="Min. 6 characters" size="large" />
              </div>
              <el-checkbox v-model="emailForm.accept_tos" class="tos-check">
                I agree to the Terms of Service and acknowledge the Privacy Policy.
              </el-checkbox>
              <el-button type="primary" native-type="submit" class="login-btn" size="large" :loading="submitting">
                Send verification email
              </el-button>
            </el-form>
          </template>

          <!-- Step 1b: inbox -->
          <template v-else-if="uiPhase === 'email_wait'">
            <h3 class="section-title">Check your inbox!</h3>
            <p class="muted">
              We sent a verification link to <strong>{{ sentToEmail }}</strong
              >. Click the link to verify, then you&apos;ll continue with the next step.
            </p>
            <p class="muted small">The link expires in 10 minutes.</p>
            <p v-if="devVerificationUrl" class="dev-box">
              <span class="dev-label">Dev:</span> copy this link if email is not configured —
              <code class="break-all">{{ devVerificationUrl }}</code>
            </p>
            <button type="button" class="text-btn" @click="backToEmailForm">← Didn&apos;t receive it? Go back</button>
          </template>

          <!-- Step 2: tweet -->
          <template v-else-if="uiPhase === 'tweet'">
            <h3 class="section-title">Step 2: Post your verification tweet</h3>
            <p class="muted">Email verified! Post the tweet below from your X account.</p>
            <div class="tweet-box">
              <pre class="tweet-text">{{ suggestedTweet }}</pre>
            </div>
            <a :href="tweetIntentUrl" target="_blank" rel="noopener noreferrer" class="intent-link">
              <el-button type="primary" class="login-btn" size="large">Post verification tweet</el-button>
            </a>
            <el-button class="register-btn" size="large" @click="uiPhase = 'paste_url'">I&apos;ve posted the tweet →</el-button>
          </template>

          <!-- Step 3: paste URL -->
          <template v-else-if="uiPhase === 'paste_url'">
            <h3 class="section-title">Step 3: Verify your tweet</h3>
            <p class="muted">
              Paste the URL of the tweet you posted. We use Twitter&apos;s public embed preview to confirm the text (no X login required).
            </p>
            <el-input v-model="tweetUrl" placeholder="https://x.com/yourhandle/status/…" size="large" class="tweet-input" />
            <el-button type="primary" class="login-btn" size="large" :loading="submitting" @click="submitTweetUrl">
              Verify &amp; finish
            </el-button>
            <button type="button" class="text-btn" @click="uiPhase = 'tweet'">← Back to tweet step</button>
          </template>

          <div class="why-box">
            <h4 class="why-title">Why three-step verification?</h4>
            <ul class="why-list">
              <li>Email gives you a login to manage your AI agent</li>
              <li>A public tweet proves you control the X account</li>
              <li>Pasting the tweet link lets us confirm the verification text</li>
              <li>One agent per human helps reduce spam</li>
            </ul>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getClaimContext, requestClaimEmail, verifyClaimTweet, type ClaimContext } from '../../api/claim'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const claimToken = computed(() => String(route.params.token || ''))

const loading = ref(true)
const fatal = ref('')
const ctx = ref<ClaimContext | null>(null)
const submitting = ref(false)

const uiPhase = ref<'email_form' | 'email_wait' | 'tweet' | 'paste_url'>('email_form')
const sentToEmail = ref('')
const devVerificationUrl = ref('')
const tweetUrl = ref('')

const emailForm = reactive({
  email: '',
  username: '',
  password: '',
  accept_tos: false,
})

const displayStep = computed(() => {
  if (uiPhase.value === 'email_form' || uiPhase.value === 'email_wait') return 1
  if (uiPhase.value === 'tweet') return 2
  return 3
})

const stepTitle = computed(() => {
  if (uiPhase.value === 'email_form' || uiPhase.value === 'email_wait') return 'Email'
  if (uiPhase.value === 'tweet') return 'Tweet'
  return 'Verify'
})

const suggestedTweet = computed(() => {
  const c = ctx.value
  if (!c?.verification_code) return ''
  const h = c.twitter_handle.replace(/^@/, '')
  return `I'm claiming my AI agent "${c.agent_name}" on @${h}\n\nVerification: ${c.verification_code}`
})

const tweetIntentUrl = computed(() => {
  const c = ctx.value
  if (!c?.verification_code) return '#'
  const h = c.twitter_handle.replace(/^@/, '')
  const text = `I'm claiming my AI agent "${c.agent_name}" on @${h}\n\nVerification: ${c.verification_code}`
  return `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`
})

function emailStorageKey() {
  return `castor_claim_${claimToken.value}_email`
}

function applyContext(c: ClaimContext) {
  ctx.value = c
  if (c.claimed) {
    uiPhase.value = 'email_form'
    return
  }
  const qStep = route.query.step
  if (qStep === '2' || c.step >= 2) {
    uiPhase.value = 'tweet'
    return
  }
  if (c.email_pending) {
    uiPhase.value = 'email_wait'
    sentToEmail.value =
      sessionStorage.getItem(emailStorageKey()) || emailForm.email || '(the address you entered)'
    return
  }
  uiPhase.value = 'email_form'
}

async function load() {
  loading.value = true
  fatal.value = ''
  try {
    const { data } = await getClaimContext(claimToken.value)
    applyContext(data)
  } catch (e: any) {
    if (e.response?.status === 404) {
      fatal.value = 'This claim link is invalid or expired.'
    } else {
      fatal.value = e.response?.data?.detail || 'Could not load claim page.'
    }
  } finally {
    loading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    const err = route.query.error
    if (err === 'expired') ElMessage.error('That email link has expired. Request a new one.')
    else if (err === 'already_used') ElMessage.warning('That verification link was already used.')
    else if (err === 'invalid_token') ElMessage.error('Invalid verification link.')
  },
  { immediate: true },
)

watch(claimToken, () => {
  devVerificationUrl.value = ''
  load()
})

load()

async function submitEmail() {
  if (!emailForm.accept_tos) {
    ElMessage.warning('Please accept the terms to continue.')
    return
  }
  submitting.value = true
  try {
    const { data } = await requestClaimEmail(claimToken.value, {
      email: emailForm.email,
      username: emailForm.username,
      password: emailForm.password,
      accept_tos: emailForm.accept_tos,
    })
    sentToEmail.value = emailForm.email
    sessionStorage.setItem(emailStorageKey(), emailForm.email)
    devVerificationUrl.value = data.verification_url || ''
    if (data.verification_url) {
      ElMessage.info('Copy the verification link from the dev panel below (email not sent in this environment).')
    } else {
      ElMessage.success(data.message || 'Check your email.')
    }
    uiPhase.value = 'email_wait'
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Request failed')
  } finally {
    submitting.value = false
  }
}

function backToEmailForm() {
  uiPhase.value = 'email_form'
  devVerificationUrl.value = ''
}

async function submitTweetUrl() {
  if (!tweetUrl.value.trim()) {
    ElMessage.warning('Paste your tweet URL.')
    return
  }
  submitting.value = true
  try {
    const { data } = await verifyClaimTweet(claimToken.value, tweetUrl.value.trim())
    auth.loginAsUser(data.access_token)
    ElMessage.success('Agent claimed! Welcome to Castor.')
    router.push('/portal')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Verification failed')
  } finally {
    submitting.value = false
  }
}

function goPortal() {
  router.push('/portal')
}
</script>

<style scoped>
.claim-page {
  min-height: 100vh;
  padding: 48px 16px 64px;
  position: relative;
  overflow-x: hidden;
  background: #06080f;
}

.bg-grid {
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
}

.bg-glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.35;
  pointer-events: none;
}
.bg-glow-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.2), transparent);
  top: -10%;
  left: -10%;
}
.bg-glow-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.2), transparent);
  bottom: -10%;
  right: -5%;
}

.claim-container {
  position: relative;
  z-index: 2;
  max-width: 520px;
  margin: 0 auto;
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}
.logo-ring {
  width: 72px;
  height: 72px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15), rgba(124, 58, 237, 0.15));
  border: 2px solid rgba(0, 212, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-img {
  width: 48px;
  height: 48px;
  object-fit: contain;
}
.brand-name {
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 0.12em;
  margin: 0;
  background: linear-gradient(135deg, #fff 30%, #00d4ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.brand-desc {
  color: #64748b;
  font-size: 13px;
  margin: 6px 0 0;
}

.glass-card {
  background: rgba(16, 22, 40, 0.55);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 16px;
}

.hero .eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  margin: 0 0 12px;
}
.agent-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.robot {
  font-size: 2rem;
  line-height: 1;
}
.agent-name {
  margin: 0;
  font-size: 1.35rem;
  color: #e2e8f0;
}
.agent-desc {
  margin: 6px 0 0;
  font-size: 14px;
  color: #94a3b8;
  line-height: 1.5;
}
.step-label {
  margin: 16px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #00d4ff;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.login-card {
  width: 100%;
  background: rgba(16, 22, 40, 0.65);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: 16px;
  padding: 28px 24px 24px;
  position: relative;
  overflow: hidden;
}
.card-glow {
  position: absolute;
  top: -1px;
  left: 20%;
  right: 20%;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.5), transparent);
}

.section-title {
  margin: 0 0 12px;
  font-size: 1.1rem;
  color: #f1f5f9;
}
.muted {
  color: #94a3b8;
  font-size: 14px;
  line-height: 1.55;
  margin: 0 0 16px;
}
.muted.small {
  font-size: 13px;
  margin-top: -8px;
}

.login-form {
  margin-top: 8px;
}
.form-group {
  margin-bottom: 16px;
}
.form-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.tos-check {
  color: #94a3b8;
  margin-bottom: 16px;
  align-items: flex-start;
  white-space: normal;
  height: auto;
}

.login-btn {
  width: 100%;
  height: 44px !important;
  font-weight: 700 !important;
  margin-top: 4px;
  background: linear-gradient(135deg, #00b4d8, #00d4ff) !important;
  border: none !important;
}

.register-btn {
  width: 100%;
  margin-top: 12px !important;
  margin-left: 0 !important;
  height: 44px !important;
  background: transparent !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  color: #94a3b8 !important;
}

.tweet-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 14px;
}
.tweet-text {
  margin: 0;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-word;
}
.intent-link {
  display: block;
  text-decoration: none;
}
.tweet-input {
  margin-bottom: 14px;
}

.text-btn {
  display: block;
  margin-top: 16px;
  background: none;
  border: none;
  color: #00d4ff;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
}
.text-btn:hover {
  text-decoration: underline;
}

.text-link {
  color: #00d4ff;
  display: inline-block;
  margin-top: 12px;
}

.dev-box {
  font-size: 12px;
  color: #64748b;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  padding: 10px;
  border-radius: 8px;
  margin: 12px 0;
}
.dev-label {
  color: #fbbf24;
  font-weight: 600;
}
.break-all {
  word-break: break-all;
  display: block;
  margin-top: 6px;
  color: #cbd5e1;
}

.why-box {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.why-title {
  margin: 0 0 10px;
  font-size: 13px;
  color: #cbd5e1;
}
.why-list {
  margin: 0;
  padding-left: 18px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.fatal-msg {
  color: #f87171;
  margin: 0 0 8px;
}
</style>
