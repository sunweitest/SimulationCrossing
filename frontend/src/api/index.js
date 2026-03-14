import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8001/api',
  timeout: 30000
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
  getGameState: (id) => api.get(`/game/session/${id}/state`)
}

export default api

