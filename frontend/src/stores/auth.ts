import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type AuthRole = 'user' | 'admin'

export const useAuthStore = defineStore('auth', () => {
  const userToken = ref(localStorage.getItem('castor_user_token') || '')
  const adminToken = ref(localStorage.getItem('castor_admin_token') || '')
  const role = ref<AuthRole>((localStorage.getItem('castor_role') as AuthRole) || 'user')

  const isLoggedIn = computed(() => !!userToken.value || !!adminToken.value)
  const isAdmin = computed(() => role.value === 'admin' && !!adminToken.value)

  function loginAsUser(token: string) {
    userToken.value = token
    role.value = 'user'
    localStorage.setItem('castor_user_token', token)
    localStorage.setItem('castor_role', 'user')
  }

  function loginAsAdmin(token: string) {
    adminToken.value = token
    role.value = 'admin'
    localStorage.setItem('castor_admin_token', token)
    localStorage.setItem('castor_role', 'admin')
  }

  function logout() {
    userToken.value = ''
    adminToken.value = ''
    role.value = 'user'
    localStorage.removeItem('castor_user_token')
    localStorage.removeItem('castor_admin_token')
    localStorage.removeItem('castor_role')
  }

  return { userToken, adminToken, role, isLoggedIn, isAdmin, loginAsUser, loginAsAdmin, logout }
})
