<template>
  <div class="container character-relations-container">
    <div class="header">
      <button @click="goBack" class="btn btn-secondary">&larr; 返回游戏</button>
      <h1>👥 人物关系</h1>
      <div class="header-info">
        <span v-if="worldLabel">{{ worldLabel }}</span>
        <span v-if="turnLabel" class="turn-badge">{{ turnLabel }}</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>加载人物数据...</p>
    </div>

    <!-- 无数据 -->
    <div v-else-if="!characters.length" class="empty-state">
      <p class="text-muted">🎭 尚未遇到任何人物</p>
      <p class="text-small text-muted">随着剧情推进，与你互动的人物将出现在这里</p>
    </div>

    <!-- 人物卡片网格 -->
    <div v-else class="character-grid">
      <div
        v-for="(char, index) in characters"
        :key="index"
        class="character-card"
        :class="statusClass(char.status)"
      >
        <div class="card-header">
          <span class="char-name">{{ char.name }}</span>
          <span class="char-status" :class="statusClass(char.status)">
            {{ char.status }}
          </span>
        </div>

        <div class="card-body">
          <div class="info-row">
            <span class="info-label">身份</span>
            <span class="info-value">{{ char.identity || '未知' }}</span>
          </div>

          <div class="info-row">
            <span class="info-label">关系</span>
            <span class="info-value relationship">{{ char.relationship_to_player || '未知' }}</span>
          </div>

          <div class="info-row">
            <span class="info-label">好感度</span>
            <div class="favorability-bar-wrapper">
              <div class="favorability-bar">
                <div
                  class="favorability-fill"
                  :class="favorabilityClass(char.favorability)"
                  :style="{ width: favorabilityWidth(char.favorability) }"
                ></div>
              </div>
              <span class="favorability-value" :class="favorabilityClass(char.favorability)">
                {{ char.favorability ?? 0 }}
              </span>
            </div>
          </div>

          <div v-if="char.last_interaction" class="info-row last-interaction">
            <span class="info-label">最近互动</span>
            <span class="info-value">{{ char.last_interaction }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGameStore } from '@/stores/game'

const router = useRouter()
const route = useRoute()
const gameStore = useGameStore()

const loading = ref(false)

const characters = computed(() => {
  const state = gameStore.currentSession?.characters_state
  if (!state) return []
  return state.characters || []
})

const worldLabel = computed(() => {
  const s = gameStore.currentSession
  if (!s) return ''
  return `${s.novel} · ${s.timeline}`
})

const turnLabel = computed(() => {
  const state = gameStore.currentSession?.characters_state
  if (!state?.last_updated_turn) return ''
  return `更新于第 ${state.last_updated_turn} 轮`
})

onMounted(async () => {
  if (!gameStore.currentSession) {
    router.push('/character-create')
    return
  }

  // 每次进入页面重新加载 session，获取最新的 characters_state
  // （characters_state 由后台压缩任务异步更新）
  const sessionId = gameStore.currentSession.id
  if (sessionId) {
    loading.value = true
    try {
      await gameStore.loadExistingSession(sessionId)
    } catch {
      // 加载失败时用已有数据继续
    } finally {
      loading.value = false
    }
  }
})

const goBack = () => {
  const sessionId = gameStore.currentSession?.id
  router.push(sessionId ? `/game/${sessionId}` : '/game')
}

const favorabilityWidth = (score) => {
  // -100 → 0%, 0 → 50%, 100 → 100%
  const pct = ((score ?? 0) + 100) / 2
  return Math.max(0, Math.min(100, pct)) + '%'
}

const favorabilityClass = (score) => {
  const s = score ?? 0
  if (s >= 50) return 'fav-high'
  if (s >= 20) return 'fav-positive'
  if (s >= -20) return 'fav-neutral'
  if (s >= -50) return 'fav-negative'
  return 'fav-hostile'
}

