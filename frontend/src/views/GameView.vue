<template>
  <div class="container game-container">
    <h1>🎮 穿越模拟</h1>

    <div class="grid">
      <!-- 左侧：角色信息 -->
      <div class="sidebar">
        <div
          v-if="currentWorldImage"
          class="world-card"
          :style="{ backgroundImage: `url(${currentWorldImage.src})` }"
        >
          <div class="world-card-caption">
            <span>{{ gameStore.currentSession?.novel }}</span>
            <strong>{{ gameStore.currentSession?.timeline }}</strong>
          </div>
        </div>

        <div class="card game-stats">
          <h3>📜 角色信息</h3>
          <div v-if="gameStore.currentSession">
            <div class="stat-item">
              <span>姓名</span>
              <span class="badge">{{ gameStore.currentSession.character_name }}</span>
            </div>
            <div class="stat-item">
              <span>身份</span>
              <span>{{ gameStore.currentSession.character_rank }}</span>
            </div>
            <div class="stat-item">
              <span>世界</span>
              <span>{{ gameStore.currentSession.novel }}</span>
            </div>
            <div class="stat-item">
              <span>时间节点</span>
              <span>{{ gameStore.currentSession.timeline }}</span>
            </div>
          </div>
        </div>

        <div class="card game-stats mt-3">
          <h3>🏆 游戏状态</h3>
          <div v-if="gameStore.currentSession">
            <div class="stat-item">
              <span>积分</span>
              <span class="badge badge-warning">{{ gameStore.currentSession.points }}</span>
            </div>
            <div class="stat-item">
              <span>成就数量</span>
              <span class="badge badge-success">{{ gameStore.currentSession.achievements?.length || 0 }}</span>
            </div>
          </div>

          <h4 class="mt-3">🏅 成就列表</h4>
          <ul class="achievement-list">
            <li
              v-for="(achievement, index) in gameStore.currentSession?.achievements"
              :key="index"
              class="achievement-item"
            >
              {{ achievement }}
            </li>
          </ul>
          <div v-if="!gameStore.currentSession?.achievements?.length" class="text-center text-muted mt-2">
            暂无成就
          </div>
        </div>

        <button @click="newGame" class="btn btn-secondary btn-block mt-3">
          重新开始游戏
        </button>
      </div>

      <!-- 中间：游戏主界面 -->
      <div class="main-content">
        <div class="card">
          <h2>🎭 游戏进行中</h2>

          <!-- 加载中 -->
          <div v-if="gameStore.isGenerating" class="loading">
            <div class="spinner"></div>
            <p class="mt-2">⏳ AI正在生成剧情...</p>
          </div>

          <!-- 剧情显示 -->
          <div v-else-if="currentScene">
            <div class="scene-description">
              <h3>📖 剧情发展</h3>
              <p>{{ displayedScene }}</p>
            </div>

            <div class="mt-3">
              <h3>🎯 行动建议</h3>
              <div class="choice-group">
                <button
                  v-for="(choice, index) in currentScene.choices"
                  :key="index"
                  @click="performAction(choice)"
                  :disabled="gameStore.isGenerating"
                  class="btn choice-btn"
                >
                  {{ choice }}
                </button>
              </div>
            </div>

            <div class="mt-3">
              <h3>💬 自由行动</h3>
              <div class="custom-action">
                <input
                  v-model="customAction"
                  type="text"
                  class="input"
                  placeholder="或者输入自定义行动..."
                  @keyup.enter="performCustomAction"
                />
                <button
                  @click="performCustomAction"
                  class="btn btn-primary mt-2"
                  :disabled="gameStore.isGenerating || !customAction.trim()"
                >
                  执行行动
                </button>
              </div>
            </div>
          </div>

          <!-- 无场景 -->
          <div v-else class="text-center text-muted">
            <p>加载游戏中...</p>
          </div>

          <!-- 错误提示 -->
          <div v-if="error" class="error-message mt-3">
            {{ error }}
            <div v-if="needsLogin" class="mt-2">
              <router-link to="/login" class="btn btn-primary">前往登录</router-link>
            </div>
          </div>

          <!-- 成就解锁提示 -->
          <Transition name="toast">
            <div v-if="achievementToast?.visible" class="achievement-toast">
              <span class="toast-icon">🏆</span>
              <span class="toast-text">成就解锁：{{ achievementToast.name }}</span>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/game'
