<template>
  <div class="game-immersive" :class="{ 'has-mission': !!mission }">
    <!-- ===== 全屏背景层 ===== -->
    <div
      class="game-bg"
      :style="{ backgroundImage: bgImageStyle }"
    ></div>

    <!-- ===== 顶部信息栏 ===== -->
    <div class="top-bar">
      <div class="top-bar-left">
        <button class="player-chip" @click="openProfile" title="查看当前角色">
          <img v-if="playerAvatar" :src="playerAvatar" :alt="playerName" class="player-avatar">
          <span v-else class="player-avatar player-avatar-fallback">{{ playerInitial }}</span>
        </button>
        <span class="top-char-name">{{ gameStore.currentSession?.character_name }}</span>
        <span class="top-divider">·</span>
        <span>{{ gameStore.currentSession?.character_rank }}</span>
        <span class="top-divider">|</span>
        <span>{{ gameStore.currentSession?.novel }} · {{ gameStore.currentSession?.timeline }}</span>
        <span v-if="gameStore.isGenerating" class="top-streaming-dot" :title="streamStatus"></span>
      </div>
      <div class="top-bar-right">
        <span v-if="quota" :class="['top-stat', 'quota-stat', { 'quota-empty': quota.remaining === 0 }]" :title="quotaTitle">
          <template v-if="quota.is_unlimited">♾️ 不限次</template>
          <template v-else-if="quota.remaining === null || quota.remaining === undefined">💬 —</template>
          <template v-else>💬 剩 {{ quota.remaining }} 次</template>
        </span>
        <span class="top-stat">⭐ {{ gameStore.currentSession?.points || 0 }}</span>
        <span class="top-stat">🏅 {{ gameStore.currentSession?.achievements?.length || 0 }}</span>
        <button class="top-menu-btn" @click="toggleSound" :title="soundOn ? '关闭音效' : '开启音效'">
          {{ soundOn ? '🔊' : '🔇' }}
        </button>
        <button class="top-menu-btn" @click="openTurns" title="回到之前的回合">⏪</button>
        <button class="top-menu-btn" @click="showSidebar = !showSidebar" title="菜单">
          ☰
        </button>
      </div>
    </div>

    <!-- ===== 使命条 ===== -->
    <div
      v-if="mission"
      class="mission-bar"
      :class="{ 'mb-open': missionOpen, 'mb-failed': mission.status === 'failed', 'mb-done': mission.status === 'done' }"
      @click="missionOpen = !missionOpen"
    >
      <span class="mb-mark">◎</span>
      <span v-if="mission.act >= 2" class="mb-chip mb-act">{{ actLabel }}</span>
      <span class="mb-title">{{ mission.title }}</span>
      <span v-if="mission.status === 'done'" class="mb-chip mb-chip-done">使命达成</span>
      <span v-else-if="mission.status === 'failed'" class="mb-chip mb-chip-failed">使命未竟</span>
      <template v-else>
        <span class="mb-chip">阶段 {{ Math.min(mission.stage_index + 1, mission.stage_count) }}/{{ mission.stage_count }}</span>
        <span class="mb-chip mb-days" :class="{ 'mb-urgent': mission.days_left <= 3 }">剩 {{ mission.days_left }} 回合</span>
      </template>
      <span v-if="mission.last_label" class="mb-last" :class="`mb-last-${mission.last_label}`">{{ mission.last_label }}</span>
    </div>

    <div v-if="mission && missionOpen" class="mission-panel">
      <p class="mp-goal">{{ mission.goal }}</p>
      <ol class="mp-stages">
        <li
          v-for="(stage, i) in mission.stages"
          :key="i"
          :class="{ 'mp-done': i < mission.stage_index, 'mp-current': i === mission.stage_index }"
        >
          <span class="mp-dot">{{ i < mission.stage_index ? '✓' : i + 1 }}</span>{{ stage }}
        </li>
      </ol>
      <p class="mp-stakes">赌注：{{ mission.stakes }}</p>
      <p v-if="mission.last_note" class="mp-note">上一回合：{{ mission.last_note }}</p>
    </div>

    <!-- ===== 剧情文字浮层（居中，固定尺寸，带滑动） ===== -->
    <div v-if="currentScene" class="story-overlay">
      <div class="story-text" ref="storyTextEl">
        <p>{{ displayedScene }}</p>
      </div>
    </div>

    <!-- ===== 终局面板 ===== -->
    <div v-if="mission?.ended" class="ending-mask">
      <div class="ending-card">
        <p class="ending-kicker">— 终局 —</p>
        <h2 class="ending-title">{{ gameStore.currentSession?.character_name }} 死了</h2>
        <p class="ending-line">{{ endingLine }}</p>
        <div class="ending-stats">
          <div><span class="es-num">{{ gameStore.currentSession?.points || 0 }}</span><span class="es-label">积分</span></div>
          <div><span class="es-num">{{ gameStore.currentSession?.achievements?.length || 0 }}</span><span class="es-label">成就</span></div>
        </div>
        <div class="ending-actions">
          <button class="ending-btn primary" @click="restartSameCharacter">用同一个角色重开</button>
          <button class="ending-btn" @click="backToHome">回到主界面</button>
        </div>
        <p class="ending-hint">这一局已经存档，可在「我的游戏」里回看</p>
      </div>
    </div>

    <!-- ===== 底部行动栏 ===== -->
    <div v-if="currentScene && !mission?.ended" class="bottom-bar" ref="bottomBarEl">
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
          maxlength="200"
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

    <!-- 加载失败 -->
    <div v-if="loadFailed && !currentScene" class="initial-hint">
      <p class="load-failed-text">{{ error }}</p>
      <div class="load-failed-actions">
        <button class="load-failed-btn" @click="goMyGames">去我的游戏</button>
        <button class="load-failed-btn ghost" @click="backToHome">回到主界面</button>
      </div>
    </div>

    <!-- 无场景（初始加载） -->
    <div v-else-if="!currentScene && !gameStore.isGenerating" class="initial-hint">
      <p>加载游戏中...</p>
    </div>

    <!-- 错误提示 -->
    <Transition name="fade">
      <div v-if="error" class="error-toast">
        <p>{{ error }}</p>
        <router-link v-if="needsLogin" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="error-login-link">前往登录</router-link>
        <button @click="error = ''" class="error-close">✕</button>
      </div>
    </Transition>

    <!-- 登录用户次数用完：弹窗引导充值 -->
    <Transition name="fade">
      <div v-if="showQuotaModal" class="quota-modal-mask" @click.self="showQuotaModal = false">
        <div class="quota-modal">
          <div class="quota-modal-icon">⏳</div>
          <h3>今天的次数用完了</h3>
          <p class="quota-modal-desc">
            免费次数每天 0 点自动恢复。<br>
            想现在继续，可以买次数包或开通月卡。
          </p>
          <div class="quota-modal-qq">
            <span class="qq-label">作者 QQ</span>
            <span class="qq-number">{{ QQ_NUMBER }}</span>
          </div>
          <p class="quota-modal-tip">
            {{ qqCopied ? 'QQ 号已复制，去 QQ 搜索添加即可' : '加好友时备注「穿越次数」，作者会尽快回复' }}
          </p>
          <div class="quota-modal-actions">
            <button class="btn-pricing" @click="goPricing">查看定价与开通</button>
            <button class="btn-copy-qq" @click="copyQQ">{{ qqCopied ? '✅ 已复制' : '复制 QQ 号' }}</button>
            <button class="btn-later" @click="showQuotaModal = false">明天再说</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 当前角色详情 -->
    <Transition name="fade">
      <div v-if="showProfile" class="quota-modal-mask" @click.self="showProfile = false">
        <div class="profile-modal">
          <div class="profile-head">
            <img v-if="playerAvatar" :src="playerAvatar" :alt="playerName" class="profile-avatar">
            <span v-else class="profile-avatar profile-avatar-fallback">{{ playerInitial }}</span>
            <div class="profile-title">
              <h3>{{ playerName }}</h3>
              <p>{{ profileRank }} · {{ gameStore.currentSession?.novel }}</p>
              <p class="profile-timeline">{{ gameStore.currentSession?.timeline }}</p>
            </div>
          </div>

          <div class="profile-stats">
            <div><span class="ps-num">{{ playerGender }}</span><span class="ps-label">性别</span></div>
            <div><span class="ps-num">{{ playerAge }}</span><span class="ps-label">年龄</span></div>
            <div><span class="ps-num">{{ gameStore.currentSession?.points || 0 }}</span><span class="ps-label">积分</span></div>
            <div><span class="ps-num">{{ currentTurn ?? '—' }}</span><span class="ps-label">已过回合</span></div>
          </div>

          <div v-if="currentMission" class="profile-mission">
            <span class="pm-label">当前使命</span>
            <strong>{{ currentMission.title }}</strong>
            <p>{{ currentMission.goal }}</p>
            <p class="pm-meta">
              阶段 {{ (currentMission.stage_index || 0) + 1 }}/{{ currentMission.stage_count || 3 }}
              · 剩 {{ currentMission.days_left ?? '—' }} 回合
            </p>
          </div>

          <div v-if="playerBackground" class="profile-bg">
            <h4>角色背景</h4>
            <p>{{ playerBackground }}</p>
          </div>

          <div class="profile-actions">
            <button class="btn-relations" @click="goRelations">人物关系</button>
            <button class="btn-later" @click="showProfile = false">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 回合回溯 -->
    <Transition name="fade">
      <div v-if="showTurnsPanel" class="quota-modal-mask" @click.self="closeTurns">
        <div class="quota-modal turns-modal">
          <h3>⏪ 回到之前的回合</h3>
          <p class="quota-modal-desc">
            选一个回合重来，之后的剧情会被丢弃，积分和成就一起回退。<br>
            <span class="turns-note">回溯不消耗次数</span>
          </p>

          <div class="turns-list">
            <button
              v-for="t in turns"
              :key="t.turn_index"
              class="turn-item"
              :class="{ 'turn-current': t.is_current, 'turn-selected': rewindTarget === t.turn_index }"
              @click="rewindTarget = t.turn_index"
            >
              <div class="turn-head">
                <span class="turn-no">{{ t.turn_index === 0 ? '🎬 开局' : `第 ${t.turn_index} 回合` }}</span>
                <span v-if="t.points_awarded" class="turn-points">+{{ t.points_awarded }}</span>
                <span v-if="t.is_current" class="turn-now">当前</span>
              </div>
              <div class="turn-preview">{{ t.preview }}</div>
              <div v-if="t.choice" class="turn-choice">你当时选了：{{ t.choice }}</div>
            </button>
            <p v-if="!turns.length" class="turns-empty">还没有回合记录</p>
          </div>

          <div class="quota-modal-actions">
            <button
              class="btn-copy-qq"
              :disabled="rewinding || rewindTarget === null || rewindTarget === currentTurn"
              @click="doRewind"
            >
              {{ rewinding ? '回溯中…' : (rewindTarget === currentTurn ? '已经在当前回合' : '回到这一回合') }}
            </button>
            <button class="btn-later" @click="closeTurns">取消</button>
          </div>
        </div>
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
            <button @click="showSidebar = false; openTurns()" class="sidebar-link">
              ⏪ 回到之前的回合
            </button>
            <button @click="backToHome" class="sidebar-link">
              ← 回到主界面
            </button>
            <p class="sidebar-hint">进度已自动保存，可在「我的游戏」继续</p>
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
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import { gameAPI, communityAPI } from '@/api'
import { WORLD_AMBIENCE, AMBIENCE_VOLUME, AMBIENCE_DUCKED } from '@/content/ambience'
import { WORLD_ART, heroOf, thumbOf, captionOf, bgLayers } from '@/utils/worldArt'
import { AUTHOR_QQ } from '@/content/contact'

