<template>
  <div class="container">
    <div class="login-wrapper">
      <div class="card login-card">
        <h1>登录</h1>

        <form @submit.prevent="handleLogin">
          <div class="input-group">
            <label>邮箱或手机号</label>
            <input
              v-model="form.identifier"
              type="text"
              class="input"
              placeholder="请输入邮箱或手机号"
              required
            />
          </div>

          <div class="input-group">
            <label>密码</label>
            <input
              v-model="form.password"
              type="password"
              class="input"
              placeholder="请输入密码"
              required
            />
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <div class="text-center mt-3">
          <router-link to="/register" class="text-accent">还没有账号？立即注册</router-link>
        </div>

        <div class="text-center mt-2">
          <router-link to="/character-create" class="text-muted">跳过登录，直接体验</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  identifier: '',
  password: ''
})

const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  loading.value = true
  error.value = ''

  try {
    await authStore.login(form.value)
    router.push('/character-create')
  } catch (err) {
    error.value = err.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
}

.login-card {
  width: 100%;
  max-width: 450px;
}

.error-message {
  padding: 0.75rem;
  background: var(--error-color);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
  text-align: center;
}
</style>
