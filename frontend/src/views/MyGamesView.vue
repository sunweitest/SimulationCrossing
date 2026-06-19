<template>
  <div class="container">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <router-link to="/character-create" class="back-link">← 返回主界面</router-link>
    </div>

    <h1>📋 我的游戏</h1>

    <!-- 加载中 -->
    <div v-if="gameStore.isSessionsLoading" class="loading">
      <div class="spinner"></div>
      <p class="mt-2">加载中...</p>
    </div>

    <!-- 空列表 -->
    <div v-else-if="gameStore.mySessions.length === 0" class="card text-center" style="padding: 3rem 2rem;">
      <p style="font-size: 1.2rem; margin-bottom: 1rem;">🎮 暂无游戏存档</p>
      <p class="text-muted mb-3">创建角色并开始穿越，游戏进度会自动保存</p>
      <router-link to="/character-create" class="btn btn-primary">开始新游戏</router-link>
    </div>

    <!-- 游戏列表 -->
    <div v-else>
      <div class="sessions-count mb-2 text-muted">
        共 {{ gameStore.mySessions.length }} 个存档
      </div>

      <div class="grid grid-3">
        <div
          v-for="session in gameStore.mySessions"
          :key="session.id"
          class="card game-card"
        >
          <!-- 背景横幅 -->
          <div
            class="game-card-banner"
            :style="{ backgroundImage: `url(${getWorldImage(session.novel)})` }"
          >
            <div class="game-card-banner-overlay">
              <span class="badge">{{ session.novel }}</span>
            </div>
          </div>

          <!-- 卡片内容 -->
          <div class="game-card-body">
            <h3>{{ session.character_name }}</h3>

            <div class="stat-item">
              <span class="stat-label">身份</span>
              <span class="stat-value">{{ session.character_rank }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">时间节点</span>
              <span class="stat-value">{{ session.timeline }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">积分</span>
              <span class="badge badge-warning">{{ session.points }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">成就</span>
              <span class="stat-value">{{ session.achievements?.length || 0 }} 个</span>
            </div>

            <!-- 场景预览 -->
            <p v-if="session.current_scene_desc" class="scene-preview text-muted">
              {{ session.current_scene_desc }}
            </p>

            <!-- 时间 -->
            <p class="time-info text-muted text-sm">
              上次游玩：{{ formatDate(session.updated_at) }}
            </p>

            <!-- 继续按钮 -->
            <button
              class="btn btn-primary btn-block"
              @click="continueGame(session.id)"
            >
              ▶ 继续游戏
            </button>

            <!-- 删除按钮 -->
            <button
              class="btn-delete"
              @click="confirmDelete(session)"
            >
              删除存档
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="deleteTarget" class="modal-backdrop" @click.self="cancelDelete">
          <div class="confirm-dialog" @click.stop>
            <h3>确认删除</h3>
            <p>确定要删除角色 <strong>{{ deleteTarget.character_name }}</strong>（{{ deleteTarget.novel }}·{{ deleteTarget.timeline }}）的游戏存档吗？此操作不可撤销。</p>
            <div class="confirm-actions">
              <button class="btn" @click="cancelDelete" :disabled="isDeleting">取消</button>
              <button class="btn btn-delete-danger" @click="doDelete" :disabled="isDeleting">
                {{ isDeleting ? '删除中...' : '确认删除' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 错误提示 -->
    <div v-if="error" class="error-toast text-center">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/game'
import sanguoImage from '../../../images/sanguo.png'
import shuihuImage from '../../../images/shuihu.png'
import mingdaiImage from '../../../images/mingdai.png'
import hongloumengImage from '../../../images/hongloumeng.png'
import xiyouImage from '../../../images/xiyou.png'

const router = useRouter()
const gameStore = useGameStore()

const error = ref('')

const worldImageMap = {
  '三国演义': sanguoImage,
  '水浒传': shuihuImage,
  '明代': mingdaiImage,
  '清代': hongloumengImage,
  '西游记': xiyouImage
}

const getWorldImage = (novel) => worldImageMap[novel] || sanguoImage

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const deleteTarget = ref(null)
const isDeleting = ref(false)

const confirmDelete = (session) => {
  deleteTarget.value = session
}

const cancelDelete = () => {
  deleteTarget.value = null
}

const doDelete = async () => {
  if (!deleteTarget.value) return
  isDeleting.value = true
  try {
    await gameStore.deleteSession(deleteTarget.value.id)
    deleteTarget.value = null
  } catch (err) {
    error.value = '删除失败，请稍后重试'
    setTimeout(() => { error.value = '' }, 3000)
  } finally {
    isDeleting.value = false
  }
}

const continueGame = async (sessionId) => {
  try {
    await gameStore.loadExistingSession(sessionId)
    router.push(`/game/${sessionId}`)
  } catch (err) {
    error.value = '加载游戏失败，请稍后重试'
    setTimeout(() => { error.value = '' }, 3000)
  }
}

onMounted(() => {
  gameStore.listSessions()
})
</script>

<style scoped>
/* 页面导航 */
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

.sessions-count {
  font-size: 0.9rem;
}

.game-card {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.game-card-banner {
  height: 120px;
  background-size: cover;
  background-position: center;
  position: relative;
}

.game-card-banner-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.5rem 1rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
}

.game-card-banner-overlay .badge {
  font-size: 0.8rem;
}

.game-card-body {
  padding: 1.25rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.game-card-body h3 {
  font-size: 1.2rem;
  margin-bottom: 0.75rem;
  border: none;
  padding: 0;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.9rem;
}

.stat-item:last-of-type {
  border-bottom: none;
}

.stat-label {
  color: var(--text-light);
  font-weight: 500;
}

.stat-value {
  color: var(--text-color);
}

.scene-preview {
  margin-top: 0.75rem;
  font-size: 0.85rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.time-info {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
}

.text-sm {
  font-size: 0.8rem;
}

.error-toast {
  position: fixed;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  background: var(--error-color);
  color: white;
  padding: 0.75rem 2rem;
  border-radius: 8px;
  font-size: 0.95rem;
  z-index: 999;
  box-shadow: var(--shadow-md);
}

/* 删除按钮 */
.btn-delete {
  display: block;
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.4rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.85rem;
  background: transparent;
  color: var(--text-light);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-delete:hover {
  color: var(--error-color);
  border-color: var(--error-color);
  background: rgba(245, 34, 45, 0.05);
}

/* 确认弹窗 */
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

.confirm-dialog {
  background: var(--card-bg);
  border-radius: 12px;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-lg);
  padding: 2rem;
  width: 100%;
  max-width: 420px;
}

.confirm-dialog h3 {
  margin-bottom: 1rem;
  font-size: 1.25rem;
}

.confirm-dialog p {
  margin-bottom: 1.5rem;
  line-height: 1.6;
  color: var(--text-color);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-delete-danger {
  background: var(--error-color);
  color: white;
  border-color: var(--error-color);
}

.btn-delete-danger:hover {
  background: #cf1322;
}

/* 弹窗过渡 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .confirm-dialog,
.modal-leave-active .confirm-dialog {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .confirm-dialog {
  transform: scale(0.95);
}

.modal-leave-to .confirm-dialog {
  transform: scale(0.95);
}
</style>
