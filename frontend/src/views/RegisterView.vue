<template>
  <div class="container">
    <div class="register-wrapper">
      <div class="card register-card">
        <h1>注册账号</h1>

        <form @submit.prevent="handleRegister">
          <div class="input-group">
            <label>邮箱</label>
            <input
              v-model="form.email"
              type="email"
              class="input"
              placeholder="请输入邮箱（选填）"
            />
          </div>

          <div class="input-group">
            <label>手机号</label>
            <input
              v-model="form.phone"
              type="tel"
              class="input"
              placeholder="请输入手机号（选填）"
            />
          </div>

          <div class="input-group">
            <label>密码</label>
            <input
              v-model="form.password"
              type="password"
              class="input"
              placeholder="请输入密码（至少6位）"
              required
            />
          </div>

          <div class="input-group">
            <label>确认密码</label>
            <input
              v-model="form.confirmPassword"
              type="password"
              class="input"
              placeholder="请再次输入密码"
              required
            />
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <div class="text-center mt-3">
          <router-link to="/login" class="text-accent">已有账号？立即登录</router-link>
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
  email: '',
  phone: '',
  password: '',
  confirmPassword: ''
})

const loading = ref(false)
const error = ref('')

const handleRegister = async () => {
  // 验证
  if (!form.value.email && !form.value.phone) {
    error.value = '请至少填写邮箱或手机号'
    return
  }

  if (form.value.password.length < 6) {
    error.value = '密码至少需要6位'
    return
  }

  if (form.value.password !== form.value.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await authStore.register({
      email: form.value.email || null,
      phone: form.value.phone || null,
      password: form.value.password
    })
    router.push('/character-create')
  } catch (err) {
    error.value = err.response?.data?.detail || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
}

.register-card {
  width: 100%;
  max-width: 500px;
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
