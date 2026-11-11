import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  const login = async (credentials) => {
    const response = await authAPI.login(credentials)
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    return response
  }

  const register = async (userData) => {
    const response = await authAPI.register(userData)
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    return response
  }

  const setUser = (u) => {
    user.value = u
    localStorage.setItem('user', JSON.stringify(u))
  }

  // 修改天梯昵称：后端校验通过后回写本地
  const updateNickname = async (nickname) => {
    const updated = await authAPI.updateNickname(nickname)
    setUser(updated)
    return updated
  }

  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    user,
    isAuthenticated,
    setUser,
    updateNickname,
    login,
    register,
    logout
  }
})
