<template>
  <div class="game-immersive">
    <!-- ===== 全屏背景层 ===== -->
    <div
      class="game-bg"
      :style="{ backgroundImage: `url(${bgImageSrc})` }"
    ></div>

    <!-- ===== 顶部信息栏 ===== -->
    <div class="top-bar">
      <div class="top-bar-left">
        <span class="top-char-name">{{ gameStore.currentSession?.character_name }}</span>
        <span class="top-divider">·</span>
        <span>{{ gameStore.currentSession?.character_rank }}</span>
        <span class="top-divider">|</span>
        <span>{{ gameStore.currentSession?.novel }} · {{ gameStore.currentSession?.timeline }}</span>
        <span v-if="gameStore.isGenerating" class="top-streaming-dot" :title="streamStatus"></span>
      </div>
      <div class="top-bar-right">
        <span class="top-stat">⭐ {{ gameStore.currentSession?.points || 0 }}</span>
        <span class="top-stat">🏅 {{ gameStore.currentSession?.achievements?.length || 0 }}</span>
        <button class="top-menu-btn" @click="showSidebar = !showSidebar" title="菜单">
          ☰
        </button>
      </div>
    </div>

    <!-- ===== 剧情文字浮层（居中，固定尺寸，带滑动） ===== -->
    <div v-if="currentScene" class="story-overlay">
      <div class="story-text" ref="storyTextEl">
        <p>{{ displayedScene }}</p>
      </div>
    </div>

    <!-- ===== 底部行动栏 ===== -->
    <div v-if="currentScene" class="bottom-bar">
      <div class="action-buttons">
        <button
          v-for="(choice, index) in currentScene.choices"
          :key="index"
          @click="performAction(choice)"
          :disabled="gameStore.isGenerating || isAwaitingOptions"
          class="action-btn"
        >
          {{ choice }}
        </button>
        <button
          v-if="isAwaitingOptions || !currentScene.choices?.length"
          class="action-btn"
          disabled
        >
          正在生成行动选项...
        </button>
      </div>

      <div class="free-action-row">
        <textarea
          ref="actionTextarea"
          v-model="customAction"
          class="free-action-input"
          placeholder="输入自定义行动..."
          rows="1"
          @input="autoResize"
          @keyup.enter.exact="performCustomAction"
        ></textarea>
        <button
          @click="performCustomAction"
          class="free-action-submit"
          :disabled="gameStore.isGenerating || isAwaitingOptions || !customAction.trim()"
        >
          执行
        </button>
      </div>
    </div>

    <!-- 无场景（初始加载） -->
    <div v-if="!currentScene && !gameStore.isGenerating" class="initial-hint">
      <p>加载游戏中...</p>
    </div>

    <!-- 错误提示 -->
    <Transition name="fade">
      <div v-if="error" class="error-toast">
        <p>{{ error }}</p>
        <router-link v-if="needsLogin" to="/login" class="error-login-link">前往登录</router-link>
        <button @click="error = ''" class="error-close">✕</button>
      </div>
    </Transition>

    <!-- ===== 侧边栏（滑出） ===== -->
    <Transition name="panel-slide">
      <div v-if="showSidebar" class="sidebar-panel" @click.self="showSidebar = false">
        <div class="sidebar-inner">
          <div class="sidebar-header">
            <h2>📜 角色信息</h2>
            <button @click="showSidebar = false" class="sidebar-close">✕</button>
          </div>

          <div class="sidebar-section">
            <div class="stat-item">
              <span>姓名</span>
              <span class="stat-value">{{ gameStore.currentSession?.character_name }}</span>
            </div>
            <div class="stat-item">
              <span>身份</span>
              <span class="stat-value">{{ gameStore.currentSession?.character_rank }}</span>
            </div>
            <div class="stat-item">
              <span>世界</span>
              <span class="stat-value">{{ gameStore.currentSession?.novel }}</span>
            </div>
            <div class="stat-item">
              <span>时间节点</span>
              <span class="stat-value">{{ gameStore.currentSession?.timeline }}</span>
            </div>
          </div>

          <div class="sidebar-section">
            <h3>🏅 成就列表</h3>
            <ul class="achievement-list">
              <li
                v-for="(achievement, index) in gameStore.currentSession?.achievements"
                :key="index"
                class="achievement-item"
              >
                {{ achievement }}
              </li>
            </ul>
            <div v-if="!gameStore.currentSession?.achievements?.length" class="text-muted">
              暂无成就
            </div>
          </div>

          <div class="sidebar-section sidebar-actions">
            <router-link to="/character-relations" class="sidebar-link" @click="showSidebar = false">
              👥 人物关系
            </router-link>
            <router-link v-if="authStore.isAuthenticated" to="/my-games" class="sidebar-link" @click="showSidebar = false">
              📋 我的游戏
            </router-link>
            <button @click="newGame" class="sidebar-link sidebar-link-danger">
              重新开始游戏
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ===== 成就解锁 Toast ===== -->
    <Transition name="toast">
      <div v-if="achievementToast?.visible" class="achievement-toast">
        <span class="toast-icon">🏆</span>
        <span class="toast-text">成就解锁：{{ achievementToast.name }}</span>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import sanguoImage from '../../../images/sanguo.png'