const statusClass = (status) => {
  switch (status) {
    case '存活': return 'status-alive'
    case '死亡': return 'status-dead'
    case '离开': return 'status-gone'
    case '敌对': return 'status-hostile'
    case '同盟': return 'status-allied'
    default: return ''
  }
}
</script>

<style scoped>
.character-relations-container {
  max-width: 1200px;
  padding-top: 2rem;
  padding-bottom: 3rem;
  color: #e0e0e0;
  min-height: 100vh;
  background: #1a1a2e;
}

.header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

.header h1 {
  margin: 0;
  flex: 1;
  color: #f0f0f0;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.9rem;
  color: #8b949e;
}

.turn-badge {
  background: rgba(102, 126, 234, 0.2);
  color: #8fadff;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: #8b949e;
}

.empty-state p {
  margin-bottom: 0.5rem;
}

.text-small {
  font-size: 0.85rem;
}

/* 卡片网格 */
.character-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

.character-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
  backdrop-filter: blur(8px);
}

.character-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

/* 状态边框颜色 */
.character-card.status-alive { border-left: 3px solid #4ade80; }
.character-card.status-dead { border-left: 3px solid #6b7280; }
.character-card.status-gone { border-left: 3px solid #f59e0b; }
.character-card.status-hostile { border-left: 3px solid #ef4444; }
.character-card.status-allied { border-left: 3px solid #3b82f6; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.char-name {
  font-size: 1.15rem;
  font-weight: 700;
  color: #f0f0f0;
}

.char-status {
  font-size: 0.8rem;
  padding: 0.15rem 0.65rem;
  border-radius: 10px;
  font-weight: 600;
}

.char-status.status-alive { background: rgba(74, 222, 128, 0.18); color: #4ade80; }
.char-status.status-dead { background: rgba(107, 114, 128, 0.18); color: #9ca3af; }
.char-status.status-gone { background: rgba(245, 158, 11, 0.18); color: #fbbf24; }
.char-status.status-hostile { background: rgba(239, 68, 68, 0.18); color: #f87171; }
.char-status.status-allied { background: rgba(59, 130, 246, 0.18); color: #60a5fa; }

.card-body {
  padding: 1rem;
}

.info-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.4rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 0.85rem;
  color: #8b949e;
  flex-shrink: 0;
  min-width: 4em;
}

.info-value {
  font-size: 0.9rem;
  color: #d0d0d0;
  text-align: right;
  line-height: 1.4;
}

.info-value.relationship {
  font-weight: 600;
  color: #f0c040;
}

/* 好感度条 */
.favorability-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  max-width: 180px;
}

.favorability-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 3px;
  overflow: hidden;
}

.favorability-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.favorability-fill.fav-high { background: #4ade80; }
.favorability-fill.fav-positive { background: #86efac; }
.favorability-fill.fav-neutral { background: #9ca3af; }
.favorability-fill.fav-negative { background: #f59e0b; }
.favorability-fill.fav-hostile { background: #ef4444; }

.favorability-value {
  font-size: 0.85rem;
  font-weight: 700;
  min-width: 2.5em;
  text-align: right;
}

.favorability-value.fav-high { color: #4ade80; }
.favorability-value.fav-positive { color: #86efac; }
.favorability-value.fav-neutral { color: #9ca3af; }
.favorability-value.fav-negative { color: #f59e0b; }
.favorability-value.fav-hostile { color: #ef4444; }

.last-interaction .info-value {
  max-width: 280px;
  font-size: 0.82rem;
  color: #8b949e;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4rem;
  gap: 1rem;
  color: #8b949e;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 深色主题按钮覆盖 */
.character-relations-container :deep(.btn) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
  color: #e0e0e0;
}

.character-relations-container :deep(.btn:hover) {
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.35);
  color: #fff;
}

@media (max-width: 768px) {
  .character-grid {
    grid-template-columns: 1fr;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