const router = useRouter()
const route = useRoute()
const gameStore = useGameStore()
const authStore = useAuthStore()

const customAction = ref('')
const actionTextarea = ref(null)
const error = ref('')
const needsLogin = ref(false)
const loadFailed = ref(false)

// 登录用户次数用完 → 弹窗引导充值
const QQ_NUMBER = AUTHOR_QQ
const showProfile = ref(false)
const playerAvatar = ref('')
const showQuotaModal = ref(false)
const playerName = computed(() => gameStore.currentSession?.character_name || '我')
const playerInitial = computed(() => (playerName.value || '我').trim().slice(0, 1))
const profileRank = computed(() => gameStore.currentSession?.character_rank || '身份未定')
const playerGender = computed(() => gameStore.currentSession?.character_gender || '—')
const playerAge = computed(() => gameStore.currentSession?.character_age ?? '—')
const playerBackground = computed(() => gameStore.currentSession?.character_background || '')
const currentMission = computed(() => {
  const session = gameStore.currentSession
  return session?.mission_state?.mission || session?.current_scene?.mission || null
})

const goRelations = () => {
  const s = gameStore.currentSession
  if (!s) return
  showProfile.value = false
  router.push({ path: '/character-relations', query: { novel: s.novel, name: s.character_name, timeline: s.timeline } })
}