import shuihuImage from '../../../images/shuihu.png'
import mingdaiImage from '../../../images/mingdai.png'
import hongloumengImage from '../../../images/hongloumeng.png'
import xiyouImage from '../../../images/xiyou.png'

const router = useRouter()
const route = useRoute()
const gameStore = useGameStore()
const authStore = useAuthStore()

const customAction = ref('')
const actionTextarea = ref(null)
const error = ref('')
const needsLogin = ref(false)
const displayedScene = ref('')
const achievementToast = ref(null)
const isAwaitingOptions = ref(false)
const currentSceneImage = ref(null)
const streamStatus = ref('AI正在生成剧情...')
const showSidebar = ref(false)

const autoResize = () => {
  const el = actionTextarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

const currentScene = computed(() => gameStore.currentSession?.current_scene)

const worldImageMap = {
  '三国演义': { src: sanguoImage },
  '水浒传': { src: shuihuImage },
  '明代': { src: mingdaiImage },
  '清代': { src: hongloumengImage },
  '西游记': { src: xiyouImage }
}
const currentWorldImage = computed(() => worldImageMap[gameStore.currentSession?.novel])

// 背景图：优先用场景匹配图，无匹配时用世界图
const bgImageSrc = computed(() => {
  if (currentSceneImage.value) return currentSceneImage.value
  if (currentWorldImage.value?.src) return currentWorldImage.value.src
  return ''
})

// 模拟打字机效果
let typewriterTimer = null
const typewriterEffect = (text) => {
  if (typewriterTimer) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
  displayedScene.value = ''
  if (!text) return

  let index = 0
  typewriterTimer = setInterval(() => {
    if (index < text.length) {
      displayedScene.value += text[index]
      index++
    } else {
      clearInterval(typewriterTimer)
      typewriterTimer = null
    }
  }, 20)
}

onMounted(async () => {
  const sessionId = route.params.id

  if (sessionId) {
    try {
      await gameStore.loadExistingSession(Number(sessionId))
    } catch (err) {
      error.value = '无法加载游戏会话，会话可能不存在或无权访问'
      return
    }
  }

  if (!gameStore.currentSession) {
    router.push('/character-create')
    return
  }

  if (currentScene.value?.scene_description) {
    typewriterEffect(currentScene.value.scene_description)
  }
  if (currentScene.value?.scene_image) {
    currentSceneImage.value = currentScene.value.scene_image
  }
})

const performAction = async (action) => {
  if (gameStore.isGenerating) return

  error.value = ''
  needsLogin.value = false
  isAwaitingOptions.value = true
  streamStatus.value = 'AI正在生成剧情...'

  try {
    displayedScene.value = ''
    gameStore.currentSession.current_scene = {
      scene_description: '',
      choices: [],
      game_update: { points_awarded: 0, new_achievement: '' }
    }

    const scene = await gameStore.performActionStream(action, {
      onStatus: (status) => {
        streamStatus.value = status.message || streamStatus.value
        if (status.phase === 'metadata') {
          isAwaitingOptions.value = true
        }
      },
      onStoryChunk: (delta) => {
        displayedScene.value += delta
      },
      onScene: (scenePayload) => {
        displayedScene.value = scenePayload.scene_description
        currentSceneImage.value = scenePayload.scene_image || null
        isAwaitingOptions.value = false
      }
    })

    if (!scene) {
      throw new Error('执行行动失败')
    }

    if (scene.game_update.new_achievement) {
      const achievements = gameStore.currentSession.achievements || []
      if (!achievements.includes(scene.game_update.new_achievement)) {
        achievements.push(scene.game_update.new_achievement)
        gameStore.currentSession.achievements = achievements
        achievementToast.value = { name: scene.game_update.new_achievement, visible: true }
        setTimeout(() => {
          if (achievementToast.value?.name === scene.game_update.new_achievement) {
            achievementToast.value = null
          }
        }, 3000)
      }
    }
  } catch (err) {
    if (err.response?.status === 429) {
      error.value = err.response.data.detail.message || '今日次数已用完'
      needsLogin.value = err.response.data.detail.needs_login
    } else {
      const detail = err.response?.data?.detail
      error.value = typeof detail === 'string' ? detail : detail?.message || err.message || '执行行动失败'
    }
  } finally {
    isAwaitingOptions.value = false
  }
}

const performCustomAction = () => {
  if (customAction.value.trim()) {
    performAction(customAction.value)
    customAction.value = ''
    if (actionTextarea.value) {
      actionTextarea.value.style.height = 'auto'
    }
  }
}

const newGame = () => {
  if (confirm('确定要重新开始游戏吗？当前进度将丢失。')) {
    gameStore.resetGame()
    router.push('/character-create')
  }
}
</script>

<style scoped>
/* ===== 全局重置 ===== */
.game-immersive {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  font-family: "Noto Serif SC", "华文楷体", "SimSun", serif;
}

/* ===== 全屏背景 ===== */
.game-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 0;
  background-size: cover;
  background-position: center center;
  background-color: #1a1a2e;
  transition: background-image 0.8s ease-in-out;
}

