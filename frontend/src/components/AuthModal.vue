<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-backdrop" @click.self="close">
        <div class="modal-container" @click.stop>
          <!-- 关闭按钮 -->
          <button class="modal-close" @click="close" title="关闭">&times;</button>

          <!-- 标签切换 -->
          <div class="modal-tabs">
            <button
              :class="['tab-btn', { active: activeTab === 'login' }]"
              @click="switchTab('login')"
            >
              登录
            </button>
            <button
              :class="['tab-btn', { active: activeTab === 'register' }]"
              @click="switchTab('register')"
            >
              注册
            </button>
          </div>

          <!-- 登录表单 -->
          <form v-if="activeTab === 'login'" @submit.prevent="handleLogin">
            <div class="input-group">
              <label>邮箱或手机号</label>
              <input
                v-model="loginForm.identifier"
                type="text"
                class="input"
                placeholder="请输入邮箱或手机号"
                required
              />
            </div>

            <div class="input-group">
              <label>密码</label>
              <input
                v-model="loginForm.password"
                type="password"
                class="input"
                placeholder="请输入密码"
                required
              />
            </div>

            <div v-if="error" class="error-message">{{ error }}</div>

            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              {{ loading ? '登录中...' : '登录' }}
            </button>
          </form>

          <!-- 注册表单 -->
          <form v-if="activeTab === 'register'" @submit.prevent="handleRegister">
            <div class="input-group">
              <label>邮箱</label>
              <input
                v-model="registerForm.email"
                type="email"
                class="input"
                placeholder="请输入邮箱（选填）"
              />
            </div>

            <div class="input-group">
              <label>手机号</label>
              <input
                v-model="registerForm.phone"
                type="tel"
                class="input"
                placeholder="请输入手机号（选填）"
              />
            </div>

            <div class="input-group">
              <label>密码</label>
              <input
                v-model="registerForm.password"
                type="password"
                class="input"
                placeholder="请输入密码（至少6位）"
                required
              />
            </div>

            <div class="input-group">
              <label>确认密码</label>
              <input
                v-model="registerForm.confirmPassword"
                type="password"
                class="input"
                placeholder="请再次输入密码"
                required
              />
            </div>

            <div v-if="error" class="error-message">{{ error }}</div>

            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              {{ loading ? '注册中...' : '注册' }}
            </button>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['update:visible'])

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  initialTab: {
    type: String,
    default: 'login',
    validator: (v) => ['login', 'register'].includes(v)
  }
})

const authStore = useAuthStore()

const activeTab = ref('login')
const loading = ref(false)
const error = ref('')

const loginForm = reactive({
  identifier: '',
  password: ''
})

const registerForm = reactive({
  email: '',
  phone: '',
  password: '',
  confirmPassword: ''
})

const close = () => {
  emit('update:visible', false)
}

const switchTab = (tab) => {
  activeTab.value = tab
  error.value = ''
}

// 切换时清除错误
watch(activeTab, () => {
  error.value = ''
})

// 打开时重置状态
watch(() => props.visible, (val) => {
  if (val) {
    activeTab.value = props.initialTab
    error.value = ''
    loginForm.identifier = ''
    loginForm.password = ''
    registerForm.email = ''
    registerForm.phone = ''
    registerForm.password = ''
    registerForm.confirmPassword = ''
  }
})

// 监听 Esc 键关闭
const onKeydown = (e) => {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

// 需要用一个全局的 keydown 监听（因为 Teleport 到 body 后，组件本身可能收不到事件）
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKeydown)
}

const handleLogin = async () => {
  loading.value = true
  error.value = ''

  try {
    await authStore.login({ ...loginForm })
    close()
  } catch (err) {
    error.value = err.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  // 客户端验证
  if (!registerForm.email && !registerForm.phone) {
    error.value = '请至少填写邮箱或手机号'
    return
  }

  if (registerForm.password.length < 6) {
    error.value = '密码至少需要6位'
    return
  }

  if (registerForm.password !== registerForm.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await authStore.register({
      email: registerForm.email || null,
      phone: registerForm.phone || null,
      password: registerForm.password
    })
    close()
  } catch (err) {
    error.value = err.response?.data?.detail || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 遮罩层 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

/* 弹窗容器 */
.modal-container {
  background: var(--card-bg);
  border-radius: 12px;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-lg);
  padding: 2rem;
  width: 100%;
  max-width: 450px;
  position: relative;
  max-height: 90vh;
  overflow-y: auto;
}

/* 关闭按钮 */
.modal-close {
  position: absolute;
  top: 0.75rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-light);
  line-height: 1;
  padding: 0.25rem;
  transition: color 0.2s;
}

.modal-close:hover {
  color: var(--text-color);
}

/* 标签切换 */
.modal-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  flex: 1;
  padding: 0.75rem 1rem;
  border: none;
  background: none;
  font-size: 1.1rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--text-light);
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-color);
}

.tab-btn.active {
  color: var(--primary-color);
  border-bottom-color: var(--accent-color);
  font-weight: 600;
}

/* 错误消息 */
.error-message {
  padding: 0.75rem;
  background: var(--error-color);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
  text-align: center;
}

/* 过渡动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.25s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.25s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container {
  transform: scale(0.95) translateY(-10px);
}

.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(-10px);
}
</style>
