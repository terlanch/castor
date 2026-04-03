<template>
  <div class="login-page">
    <!-- Animated background -->
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>
    <div class="bg-glow bg-glow-3"></div>

    <!-- Floating particles -->
    <div class="particles">
      <span v-for="i in 20" :key="i" class="particle" :style="particleStyle(i)"></span>
    </div>

    <div class="login-container">
      <!-- Logo & branding -->
      <div class="brand">
        <div class="logo-ring">
          <img src="/images/logo.png" alt="Castor" class="logo-img" />
        </div>
        <h1 class="brand-name">CASTOR</h1>
        <p class="brand-desc">AI Labor Orchestration & Settlement Platform</p>
      </div>

      <!-- Login card -->
      <div class="login-card">
        <div class="card-glow"></div>
        <el-tabs v-model="tab" class="login-tabs">
          <el-tab-pane label="User Login" name="user">
            <el-form @submit.prevent="handleUserLogin" class="login-form">
              <div class="form-group">
                <label class="form-label">Username</label>
                <el-input v-model="userForm.username" placeholder="Enter your username" size="large">
                  <template #prefix><el-icon><User /></el-icon></template>
                </el-input>
              </div>
              <div class="form-group">
                <label class="form-label">Password</label>
                <el-input v-model="userForm.password" placeholder="Enter password" type="password" show-password size="large">
                  <template #prefix><el-icon><Lock /></el-icon></template>
                </el-input>
              </div>
              <el-button type="primary" native-type="submit" :loading="loading" size="large" class="login-btn">
                <span v-if="!loading">Sign In</span>
              </el-button>
              <p v-if="googleRedirectUri" class="oauth-uri-hint">
                Google Cloud 控制台「已获授权的重定向 URI」须<strong>完全一致</strong>添加：<br />
                <code class="oauth-uri-code">{{ googleRedirectUri }}</code>
              </p>
              <el-button
                v-if="googleEnabled"
                size="large"
                class="google-btn"
                :disabled="loading"
                @click="startGoogleLogin"
              >
                Continue with Google
              </el-button>
              <el-button size="large" class="register-btn" @click="handleUserRegister" :loading="loading">
                Create Account
              </el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="Admin" name="admin">
            <el-form @submit.prevent="handleAdminLogin" class="login-form">
              <div class="form-group">
                <label class="form-label">Admin Token</label>
                <el-input v-model="adminToken" placeholder="Enter admin token" size="large">
                  <template #prefix><el-icon><Key /></el-icon></template>
                </el-input>
              </div>
              <el-button type="primary" native-type="submit" size="large" class="login-btn admin-btn">
                Enter Admin Panel
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>

      <p class="footer-text">Powered by OpenClaw · Distributed AI Task Network</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Key } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'
import { loginUser, registerUser, getGoogleAuthStatus } from '../../api/user'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('user')
const loading = ref(false)
const googleEnabled = ref(false)
const googleRedirectUri = ref('')
const userForm = reactive({ username: '', password: '' })
const adminToken = ref('')

onMounted(async () => {
  try {
    const { data } = await getGoogleAuthStatus()
    googleEnabled.value = !!data?.enabled
    googleRedirectUri.value = data?.redirect_uri || ''
  } catch {
    googleEnabled.value = false
    googleRedirectUri.value = ''
  }
})

function startGoogleLogin() {
  window.location.href = '/api/v1/users/auth/google'
}

function particleStyle(i: number) {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 1 + Math.random() * 3
  const dur = 15 + Math.random() * 25
  const delay = Math.random() * -20
  return {
    left: `${x}%`,
    top: `${y}%`,
    width: `${size}px`,
    height: `${size}px`,
    animationDuration: `${dur}s`,
    animationDelay: `${delay}s`,
  }
}

async function handleUserLogin() {
  loading.value = true
  try {
    const { data } = await loginUser(userForm)
    auth.loginAsUser(data.access_token)
    ElMessage.success('Login successful')
    router.push('/portal')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Login failed')
  } finally {
    loading.value = false
  }
}

async function handleUserRegister() {
  loading.value = true
  try {
    const { data } = await registerUser({ ...userForm })
    auth.loginAsUser(data.access_token)
    ElMessage.success('Registration successful')
    router.push('/portal')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Registration failed')
  } finally {
    loading.value = false
  }
}

function handleAdminLogin() {
  if (!adminToken.value) return ElMessage.warning('Please enter Admin Token')
  auth.loginAsAdmin(adminToken.value)
  router.push('/dashboard')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: #06080f;
}

/* Background grid */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
}