// 预设角色有头像；自定义角色没有，就用首字兜底
const openProfile = async () => {
  showProfile.value = true
  const sid = gameStore.currentSession?.id
  if (!sid || turns.value.length) return
  try {
    const list = await gameAPI.getTurns(sid)
    turns.value = Array.isArray(list) ? list : []
  } catch {
    /* 只是显示用，拿不到就留「—」 */
  }
}

const loadPlayerAvatar = async () => {
  const session = gameStore.currentSession
  if (!session?.novel || !session?.character_name) return
  try {
    const data = await communityAPI.getWorldCharacters(session.novel)
    const hit = (data.characters || []).find((c) => c.name === session.character_name)
    playerAvatar.value = hit?.image || ''
  } catch {
    playerAvatar.value = ''
  }
}

const goPricing = () => {
  showQuotaModal.value = false
  router.push('/pricing')
}
const qqCopied = ref(false)
const copyQQ = async () => {
  try {
    await navigator.clipboard.writeText(QQ_NUMBER)
  } catch (e) {
    // 非 https 或旧浏览器：退化到选中文本复制
    const el = document.createElement('textarea')
    el.value = QQ_NUMBER
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  qqCopied.value = true
  setTimeout(() => { qqCopied.value = false }, 3000)
}
const displayedScene = ref('')
const achievementToast = ref(null)
const isAwaitingOptions = ref(false)
const currentSceneImage = ref(null)
const soundOn = ref(localStorage.getItem('sfx_enabled') !== '0')
let lastSfxAt = 0
let lastSfxName = ''
let lastSfxKey = ''
let currentSfxAudio = null

const toggleSound = () => {
  soundOn.value = !soundOn.value
  localStorage.setItem('sfx_enabled', soundOn.value ? '1' : '0')
  if (!soundOn.value) {
    if (currentSfxAudio) {
      currentSfxAudio.pause()
      currentSfxAudio = null
    }
    stopAmbience(400)
  } else if (gameStore.currentSession?.novel) {
    startAmbience(gameStore.currentSession.novel)
  }
}

// 环境音床：每世界一条 20 秒循环，默认开，音量压得很低
let ambientAudio = null
let ambientSrc = ''
let ambientUnlockBound = false
let ambientUnlock = null

const fadeTo = (audio, target, ms = 600) => {
  if (!audio) return
  const from = audio.volume
  const steps = 12
  let i = 0
  const timer = setInterval(() => {
    i += 1
    const v = from + ((target - from) * i) / steps
    audio.volume = Math.min(1, Math.max(0, v))
    if (i >= steps) clearInterval(timer)
  }, ms / steps)
}

const detachUnlock = () => {
  if (!ambientUnlock) return
  document.removeEventListener('pointerdown', ambientUnlock)
  document.removeEventListener('keydown', ambientUnlock)
  ambientUnlock = null
  ambientUnlockBound = false
}

const stopAmbience = (fadeMs = 500) => {
  if (!ambientAudio) return
  const audio = ambientAudio
  ambientAudio = null
  ambientSrc = ''
  fadeTo(audio, 0, fadeMs)
  setTimeout(() => {
    try { audio.pause() } catch { /* 忽略 */ }
  }, fadeMs + 80)
}

const startAmbience = async (novel) => {
  const src = WORLD_AMBIENCE[novel] || ''
  if (!soundOn.value || !src) {
    if (!src) stopAmbience(300)
    return
  }
  if (ambientAudio && ambientSrc === src) {
    if (ambientAudio.paused) ambientAudio.play().catch(() => {})
    return
  }
  stopAmbience(300)
  const audio = new Audio(src)
  audio.loop = true
  audio.muted = true      // 先静音播放：浏览器允许，避免被自动播放策略拦掉
  audio.volume = 0
  ambientAudio = audio
  ambientSrc = src
  const unmute = () => {
    if (!ambientAudio) return
    ambientAudio.muted = false
    fadeTo(ambientAudio, AMBIENCE_VOLUME, 1200)
    detachUnlock()
  }
  try {
    await audio.play()
    // 静音状态下已在播放，等用户第一次交互再出声
    if (!ambientUnlockBound) {
      ambientUnlockBound = true
      ambientUnlock = unmute
      document.addEventListener('pointerdown', ambientUnlock)
      document.addEventListener('keydown', ambientUnlock)
    }
  } catch {
    // 连静音播放都被拒（极少数策略）：退回到「等手势再播」
    if (!ambientUnlockBound) {
      ambientUnlockBound = true
      ambientUnlock = () => {
        if (!ambientAudio) return
        ambientAudio.muted = false
        ambientAudio.play()
          .then(() => {
            fadeTo(ambientAudio, AMBIENCE_VOLUME, 1200)
            detachUnlock()
          })
          .catch(() => {})
      }
      document.addEventListener('pointerdown', ambientUnlock)
      document.addEventListener('keydown', ambientUnlock)
    }
  }
}

// 一回合最多一个短音效；同名 6 秒内不重复，避免连着两回合都在「拔刀」
const playSfx = (sfx, sceneKey = '') => {
  if (!soundOn.value || !sfx?.url) return
  // 同一段剧情（流式结束会和最终结果各触发一次）只响一次
  if (sceneKey && sceneKey === lastSfxKey) return
  if (sceneKey) lastSfxKey = sceneKey
  const now = Date.now()
  if (now - lastSfxAt < 1200) return
  if (sfx.name === lastSfxName && now - lastSfxAt < 6000) return
  lastSfxAt = now
  lastSfxName = sfx.name
  try {
    if (currentSfxAudio) currentSfxAudio.pause()
    const audio = new Audio(sfx.url)
    audio.volume = 0.5
    currentSfxAudio = audio
    audio.play().catch(() => { /* 浏览器不给放就静默 */ })
    // 台词/打斗音效期间把环境音压下去，避免糊在一起
    if (ambientAudio) {
      fadeTo(ambientAudio, AMBIENCE_DUCKED, 200)
      setTimeout(() => {
        if (ambientAudio) fadeTo(ambientAudio, AMBIENCE_VOLUME, 800)
      }, Math.max(1200, ((sfx.duration || 2) + 0.6) * 1000))
    }
  } catch {
    /* 播放失败不影响剧情 */
  }
}
const streamStatus = ref('AI正在生成剧情...')
const showSidebar = ref(false)

// ── 回合回溯 ──────────────────────────────────────────────
const showTurnsPanel = ref(false)
const turns = ref([])
const rewindTarget = ref(null)
const rewinding = ref(false)
const currentTurn = computed(() => (turns.value.length ? turns.value[turns.value.length - 1].turn_index : null))

const openTurns = async () => {
  const sid = gameStore.currentSession?.id
  if (!sid) return
  rewindTarget.value = null
  turns.value = []
  showTurnsPanel.value = true
  try {
    const list = await gameAPI.getTurns(sid)
    turns.value = Array.isArray(list) ? list : []
  } catch (e) {
    error.value = '读取回合记录失败，请稍后再试'
    showTurnsPanel.value = false
  }
}

const closeTurns = () => {
  showTurnsPanel.value = false
  rewindTarget.value = null
}

const doRewind = async () => {
  const sid = gameStore.currentSession?.id
  if (!sid || rewindTarget.value === null || rewinding.value) return
  rewinding.value = true
  try {
    const res = await gameAPI.rewind(sid, rewindTarget.value)
    if (gameStore.currentSession) {
      gameStore.currentSession.current_scene = res.current_scene
      gameStore.currentSession.points = res.points
      gameStore.currentSession.achievements = res.achievements
    }
    displayedScene.value = res.current_scene?.scene_description || ''
    currentSceneImage.value = res.current_scene?.scene_image || null
    showTurnsPanel.value = false
    showSidebar.value = false
    const label = res.turn_index === 0 ? '开局' : `第 ${res.turn_index} 回合`
    achievementToast.value = { text: `已回到${label}，之后的 ${res.removed_turns} 回合已丢弃` }
    setTimeout(() => { achievementToast.value = null }, 3000)
  } catch (e) {
    error.value = e?.response?.data?.detail || '回溯失败，请稍后再试'
  } finally {
    rewinding.value = false
  }
}

// ── 移动端布局：底部行动栏高度写进 CSS 变量，剧情框不再被遮住 ──
const bottomBarEl = ref(null)
let barObserver = null
const measureBars = () => {
  const bottom = bottomBarEl.value?.offsetHeight || 0
  const top = document.querySelector('.top-bar')?.offsetHeight || 0
  const root = document.documentElement
  if (bottom) root.style.setProperty('--bottom-bar-h', bottom + 'px')
  if (top) root.style.setProperty('--top-bar-h', top + 'px')
}
watch(
  () => gameStore.currentSession?.novel,
  (novel) => {
    if (novel) startAmbience(novel)
  },
  { immediate: true }
)

watch(() => gameStore.currentSession?.current_scene, async () => {
  await nextTick()
  measureBars()
  if (barObserver) barObserver.disconnect()
  if (bottomBarEl.value && typeof ResizeObserver !== 'undefined') {
    barObserver = new ResizeObserver(measureBars)
    barObserver.observe(bottomBarEl.value)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (barObserver) barObserver.disconnect()
})

// 今日剩余对话次数（右上角显示）
const quota = ref(null)
const quotaTitle = computed(() => {
  const q = quota.value
  if (!q) return ''
  if (q.is_unlimited) return '包月不限次数'
  if (q.daily_limit == null) return '次数信息暂不可用'
  let t = `今日已用 ${q.used_today}/${q.daily_limit}`
  if (q.extra_quota > 0) t += `，额外配额 ${q.extra_quota} 次`
  if (q.is_guest) t += `（未登录每日 ${q.daily_limit} 次，登录后 ${q.login_limit ?? q.daily_limit} 次）`
  return t
})

const loadQuota = async () => {
  try {
    quota.value = await gameAPI.getQuota()
  } catch (e) {
    // 次数展示失败不影响游戏本身
  }
}

const autoResize = () => {
  const el = actionTextarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

const currentScene = computed(() => gameStore.currentSession?.current_scene)

const missionOpen = ref(false)

// 使命视图：优先用本回合返回的 public 视图，刷新页面时从 session.mission_state 还原
const deriveMission = (ms) => {
  if (!ms || !ms.mission) return null
  const m = ms.mission
  const stages = (m.stages || []).map((st) => st.name || '')
  const idx = ms.stage_index || 0
  return {
    title: m.title || '',
    goal: m.goal || '',
    stakes: m.stakes || '',
    stages,
    stage_index: idx,
    stage_count: stages.length,
    stage_name: stages[idx] || '',
    days_left: ms.days_left ?? ms.deadline_turns ?? 0,
    deadline_turns: ms.deadline_turns || 0,
    status: ms.status || 'active',
    act: ms.act || 1,
    ended: ms.status === 'dead',
    last_label: ms.last_label || '',
    last_note: ms.last_note || '',
  }
}

const actLabel = computed(() => {
  const cn = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
  const n = Number(mission.value?.act || 1)
  return `第${cn[n] || n}幕`
})

const mission = computed(() => {
  const ms = gameStore.currentSession?.mission_state
  // 死亡是终局状态：以会话状态为准，别被上一回合的 scene 快照盖回去
  if (ms && ms.status === 'dead') return deriveMission(ms)
  return currentScene.value?.mission || deriveMission(ms)
})

const worldImageMap = Object.fromEntries(
  Object.keys(WORLD_ART).map((novel) => [
    novel,
    { src: heroOf(novel), thumb: thumbOf(novel), caption: captionOf(novel) }
  ])
)
const currentWorldImage = computed(() => worldImageMap[gameStore.currentSession?.novel])

// 背景图：优先用场景匹配图，无匹配时用世界图
const bgImageStyle = computed(() => {
  // 有匹配的场景图就用场景图；否则用世界 hero，hero 缺失时退回缩略图
  if (currentSceneImage.value) return `url("${currentSceneImage.value}")`
  const novel = gameStore.currentSession?.novel
  if (novel) return bgLayers(novel)
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

onBeforeUnmount(() => {
  stopAmbience(150)
  detachUnlock()
})

onMounted(async () => {
  loadQuota()
  const sessionId = route.params.id

  if (sessionId) {
    try {
      await gameStore.loadExistingSession(Number(sessionId))
    } catch (err) {
      // 会话不存在或已被别人认领：给出口，不要卡在空白页
      error.value = '这个存档加载不了，可能已被删除或不属于当前账号'
      loadFailed.value = true
      return
    }
  } else if (gameStore.currentSession?.id) {
    // 路由里没有 id（旧链接 / 登录回跳）：补进 URL，刷新才能继续
    router.replace(`/game/${gameStore.currentSession.id}`)
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
  loadPlayerAvatar()
  startAmbience(gameStore.currentSession?.novel)
})

const performAction = async (action) => {
  if (gameStore.isGenerating) return

  error.value = ''
  needsLogin.value = false
  isAwaitingOptions.value = true
  streamStatus.value = 'AI正在生成剧情...'

  try {
    // 保留上一段剧情直到新内容到达：中途失败也不会变成空白页
    let firstChunk = false

    const scene = await gameStore.performActionStream(action, {
      onStatus: (status) => {
        streamStatus.value = status.message || streamStatus.value
        if (status.phase === 'metadata') {
          isAwaitingOptions.value = true
        }
      },
      onStoryChunk: (delta) => {
        if (!firstChunk) {
          firstChunk = true
          displayedScene.value = ''
        }
        displayedScene.value += delta
      },
      onScene: (scenePayload) => {
        // 流式文本已通过 onStoryChunk 逐字累积，这里只补图片和状态；
        // 仅在没有任何流式文本时回退为完整 scene_description，避免打字机结束后整段刷新
        if (!displayedScene.value) {
          displayedScene.value = scenePayload.scene_description
        }
        currentSceneImage.value = scenePayload.scene_image || null
        playSfx(
          scenePayload.scene_sfx,
          scenePayload.turn_index ?? (scenePayload.scene_description || '').slice(0, 40)
        )
        for (const ach of scenePayload.mission_achievements || []) {
          const list = gameStore.currentSession.achievements || []
          if (!list.includes(ach)) gameStore.currentSession.achievements = [...list, ach]
        }
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
      const detail = err.response.data.detail || {}
      if (detail.needs_login) {
        // 游客：提示登录
        error.value = detail.message || '今日免费次数已用完，请登录继续'
        needsLogin.value = true
      } else {
        // 已登录：弹窗引导充值，不再用 toast
        error.value = ''
        needsLogin.value = false
        showQuotaModal.value = true
      }
    } else if (err.response?.status === 409 && err.response?.data?.detail?.ended) {
      // 主角已死：不弹错误，直接把终局面板显示出来
      if (gameStore.currentSession?.mission_state) {
        gameStore.currentSession.mission_state = {
          ...gameStore.currentSession.mission_state,
          status: 'dead',
        }
      }
      error.value = ''
    } else {
      const detail = err.response?.data?.detail
      error.value = typeof detail === 'string' ? detail : detail?.message || err.message || '执行行动失败'
    }
  } finally {
    isAwaitingOptions.value = false
    loadQuota()
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

// 回到主界面：进度本来就已存库，这里只离开对局，不弹确认、不清会话
const endingLine = computed(() => {
  const note = mission.value?.last_note
  return note && note.length > 4 ? note : '你倒在了这条路上。故事到这里为止。'
})

const restartSameCharacter = () => {
  const s = gameStore.currentSession
  if (!s) {
    router.push('/character-create')
    return
  }
  router.push({
    path: '/character-create',
    query: { novel: s.novel, name: s.character_name, timeline: s.timeline },
  })
}

const goMyGames = () => {
  router.push(authStore.isAuthenticated ? '/my-games' : { path: '/login', query: { redirect: route.fullPath } })
}

const backToHome = () => {
  showSidebar.value = false
  router.push('/character-create')
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

/* 今日剩余次数 */
.quota-stat {
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(255,255,255,0.12);
  white-space: nowrap;
}
.quota-stat.quota-empty {
  background: rgba(220,80,80,0.28);
  color: #ffd7d7;
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
  display: flex;
  flex-direction: column;
  width: 70vw;
  max-width: 900px;
  height: 55vh;
  max-height: 520px;
  background: linear-gradient(180deg, rgba(8, 8, 18, 0.22), rgba(8, 8, 18, 0.36));
  backdrop-filter: blur(4px) saturate(110%);
  -webkit-backdrop-filter: blur(4px) saturate(110%);
  border: 1px solid rgba(255, 215, 150, 0.15);
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  padding: 24px 28px;
  color: #f0e6d3;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.9), 0 2px 10px rgba(0, 0, 0, 0.8);
}

.story-text {
  /* 用 flex 占满浮层：浮层高度被 max-height 夹住时文字区自动收缩并可滚动，
     不再把整段文字顶出屏幕（移动端曾整块无法滑动） */
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
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
  background: rgba(10, 10, 25, 0.38);
  backdrop-filter: blur(7px) saturate(115%);
  -webkit-backdrop-filter: blur(7px) saturate(115%);
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
/* 次数用完弹窗 */
.quota-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.62);
  backdrop-filter: blur(2px);
}
.quota-modal {
  width: 100%;
  max-width: 340px;
  max-height: 86vh;
  overflow-y: auto;
  padding: 24px 20px 18px;
  text-align: center;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(160deg, #2b2f3a, #1d2029);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.55);
  color: #e8e6e3;
}
.quota-modal-icon { font-size: 2rem; margin-bottom: 6px; }
.quota-modal h3 {
  margin: 0 0 10px;
  font-size: 1.15rem;
  font-weight: 600;
  color: #f5f2ec;
}
.quota-modal-desc {
  margin: 0 0 16px;
  font-size: 0.9rem;
  line-height: 1.85;
  color: #cdc9c3;
  text-wrap: pretty;
}
.quota-modal-qq {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px dashed rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
}
.qq-label { font-size: 0.82rem; color: #a8a49e; }
.qq-number {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 1px;
  color: #ffd479;
  user-select: all;
}
.quota-modal-tip { margin: 0 0 16px; font-size: 0.81rem; line-height: 1.6; color: #a6a29a; }
.quota-modal-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.quota-modal-actions button {
  flex: 1;
  padding: 11px 0;
  border: none;
  border-radius: 10px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.2s, background 0.2s;
}
.btn-pricing { flex: 1 0 100% !important; background: #e8d9a8; color: #1d2029; font-weight: 700; }
.btn-pricing:hover { opacity: 0.92; }
.btn-copy-qq { background: #c9a227; color: #1d2029; font-weight: 600; }
.btn-copy-qq:hover { opacity: 0.9; }
.btn-later { background: rgba(255, 255, 255, 0.1); color: #d5d3cf; }
.btn-later:hover { background: rgba(255, 255, 255, 0.16); }

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

/* ===== 回合回溯面板 ===== */
.turns-modal {
  width: min(92vw, 560px);
  max-height: 84vh;
  display: flex;
  flex-direction: column;
}
.turns-list {
  flex: 1;
  overflow-y: auto;
  margin: 4px 0 14px;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.turn-item {
  text-align: left;
  background: rgba(255, 215, 150, 0.05);
  border: 1px solid rgba(255, 215, 150, 0.18);
  border-radius: 10px;
  padding: 10px 12px;
  color: #e8e2d6;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s ease;
}
.turn-item:hover {
  border-color: rgba(255, 215, 150, 0.42);
  background: rgba(255, 215, 150, 0.1);
}
.turn-selected {
  border-color: #e0b872;
  background: rgba(224, 184, 114, 0.16);
}
.turn-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: #c9a86a;
  margin-bottom: 4px;
}
.turn-points { color: #7fd18b; }
.turn-now {
  margin-left: auto;
  font-size: 0.72rem;
  border: 1px solid rgba(224, 184, 114, 0.5);
  border-radius: 999px;
  padding: 0 8px;
  color: #e0b872;
}
.turn-preview {
  font-size: 0.85rem;
  line-height: 1.55;
  color: #e8e2d6;
}
.turn-choice {
  margin-top: 4px;
  font-size: 0.78rem;
  color: #9a9284;
}
.turns-empty {
  text-align: center;
  color: #8d8678;
  font-size: 0.85rem;
  padding: 18px 0;
}
.turns-note { color: #8d8678; font-size: 0.78rem; }
.quota-modal-actions button:disabled { opacity: 0.45; cursor: not-allowed; }

/* ===== 响应式 ===== */
@media (max-aspect-ratio: 4/3) {
  .story-overlay {
    width: 85vw;
    height: 46vh;
    padding: 16px 18px;
  }
  .has-mission .story-overlay {
    top: auto; /* 交给 bottom 定位，别盖住底部行动区 */
    height: auto;
    max-height: calc(100vh - var(--top-bar-h, 96px) - var(--bottom-bar-h, 170px) - 24px);
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

/* ===== 移动端：剧情框夹在顶栏与行动栏之间，最后一行不会被遮住 ===== */
@media (max-width: 820px) {
  /* .has-mission 那条规则特异性更高，必须一起写上，否则 top:auto 会盖掉这里的
     top/bottom 定位，浮层高度变回内容高度，文字区就滚不动了 */
  .story-overlay,
  .has-mission .story-overlay {
    top: calc(var(--top-bar-h, 52px) + 8px);
    bottom: calc(var(--bottom-bar-h, 170px) + 8px);
    left: 3vw;
    right: 3vw;
    transform: none;
    width: auto;
    max-width: none;
    height: auto;
    max-height: none;
    padding: 14px 14px;
  }
  .story-text {
    font-size: 0.92rem;
    line-height: 1.8;
    letter-spacing: 1px;
  }
  .bottom-bar {
    padding-bottom: calc(12px + env(safe-area-inset-bottom));
  }
  /* 选项按钮：手机上一律整行、允许折行。原来是 nowrap 药丸，长选项把按钮
     撑到屏幕外，文字在最右边被硬切（截图里“也要清…”“顺藤摸瓜…”就是这样） */
  .action-buttons {
    flex-direction: column;
    flex-wrap: nowrap;
  }
  .action-btn {
    width: 100%;
    white-space: normal;
    text-align: left;
    line-height: 1.5;
    letter-spacing: 0.5px;
    padding: 8px 14px;
  }
  .turns-modal { width: 94vw; max-height: 86vh; }
}
/* 有使命条时把剧情面板整体下移，避免压住第一行文字（仅桌面；
   手机端由下面的 bottom 定位规则接管，不能设 top，否则会压到底部行动区） */
@media (min-width: 601px) {
  .has-mission .story-overlay {
    top: calc(50% + 20px);
  }
}

/* ===== 终局面板 ===== */
.ending-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 40%, rgba(20, 12, 10, 0.72), rgba(6, 5, 5, 0.94));
  backdrop-filter: blur(3px);
}
.ending-card {
  width: min(440px, 88vw);
  padding: 34px 30px 26px;
  border-radius: 18px;
  border: 1px solid rgba(214, 178, 108, 0.26);
  background: rgba(16, 13, 12, 0.9);
  color: #e8dfcc;
  text-align: center;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
}
.ending-kicker { margin: 0 0 10px; font-size: 12px; letter-spacing: 6px; color: #8d7f6c; }
.ending-title { margin: 0 0 14px; font-size: 21px; font-weight: 600; color: #f1e3c8; }
.ending-line { margin: 0 0 20px; font-size: 13.5px; line-height: 1.8; color: #b8ac97; }
.ending-stats { display: flex; justify-content: center; gap: 40px; margin-bottom: 22px; }
.ending-stats div { display: flex; flex-direction: column; gap: 4px; }
.es-num { font-size: 22px; color: #d6b26c; }
.es-label { font-size: 11px; color: #857a68; letter-spacing: 1px; }
.ending-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.ending-btn {
  padding: 9px 18px; border-radius: 999px; cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.2); background: transparent; color: #d8cebd; font-size: 13px;
}
.ending-btn.primary { background: rgba(214, 178, 108, 0.18); border-color: rgba(214, 178, 108, 0.6); color: #f3e5c6; }
.ending-hint { margin: 16px 0 0; font-size: 11.5px; color: #6f6657; }

/* ===== 加载失败 ===== */
.load-failed-text {
  max-width: 78vw;
  margin-bottom: 14px;
  color: #e8dcc6;
  line-height: 1.7;
}
.load-failed-actions { display: flex; gap: 10px; justify-content: center; }
.load-failed-btn {
  padding: 8px 18px;
  border-radius: 999px;
  border: 1px solid rgba(214, 178, 108, 0.5);
  background: rgba(214, 178, 108, 0.16);
  color: #f0e2c4;
  font-size: 13px;
  cursor: pointer;
}
.load-failed-btn.ghost {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.24);
  color: #cfc6b6;
}
.sidebar-hint {
  margin: 6px 0 0;
  padding: 0 12px;
  font-size: 11.5px;
  color: rgba(240, 230, 211, 0.45);
  line-height: 1.5;
}

/* ===== 使命条 ===== */
.mission-bar {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: 52px;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: min(680px, 92vw);
  padding: 6px 14px 6px 10px;
  border-radius: 999px;
  background: rgba(18, 16, 14, 0.62);
  border: 1px solid rgba(214, 178, 108, 0.28);
  backdrop-filter: blur(10px);
  color: #e8dfcc;
  font-size: 12.5px;
  line-height: 1;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s, border-color 0.2s;
}
.mission-bar:hover { background: rgba(28, 24, 20, 0.78); border-color: rgba(214, 178, 108, 0.5); }
.mb-mark { color: #d6b26c; font-size: 13px; }
.mb-title { font-weight: 600; letter-spacing: 0.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 34vw; }
.mb-chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(214, 178, 108, 0.12);
  color: #cbb98f;
  font-size: 11.5px;
  white-space: nowrap;
}
.mb-days { color: #c9d6b0; }
.mb-urgent { color: #f0a884; background: rgba(224, 118, 74, 0.16); }
.mb-chip-done { color: #9ed39a; background: rgba(120, 190, 120, 0.16); }
.mb-chip-failed { color: #e59a8a; background: rgba(200, 90, 80, 0.18); }
.mb-last { font-size: 11px; opacity: 0.72; white-space: nowrap; }
.mb-last-推进 { color: #9ed39a; opacity: 1; }
.mb-last-恶化 { color: #e59a8a; opacity: 1; }
.mb-open { border-color: rgba(214, 178, 108, 0.6); }

.mission-panel {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: 92px;
  z-index: 29;
  width: min(520px, 90vw);
  padding: 14px 18px 12px;
  border-radius: 14px;
  background: rgba(16, 14, 12, 0.9);
  border: 1px solid rgba(214, 178, 108, 0.24);
  backdrop-filter: blur(14px);
  color: #ddd3bf;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
}
.mp-goal { margin: 0 0 10px; color: #efe6d2; }
.mp-stages { margin: 0 0 10px; padding: 0; list-style: none; }
.mp-stages li { display: flex; align-items: flex-start; gap: 8px; padding: 3px 0; color: #9d9382; }
.mp-dot {
  flex: 0 0 18px; height: 18px; margin-top: 1px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; border: 1px solid rgba(214, 178, 108, 0.3);
  font-size: 10.5px; color: #b8a67e;
}
.mp-current { color: #efe6d2; }
.mp-current .mp-dot { border-color: #d6b26c; color: #d6b26c; background: rgba(214, 178, 108, 0.14); }
.mp-done { color: #7d8a70; text-decoration: line-through; text-decoration-color: rgba(120, 150, 110, 0.5); }
.mp-done .mp-dot { border-color: rgba(120, 190, 120, 0.5); color: #9ed39a; }
.mp-stakes { margin: 0 0 4px; font-size: 12px; color: #b8a68a; }
.mp-note { margin: 0; font-size: 12px; color: #8e8578; }

@media (max-width: 600px) {
  .mission-bar { top: 46px; font-size: 11.5px; gap: 6px; padding: 5px 10px 5px 8px; max-width: 94vw; }
  .mb-title { max-width: 30vw; }
  .mb-chip { padding: 2px 6px; font-size: 10.5px; }
  .mb-last { display: none; }
  .mission-panel { top: 84px; width: 92vw; padding: 12px 14px 10px; font-size: 12.5px; }
}

/* ===== 玩家头像与角色卡 ===== */
.player-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  margin-right: 10px;
  padding: 0;
  border: 1px solid rgba(255, 215, 150, 0.45);
  border-radius: 50%;
  background: rgba(10, 10, 25, 0.35);
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.18s, border-color 0.18s;
}

.player-chip:hover {
  transform: translateY(-1px);
  border-color: #e8cf9a;
}

.player-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.player-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  color: #f0e6d3;
  background: linear-gradient(135deg, rgba(201, 162, 39, 0.55), rgba(80, 62, 30, 0.65));
}

.profile-modal {
  width: min(460px, 92vw);
  max-height: 84vh;
  overflow-y: auto;
  padding: 22px 22px 18px;
  border: 1px solid rgba(255, 215, 150, 0.35);
  border-radius: 16px;
  background: rgba(14, 14, 26, 0.94);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.6);
  color: #efe6d6;
}

.profile-head {
  display: flex;
  gap: 14px;
  align-items: center;
}

.profile-avatar {
  width: 76px;
  height: 76px;
  border-radius: 12px;
  object-fit: cover;
  border: 1px solid rgba(255, 215, 150, 0.4);
  flex-shrink: 0;
}

.profile-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.8rem;
  color: #f6ecd8;
  background: linear-gradient(135deg, rgba(201, 162, 39, 0.6), rgba(70, 54, 26, 0.8));
}

.profile-title h3 {
  margin: 0 0 4px;
  font-size: 1.2rem;
  letter-spacing: 0.06em;
}

.profile-title p {
  margin: 0;
  font-size: 0.82rem;
  color: #c9bfa8;
}

.profile-timeline {
  margin-top: 2px !important;
  color: #a89f8b !important;
}

.profile-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 18px 0 14px;
}

.profile-stats > div {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  border-radius: 10px;
  background: rgba(255, 215, 150, 0.09);
}

.ps-num {
  font-size: 1.02rem;
  color: #f3e6c6;
}

.ps-label {
  font-size: 0.72rem;
  color: #9c937f;
}

.profile-mission {
  padding: 12px 14px;
  border-left: 3px solid #c9a227;
  border-radius: 8px;
  background: rgba(201, 162, 39, 0.1);
}

.pm-label {
  display: block;
  margin-bottom: 4px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: #c9a227;
}

.profile-mission strong {
  font-size: 0.98rem;
}

.profile-mission p {
  margin: 6px 0 0;
  font-size: 0.84rem;
  line-height: 1.65;
  color: #d6ccb6;
}

.pm-meta {
  color: #9c937f !important;
  font-size: 0.76rem !important;
}

.profile-bg {
  margin-top: 14px;
}

.profile-bg h4 {
  margin: 0 0 6px;
  font-size: 0.82rem;
  color: #c9bfa8;
  font-weight: 500;
}

.profile-bg p {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.75;
  color: #d6ccb6;
}

.profile-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.profile-actions button {
  flex: 1;
  padding: 10px 0;
  border: none;
  border-radius: 10px;
  font-size: 0.88rem;
  cursor: pointer;
}

.btn-relations {
  background: rgba(201, 162, 39, 0.9);
  color: #1d1a12;
  font-weight: 600;
}
</style>
