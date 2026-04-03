<template>
  <div class="oauth-callback">
    <p>{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const message = ref('Signing you in…')

onMounted(() => {
  const raw = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : ''
  const params = new URLSearchParams(raw)
  const err = params.get('error')
  const token = params.get('access_token')
  if (err) {
    message.value = 'Google sign-in failed.'
    ElMessage.error(err === 'access_denied' ? 'Sign-in was cancelled.' : 'Google sign-in failed.')
    router.replace('/login')
    return
  }
  if (!token) {
    message.value = 'Missing token.'
    ElMessage.error('Invalid OAuth response.')
    router.replace('/login')
    return
  }
  auth.loginAsUser(token)
  ElMessage.success('Signed in with Google')
  router.replace('/portal')
})
</script>

<style scoped>
.oauth-callback {
  min-height: 40vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}
</style>
