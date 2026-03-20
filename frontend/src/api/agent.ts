import axios from 'axios'

const publicApi = axios.create({ baseURL: '/api/v1', timeout: 30000 })

export const getPublicAgentProfile = (agentName: string) =>
  publicApi.get(`/agents/public/${encodeURIComponent(agentName)}`)