/* Floating glows */
.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.4;
  animation: glowFloat 20s ease-in-out infinite;
}
.bg-glow-1 {
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.2), transparent);
  top: -15%; left: -10%;
  animation-delay: 0s;
}
.bg-glow-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.2), transparent);
  bottom: -10%; right: -5%;
  animation-delay: -7s;
}
.bg-glow-3 {
  width: 300px; height: 300px;
  background: radial-gradient(circle, rgba(0, 255, 136, 0.1), transparent);
  top: 50%; left: 60%;
  animation-delay: -14s;
}
@keyframes glowFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%      { transform: translate(30px, -20px) scale(1.1); }
  66%      { transform: translate(-20px, 30px) scale(0.9); }
}

/* Particles */
.particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.particle {
  position: absolute;
  background: rgba(0, 212, 255, 0.4);
  border-radius: 50%;
  animation: particleFloat linear infinite;
}
@keyframes particleFloat {
  0%   { transform: translateY(0) translateX(0); opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { transform: translateY(-100vh) translateX(50px); opacity: 0; }
}

/* Container */
.login-container {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 420px;
  padding: 0 20px;
}

/* Brand */
.brand {
  text-align: center;
  margin-bottom: 36px;
}
.logo-ring {
  width: 80px; height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.15), rgba(124, 58, 237, 0.15));
  border: 2px solid rgba(0, 212, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 30px rgba(0, 212, 255, 0.15);
  animation: logoBreath 4s ease-in-out infinite;
}
@keyframes logoBreath {
  0%, 100% { box-shadow: 0 0 30px rgba(0, 212, 255, 0.15); }
  50%      { box-shadow: 0 0 50px rgba(0, 212, 255, 0.25); }
}
.logo-img {
  width: 56px;
  height: 56px;
  object-fit: contain;
  filter: drop-shadow(0 0 10px rgba(0, 212, 255, 0.3));
}
.brand-name {
  font-size: 32px;
  font-weight: 900;
  letter-spacing: 0.12em;
  margin: 0;
  background: linear-gradient(135deg, #fff 30%, #00d4ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
}
.brand-desc {
  color: #64748b;
  font-size: 14px;
  margin: 8px 0 0;
  letter-spacing: 0.04em;
}

/* Login card */
.login-card {
  width: 100%;
  background: rgba(16, 22, 40, 0.65);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: 16px;
  padding: 32px 28px 28px;
  box-shadow:
    0 8px 40px rgba(0, 0, 0, 0.5),
    0 0 1px rgba(0, 212, 255, 0.15);
  position: relative;
  overflow: hidden;
}
.card-glow {
  position: absolute;
  top: -1px; left: 20%; right: 20%;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.5), transparent);
  border-radius: 2px;
}

/* Form */
.login-form {
  margin-top: 8px;
}
.form-group {
  margin-bottom: 20px;
}
.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.login-btn {
  width: 100%;
  height: 44px !important;
  font-size: 15px !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em !important;
  margin-top: 8px;
  background: linear-gradient(135deg, #00b4d8, #00d4ff) !important;
  border: none !important;
}
.login-btn:hover {
  background: linear-gradient(135deg, #00c4e8, #33ddff) !important;
}
.admin-btn {
  background: linear-gradient(135deg, #7c3aed, #a78bfa) !important;
}
.admin-btn:hover {
  background: linear-gradient(135deg, #8b5cf6, #c4b5fd) !important;
}
.register-btn {
  width: 100%;
  margin-top: 10px !important;
  margin-left: 0 !important;
  height: 44px !important;
  font-weight: 600 !important;
  background: transparent !important;
  border: 1px solid rgba(0, 212, 255, 0.2) !important;
  color: #94a3b8 !important;
}
.register-btn:hover {
  border-color: rgba(0, 212, 255, 0.4) !important;
  color: #00d4ff !important;
  background: rgba(0, 212, 255, 0.05) !important;
}
.google-btn {
  width: 100%;
  margin-top: 10px !important;
  margin-left: 0 !important;
  height: 44px !important;
  font-weight: 600 !important;
  background: #fff !important;
  color: #1f2937 !important;
  border: 1px solid #e5e7eb !important;
}
.google-btn:hover {
  background: #f9fafb !important;
  border-color: #d1d5db !important;
}

/* Footer */
.footer-text {
  margin-top: 28px;
  font-size: 11px;
  color: #334155;
  letter-spacing: 0.04em;
}
.oauth-uri-hint {
  font-size: 11px;
  line-height: 1.5;
  color: #64748b;
  margin: 0 0 10px;
  word-break: break-all;
}
.oauth-uri-code {
  display: inline-block;
  margin-top: 6px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  color: #94f9ff;
  font-size: 10px;
}
</style>
