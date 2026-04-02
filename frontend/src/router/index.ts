import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/login/index.vue') },
  {
    path: '/oauth/callback',
    name: 'OAuthCallback',
    component: () => import('../views/oauth/callback.vue'),
  },
  { path: '/agent/:agentName', name: 'AgentPublicProfile', component: () => import('../views/agent/profile.vue'), props: true },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    children: [
      { path: '', redirect: '/portal' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/dashboard/index.vue') },
      { path: 'agents', name: 'Agents', component: () => import('../views/agent/index.vue') },
      { path: 'tasks', name: 'Tasks', component: () => import('../views/task/index.vue') },
      { path: 'tasks/create', name: 'TaskCreate', component: () => import('../views/task/create.vue') },
      { path: 'portal', name: 'UserPortal', component: () => import('../views/user/portal.vue') },
      { path: 'portal/task/:taskId', name: 'TaskDetail', component: () => import('../views/user/task-detail.vue'), props: true },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const hasToken = localStorage.getItem('castor_user_token') || localStorage.getItem('castor_admin_token')
  if (
    !hasToken &&
    to.name !== 'Login' &&
    to.name !== 'AgentPublicProfile' &&
    to.name !== 'OAuthCallback'
  )
    return { name: 'Login' }
})

export default router
