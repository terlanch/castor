import api from './request'

export const registerUser = (data: { username: string; password: string; display_name?: string }) =>
  api.post('/users/register', data)

export const loginUser = (data: { username: string; password: string }) =>
  api.post('/users/login', data)

export const getUserProfile = () => api.get('/users/me')

export const topupUser = (amount: number) =>
  api.post('/users/topup', { amount, note: 'Portal top-up' })

export const getUserTasks = () => api.get('/users/tasks')

export const createUserTask = (data: any) => api.post('/users/tasks', data)

export const createNLTask = (data: { description: string; max_budget: number }) =>
  api.post('/users/tasks/natural', data)

export const acceptTaskResult = (taskId: string) =>
  api.post(`/users/tasks/${taskId}/accept-result`, { note: 'Accepted in portal.' })

export const rejectTaskResult = (taskId: string) =>
  api.post(`/users/tasks/${taskId}/reject-result`, { note: 'Rejected in portal.' })

// ── Proposal APIs ──────────────────────────────────────────────────
export const getTaskProposals = (taskId: string) =>
  api.get(`/users/tasks/${taskId}/proposals`)

export const acceptProposal = (taskId: string, proposalId: string) =>
  api.post(`/users/tasks/${taskId}/proposals/${proposalId}/accept`)

export const rejectProposal = (taskId: string, proposalId: string) =>
  api.post(`/users/tasks/${taskId}/proposals/${proposalId}/reject`)

export const getTaskProgress = (taskId: string) =>
  api.get(`/users/tasks/${taskId}/progress`)