.game-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  z-index: 1;
}

/* ===== 顶部信息栏 ===== */
.top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 24px;
  background: linear-gradient(180deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0) 100%);
  color: #f0e6d3;
  font-size: 0.9rem;
  text-shadow: 0 1px 4px rgba(0,0,0,0.8);
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.top-char-name {
  font-weight: 700;
  font-size: 1.05rem;
  color: #ffd796;
}

.top-divider {
  opacity: 0.4;
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.top-stat {
  font-size: 0.85rem;
}

.top-menu-btn {
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
  color: #f0e6d3;
  font-size: 1.2rem;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.top-menu-btn:hover {
  background: rgba(255,255,255,0.25);
}

/* ===== 顶部流式指示点 ===== */
.top-streaming-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4ade80;
  margin-left: 8px;
  animation: stream-pulse 0.8s ease-in-out infinite;
  vertical-align: middle;
}

@keyframes stream-pulse {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.4); }
}

/* ===== 剧情文字浮层（居中固定尺寸，带滑动） ===== */
.story-overlay {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 5;
  width: 70vw;
  max-width: 900px;
  height: 55vh;
  max-height: 520px;
  background: rgba(10, 10, 25, 0.2);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 215, 150, 0.15);
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  padding: 24px 28px;
  color: #f0e6d3;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
}

.story-text {
  height: 100%;
  overflow-y: auto;
  font-size: 1.1rem;
  line-height: 1.85;
  letter-spacing: 1.5px;
  white-space: pre-wrap;
  word-break: break-word;
  padding-right: 4px;
}

.story-text p {
  margin: 0;
}

/* 滚动条美化 */
.story-text::-webkit-scrollbar {
  width: 5px;
}
.story-text::-webkit-scrollbar-track {
  background: transparent;
}
.story-text::-webkit-scrollbar-thumb {
  background: rgba(255, 215, 150, 0.2);
  border-radius: 3px;
}

/* ===== 底部行动栏 ===== */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 5;
  background: rgba(10, 10, 25, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-top: 1px solid rgba(255, 215, 150, 0.18);
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.5);
  padding: 12px 28px 18px 28px;
  color: #f0e6d3;
}

/* ===== 行动区域 ===== */
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 8px;
}

.action-btn {
  background: rgba(255, 215, 150, 0.12);
  border: 1px solid rgba(255, 215, 150, 0.3);
  color: #f0e6d3;
  padding: 7px 20px;
  border-radius: 20px;
  font-size: 0.92rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 1px;
  white-space: nowrap;
}

.action-btn:hover:not(:disabled) {
  background: rgba(255, 215, 150, 0.3);
  border-color: #ffd796;
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(255, 215, 150, 0.15);
}

.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 自由行动行 */
.free-action-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.free-action-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 215, 150, 0.2);
  color: #f0e6d3;
  padding: 7px 14px;
  border-radius: 20px;
  font-size: 0.9rem;
  font-family: inherit;
  resize: none;
  overflow: hidden;
  min-height: 36px;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.2s;
}

.free-action-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.free-action-input:focus {
  border-color: rgba(255, 215, 150, 0.5);
}