import sanguoImage from '../../../images/sanguo.png'
import shuihuImage from '../../../images/shuihu.png'
import mingdaiImage from '../../../images/mingdai.png'
import hongloumengImage from '../../../images/hongloumeng.png'

const router = useRouter()
const gameStore = useGameStore()

const customAction = ref('')
const error = ref('')
const needsLogin = ref(false)
const displayedScene = ref('')
const achievementToast = ref(null)  // { name, visible }

const currentScene = computed(() => gameStore.currentSession?.current_scene)
const worldImageMap = {
  '三国演义': { src: sanguoImage },
  '水浒传': { src: shuihuImage },
  '明代': { src: mingdaiImage },
  '清代': { src: hongloumengImage }
}
const currentWorldImage = computed(() => worldImageMap[gameStore.currentSession?.novel])

// 模拟打字机效果
const typewriterEffect = (text) => {
  displayedScene.value = ''
  let index = 0
  const interval = setInterval(() => {
    if (index < text.length) {
      displayedScene.value += text[index]
      index++
    } else {
      clearInterval(interval)
    }
  }, 20)
}

onMounted(() => {
  if (!gameStore.currentSession) {
    router.push('/character-create')
    return
  }

  if (currentScene.value?.scene_description) {
    typewriterEffect(currentScene.value.scene_description)
  }
})

const performAction = async (action) => {
  if (gameStore.isGenerating) return

  error.value = ''
  needsLogin.value = false

  try {
    const scene = await gameStore.performAction(action)

    // 更新会话以包含新场景
    gameStore.currentSession.current_scene = scene
    gameStore.currentSession.points += scene.game_update.points_awarded

    if (scene.game_update.new_achievement) {
      const achievements = gameStore.currentSession.achievements || []
      if (!achievements.includes(scene.game_update.new_achievement)) {
        achievements.push(scene.game_update.new_achievement)
        gameStore.currentSession.achievements = achievements
        // 显示成就解锁提示
        achievementToast.value = { name: scene.game_update.new_achievement, visible: true }
        setTimeout(() => {
          if (achievementToast.value?.name === scene.game_update.new_achievement) {
            achievementToast.value = null
          }
        }, 3000)
      }
    }

    typewriterEffect(scene.scene_description)
  } catch (err) {
    if (err.response?.status === 429) {
      error.value = err.response.data.detail.message || '今日次数已用完'
      needsLogin.value = err.response.data.detail.needs_login
    } else {
      const detail = err.response?.data?.detail
      error.value = typeof detail === 'string' ? detail : detail?.message || '执行行动失败'
    }
  }
}

const performCustomAction = () => {
  if (customAction.value.trim()) {
    performAction(customAction.value)
    customAction.value = ''
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
.game-container {
  max-width: 1400px;
}

.grid {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 2rem;
}

.sidebar {
  position: sticky;
  top: 2rem;
  height: fit-content;
}

.world-card {
  min-height: 220px;
  margin-bottom: 1rem;
  border-radius: 8px;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: flex-end;
}

.world-card-caption {
  width: 100%;
  padding: 1rem;
  color: white;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0), rgba(18, 18, 18, 0.8));
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
}

.world-card-caption span,
.world-card-caption strong {
  display: block;
}

.world-card-caption span {
  font-size: 0.9rem;
}

.world-card-caption strong {
  font-size: 1.25rem;
  line-height: 1.25;
}

.main-content {
  min-height: 600px;
}

.custom-action {
  display: flex;
  flex-direction: column;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.error-message {
  padding: 1rem;
  background: var(--error-color);
  color: white;
  border-radius: 8px;
  text-align: center;
}

h4 {
  font-size: 1rem;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

/* 成就解锁提示 */
.achievement-toast {
  position: fixed;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  z-index: 1000;
  font-size: 1.1rem;
  font-weight: 600;
}

.toast-icon {
  font-size: 1.5rem;
  animation: bounce 0.6s ease infinite alternate;
}

@keyframes bounce {
  from { transform: translateY(0); }
  to { transform: translateY(-4px); }
}

/* Toast 过渡动画 */
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

@media (max-width: 1024px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}
</style>
