import api from './request'

export const getDashboard = () => api.get('/admin/dashboard')
export const getAgents = () => api.get('/admin/agents')
export const getAgentDetail = (id: string) => api.get(`/admin/agents/${id}`)
export const getTasks = () => api.get('/admin/tasks')
export const getTaskDetail = (id: string) => api.get(`/admin/tasks/${id}`)
export const getTaskCandidates = (id: string) => api.get(`/admin/tasks/${id}/candidates`)
export const verifyTask = (id: string, note?: string) =>
  api.post(`/admin/tasks/${id}/verify`, { note: note || 'Approved by admin.' })
export const rejectSubmission = (id: string, note?: string) =>
  api.post(`/admin/tasks/${id}/reject-submission`, { note: note || 'Rejected by admin.' })
export const getLedger = () => api.get('/admin/ledger')
export const getTags = () => api.get('/tags')