.free-action-submit {
  background: rgba(255, 215, 150, 0.2);
  border: 1px solid rgba(255, 215, 150, 0.4);
  color: #ffd796;
  padding: 7px 18px;
  border-radius: 20px;
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  flex-shrink: 0;
}

.free-action-submit:hover:not(:disabled) {
  background: rgba(255, 215, 150, 0.4);
  box-shadow: 0 4px 16px rgba(255, 215, 150, 0.2);
}

.free-action-submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ===== 初始提示 ===== */
.initial-hint {
  position: fixed;
  inset: 0;
  z-index: 15;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f0e6d3;
  font-size: 1.2rem;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6);
}

/* ===== 错误提示 ===== */
.error-toast {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 30;
  background: rgba(180, 60, 60, 0.9);
  color: white;
  padding: 12px 24px;
  border-radius: 10px;
  text-align: center;
  max-width: 500px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 4px 20px rgba(180, 60, 60, 0.4);
}

.error-toast p {
  margin: 0;
}

.error-login-link {
  color: #ffd796;
  font-weight: 600;
}

.error-close {
  background: none;
  border: none;
  color: white;
  font-size: 1.1rem;
  cursor: pointer;
  opacity: 0.7;
}

/* ===== 侧边栏面板 ===== */
.sidebar-panel {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: flex-end;
}

.sidebar-inner {
  width: 340px;
  max-width: 85vw;
  height: 100vh;
  background: rgba(15, 15, 30, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-left: 1px solid rgba(255, 215, 150, 0.15);
  padding: 24px 20px;
  overflow-y: auto;
  color: #f0e6d3;
  box-shadow: -4px 0 32px rgba(0, 0, 0, 0.6);
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #ffd796;
}

.sidebar-close {
  background: none;
  border: 1px solid rgba(255,255,255,0.2);
  color: #f0e6d3;
  font-size: 1rem;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-section h3 {
  font-size: 0.95rem;
  color: #ffd796;
  margin-bottom: 10px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: 0.88rem;
}

.stat-value {
  color: #ccc;
}

.achievement-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
}

.achievement-item {
  padding: 4px 0;
  font-size: 0.85rem;
  color: #a0d8a0;
}

.achievement-item::before {
  content: '🏅 ';
}

.text-muted {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.85rem;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: none;
}

.sidebar-link {
  display: block;
  width: 100%;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f0e6d3;
  text-align: center;
  text-decoration: none;
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s;
}

.sidebar-link:hover {
  background: rgba(255, 255, 255, 0.12);
}

.sidebar-link-danger {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.2);
}

.sidebar-link-danger:hover {
  background: rgba(248, 113, 113, 0.15);
}

/* ===== 成就 Toast ===== */
.achievement-toast {
  position: fixed;
  top: 8%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 60;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 28px;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.5);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.05rem;
  font-weight: 600;
}

.toast-icon {
  font-size: 1.4rem;
  animation: bounce 0.6s ease infinite alternate;
}

@keyframes bounce {
  from { transform: translateY(0); }
  to { transform: translateY(-4px); }
}

/* ===== Transitions ===== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.3s ease;
}
.panel-slide-enter-active .sidebar-inner,
.panel-slide-leave-active .sidebar-inner {
  transition: transform 0.3s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  background: transparent;
}
.panel-slide-enter-from .sidebar-inner,
.panel-slide-leave-to .sidebar-inner {
  transform: translateX(100%);
}

.toast-enter-active {
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.toast-leave-active {
  transition: all 0.3s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(20px) scale(0.8);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px) scale(0.9);
}

/* ===== 响应式 ===== */
@media (max-aspect-ratio: 4/3) {
  .story-overlay {
    width: 85vw;
    height: 48vh;
    padding: 16px 18px;
  }
  .story-text {
    font-size: 0.95rem;
  }
  .action-btn {
    font-size: 0.82rem;
    padding: 5px 14px;
  }
}

@media (max-width: 480px) {
  .top-bar {
    padding: 8px 14px;
    font-size: 0.78rem;
  }
  .story-overlay {
    width: 92vw;
    height: 45vh;
    padding: 14px 14px;
  }
  .story-text {
    font-size: 0.88rem;
  }
  .bottom-bar {
    padding: 10px 12px 14px 12px;
  }
  .action-buttons {
    gap: 5px 8px;
  }
  .action-btn {
    font-size: 0.78rem;
    padding: 5px 12px;
  }
}
</style>
