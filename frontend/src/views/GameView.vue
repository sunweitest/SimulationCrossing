<template>
  <div class="container game-container">
    <h1>🎮 穿越模拟</h1>

    <div class="grid">
      <!-- 左侧：角色信息 -->
      <div class="sidebar">
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
                <button @click="performCustomAction" class="btn btn-primary mt-2">
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
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/game'

const router = useRouter()
const gameStore = useGameStore()

const customAction = ref('')
const error = ref('')
const needsLogin = ref(false)
const displayedScene = ref('')

const currentScene = computed(() => gameStore.currentSession?.current_scene)

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
      }
    }

    typewriterEffect(scene.scene_description)
  } catch (err) {
    if (err.response?.status === 429) {
      error.value = err.response.data.detail.message || '今日次数已用完'
      needsLogin.value = err.response.data.detail.needs_login
    } else {
      error.value = err.response?.data?.detail || '执行行动失败'
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

.main-content {
  min-height: 600px;
}

.custom-action {
  display: flex;
  flex-direction: column;
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

@media (max-width: 1024px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}
</style>
