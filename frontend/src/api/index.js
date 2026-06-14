import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 160000  // LLM 生成剧情可能较慢
})

// 请求拦截器 - 添加token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证API
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data)
}

// 游戏API
export const gameAPI = {
  createSession: (data) => api.post('/game/session', data),
  performAction: (data) => api.post('/game/action', data),
  getSession: (id) => api.get(`/game/session/${id}`),
  getGameState: (id) => api.get(`/game/session/${id}/state`),
  getSessions: () => api.get('/game/sessions'),
  deleteSession: (id) => api.delete(`/game/session/${id}`),
  getCharacters: (params) => api.get('/game/characters', { params }),
  getCharacterDetail: (novel, name, timeline) => api.get(`/game/character/${encodeURIComponent(novel)}/${encodeURIComponent(name)}`, { params: { timeline } })
}

// 管理后台 API（需要 X-Admin-Key 请求头）
export const adminAPI = {
  lookupUser: (q, adminKey) =>
    api.get('/admin/lookup', { params: { q }, headers: { 'X-Admin-Key': adminKey } }),

  addQuota: (userId, amount, adminKey) =>
    api.post('/admin/add-quota', null, { params: { user_id: userId, amount }, headers: { 'X-Admin-Key': adminKey } }),

  setUnlimited: (userId, adminKey) =>
    api.post('/admin/monthly-unlimited', null, { params: { user_id: userId }, headers: { 'X-Admin-Key': adminKey } }),

  cancelUnlimited: (userId, adminKey) =>
    api.delete('/admin/monthly-unlimited', { params: { user_id: userId }, headers: { 'X-Admin-Key': adminKey } }),
}

export default api

