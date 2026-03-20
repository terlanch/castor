import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

// Inject auth headers
api.interceptors.request.use((config) => {
  const role = localStorage.getItem('castor_role') || 'user'
  if (role === 'admin') {
    const adminToken = localStorage.getItem('castor_admin_token') || ''
    config.headers['X-Admin-Token'] = adminToken
  } else {
    const userToken = localStorage.getItem('castor_user_token') || ''
    if (userToken) config.headers['Authorization'] = `Bearer ${userToken}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('castor_user_token')
      localStorage.removeItem('castor_admin_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default api
