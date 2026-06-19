<template>
  <div class="container">
    <div class="page-nav">
      <router-link to="/character-create" class="back-link">← 返回主界面</router-link>
    </div>

    <h1>🔧 管理后台</h1>

    <!-- 管理密钥 -->
    <div class="card mb-3">
      <h3>管理密钥</h3>
      <div class="input-group">
        <input
          v-model="adminKey"
          type="password"
          class="input"
          placeholder="请输入管理密钥"
          @keyup.enter="lookupUser"
        />
      </div>
    </div>

    <!-- 用户查询 -->
    <div class="card mb-3">
      <h3>查找用户</h3>
      <div class="lookup-row">
        <input
          v-model="searchQuery"
          type="text"
          class="input"
          placeholder="输入邮箱或手机号"
          @keyup.enter="lookupUser"
        />
        <button class="btn btn-primary" @click="lookupUser" :disabled="lookingUp">
          {{ lookingUp ? '查找中...' : '查找' }}
        </button>
      </div>
    </div>

    <!-- 错误/成功提示 -->
    <div v-if="message" :class="messageType === 'error' ? 'error-message' : 'success-message'">
      {{ message }}
    </div>

    <!-- 用户信息与操作 -->
    <div v-if="user" class="card">
      <h3>用户信息</h3>
      <div class="user-detail">
        <div class="stat-item">
          <span class="stat-label">ID</span>
          <span class="stat-value">{{ user.id }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">邮箱</span>
          <span class="stat-value">{{ user.email || '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">手机号</span>
          <span class="stat-value">{{ user.phone || '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">注册时间</span>
          <span class="stat-value">{{ formatDate(user.created_at) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">额外配额</span>
          <span class="stat-value">
            <span :class="user.extra_quota > 0 ? 'badge badge-success' : 'badge'">
              {{ user.extra_quota }} 次
            </span>
          </span>
        </div>
        <div class="stat-item">
          <span class="stat-label">30天不限次数</span>
          <span class="stat-value">
            <span v-if="user.is_unlimited" class="badge badge-success">
              已开通（剩 {{ user.unlimited_days_left }} 天）
            </span>
            <span v-else class="text-muted">未开通</span>
          </span>
        </div>
      </div>

      <!-- 操作区域 -->
      <div class="actions mt-4">
        <!-- 追加次数 -->
        <div class="action-card">
          <h4>追加次数</h4>
          <div class="action-row">
            <input
              v-model.number="quotaAmount"
              type="number"
              class="input"
              placeholder="输入次数"
              min="1"
              style="max-width: 200px;"
            />
            <button
              class="btn btn-primary"
              @click="addQuota"
              :disabled="!quotaAmount || addingQuota"
            >
              {{ addingQuota ? '处理中...' : '追加' }}
            </button>
          </div>
        </div>

        <!-- 包月 -->
        <div class="action-card">
          <h4>30天不限次数</h4>
          <div class="action-row">
            <button
              v-if="!user.is_unlimited"
              class="btn btn-delete-danger"
              @click="setUnlimited"
              :disabled="settingUnlimited"
            >
              {{ settingUnlimited ? '处理中...' : '开通30天不限次数' }}
            </button>
            <button
              v-else
              class="btn btn-secondary"
              @click="cancelUnlimited"
              :disabled="cancelingUnlimited"
            >
              {{ cancelingUnlimited ? '处理中...' : '取消30天不限' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { adminAPI } from '@/api'

const adminKey = ref('')
const searchQuery = ref('')
const lookingUp = ref(false)
const user = ref(null)
const message = ref('')
const messageType = ref('error')

const quotaAmount = ref(null)
const addingQuota = ref(false)
const settingUnlimited = ref(false)
const cancelingUnlimited = ref(false)

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const showMessage = (msg, type = 'success') => {
  message.value = msg
  messageType.value = type
  setTimeout(() => { message.value = '' }, 5000)
}

const lookupUser = async () => {
  if (!adminKey.value) {
    showMessage('请输入管理密钥', 'error')
    return
  }
  if (!searchQuery.value.trim()) {
    showMessage('请输入邮箱或手机号', 'error')
    return
  }

  lookingUp.value = true
  user.value = null
  message.value = ''

  try {
    const result = await adminAPI.lookupUser(searchQuery.value.trim(), adminKey.value)
    user.value = result
    showMessage('查找成功', 'success')
  } catch (err) {
    const detail = err.response?.data?.detail
    showMessage(typeof detail === 'string' ? detail : '查找失败', 'error')
  } finally {
    lookingUp.value = false
  }
}

const addQuota = async () => {
  if (!quotaAmount.value || quotaAmount.value < 1) return
  addingQuota.value = true
  try {
    const result = await adminAPI.addQuota(user.value.id, quotaAmount.value, adminKey.value)
    showMessage(result.message || '追加成功', 'success')
    quotaAmount.value = null
    // 刷新用户信息
    await lookupUser()
  } catch (err) {
    showMessage(err.response?.data?.detail || '操作失败', 'error')
  } finally {
    addingQuota.value = false
  }
}

const setUnlimited = async () => {
  settingUnlimited.value = true
  try {
    const result = await adminAPI.setUnlimited(user.value.id, adminKey.value)
    showMessage(result.message || '开通成功', 'success')
    await lookupUser()
  } catch (err) {
    showMessage(err.response?.data?.detail || '操作失败', 'error')
  } finally {
    settingUnlimited.value = false
  }
}

const cancelUnlimited = async () => {
  cancelingUnlimited.value = true
  try {
    const result = await adminAPI.cancelUnlimited(user.value.id, adminKey.value)
    showMessage(result.message || '取消成功', 'success')
    await lookupUser()
  } catch (err) {
    showMessage(err.response?.data?.detail || '操作失败', 'error')
  } finally {
    cancelingUnlimited.value = false
  }
}
</script>

<style scoped>
.page-nav {
  margin-bottom: 1rem;
}

.back-link {
  display: inline-flex;
  align-items: center;
  color: var(--text-light);
  text-decoration: none;
  font-size: 0.95rem;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  transition: all 0.2s;
}

.back-link:hover {
  color: var(--primary-color);
  background: rgba(44, 62, 80, 0.06);
}

.lookup-row {
  display: flex;
  gap: 0.75rem;
}

.lookup-row .input {
  flex: 1;
  max-width: 400px;
}

.user-detail {
  padding: 0.5rem 0;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  font-weight: 600;
  color: var(--text-color);
}

.stat-value {
  color: var(--text-light);
}

.actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.action-card {
  padding: 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: rgba(245, 245, 220, 0.3);
}

.action-card h4 {
  margin-bottom: 0.75rem;
  font-size: 1rem;
}

.action-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.error-message {
  padding: 0.75rem 1rem;
  background: var(--error-color);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.success-message {
  padding: 0.75rem 1rem;
  background: var(--success-color);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.mb-3 {
  margin-bottom: 1.5rem;
}

.mt-4 {
  margin-top: 2rem;
}

.text-muted {
  color: var(--text-light);
}

@media (max-width: 768px) {
  .action-row {
    flex-direction: column;
  }

  .action-row .input {
    max-width: 100% !important;
  }

  .action-row .btn {
    width: 100%;
  }
}
</style>
