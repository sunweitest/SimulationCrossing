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

          <div class="agree-row">
            <label class="agree-label">
              <input type="checkbox" v-model="agree" />
              <span>
                我已阅读并同意
                <a href="/terms" target="_blank" rel="noopener">《服务条款》</a>和
                <a href="/privacy" target="_blank" rel="noopener">《隐私政策》</a>
              </span>
            </label>
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <button type="submit" class="btn btn-primary btn-block" :disabled="loading || !agree">
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
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()

// 注册后回到触发注册的页面（比如正在玩的对局），否则去创建角色
const goAfterAuth = () => {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  const safe = redirect.startsWith('/') && !redirect.startsWith('//')
  router.push(safe ? redirect : '/character-create')
}
const authStore = useAuthStore()

const form = ref({
  email: '',
  phone: '',
  password: '',
  confirmPassword: ''
})

const loading = ref(false)
const error = ref('')

// 必须勾选同意《服务条款》《隐私政策》才能注册
const agree = ref(false)

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

  if (!agree.value) {
    error.value = '请先阅读并同意《服务条款》和《隐私政策》'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await authStore.register({
      email: form.value.email || null,
      phone: form.value.phone || null,
      password: form.value.password,
      agree_terms: true
    })
    goAfterAuth()
  } catch (err) {
    error.value = err.response?.data?.detail || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 同意条款勾选 */
.agree-row { margin: 2px 0 14px; }
.agree-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.84rem;
  line-height: 1.6;
  color: var(--text-light);
  cursor: pointer;
}
.agree-label input[type="checkbox"] {
  margin-top: 3px;
  width: 15px;
  height: 15px;
  flex: 0 0 auto;
  accent-color: var(--accent-color);
  cursor: pointer;
}
.agree-label a {
  color: var(--secondary-color);
  text-decoration: underline;
}
.agree-label a:hover { color: var(--accent-color); }

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
