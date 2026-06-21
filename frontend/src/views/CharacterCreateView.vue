<template>
  <div class="create-immersive">
    <!-- 全屏背景 -->
    <div class="create-bg" :style="{ backgroundImage: `url(${currentWorldImage.src})` }"></div>

    <!-- 登录/注册弹窗 -->
    <AuthModal v-model:visible="showAuthModal" :initial-tab="authModalTab" />

    <!-- 顶部栏 -->
    <div class="top-bar">
      <h1 class="top-title">🎭 角色创建</h1>
      <span class="top-subtitle">{{ form.novel }} · {{ currentWorldImage.caption }}</span>
      <div v-if="!authStore.isAuthenticated" class="top-auth">
        <span class="auth-hint">登录后可保存存档</span>
        <button class="btn btn-primary btn-sm" @click="showAuthModal = true; authModalTab = 'login'">登录</button>
        <button class="btn btn-sm" @click="showAuthModal = true; authModalTab = 'register'">注册</button>
      </div>
    </div>

    <!-- 中央内容区 -->
    <div class="create-content">
      <div class="card-grid">
        <!-- 左侧：角色创建表单 -->
        <div class="glass-card">
          <h2>选择穿越设定</h2>

          <div class="input-group">
            <label>选择小说/历史背景</label>
            <select v-model="form.novel" class="input" @change="onNovelChange">
              <option v-for="n in novelsData" :key="n.novel_id" :value="n.novel_name">{{ n.novel_name }}</option>
            </select>
          </div>

          <div class="input-group">
            <label>选择时间节点</label>
            <select v-model="form.timeline" class="input">
              <option v-for="timeline in timelines" :key="timeline" :value="timeline">
                {{ timeline }}
              </option>
            </select>
          </div>

          <div class="input-group">
            <label>角色类型</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" v-model="characterType" value="preset" />
                选择已有角色
              </label>
              <label class="radio-label">
                <input type="radio" v-model="characterType" value="custom" />
                创建自定义角色
              </label>
            </div>
          </div>

          <!-- 预设角色选择 -->
          <div v-if="characterType === 'preset'" class="input-group">
            <label>选择角色</label>
            <select v-model="selectedPresetCharacter" class="input" @change="onPresetCharacterChange">
              <option value="">请选择...</option>
              <option v-for="char in presetCharacters" :key="char" :value="char">
                {{ char }}
              </option>
            </select>
          </div>

          <!-- 自定义角色 -->
          <div v-if="characterType === 'custom'">
            <div class="input-group">
              <label>角色姓名</label>
              <input v-model="form.name" type="text" class="input" placeholder="输入角色姓名" />
            </div>

            <div class="grid grid-2">
              <div class="input-group">
                <label>性别</label>
                <select v-model="form.gender" class="input">
                  <option>男性</option>
                  <option>女性</option>
                </select>
              </div>

              <div class="input-group">
                <label>年龄</label>
                <input v-model.number="form.age" type="number" class="input" min="18" />
              </div>
            </div>

            <div class="input-group">
              <label>初始身份</label>
              <select v-model="form.rank" class="input">
                <option>将军</option>
                <option>军师</option>
                <option>士兵</option>
                <option>读书人</option>
                <option>文官</option>
                <option>小吏</option>
                <option>商人</option>
                <option>未知</option>
              </select>
            </div>

            <div class="input-group">
              <label>角色背景（可选）</label>
              <textarea v-model="form.background" class="input" rows="4" placeholder="描述角色的背景故事..."></textarea>
            </div>
          </div>

          <div v-if="error" class="error-message">{{ error }}</div>

          <button @click="startGame" class="btn btn-primary btn-block btn-start" :disabled="loading">
            {{ loading ? '⏳ 穿越中...' : '🚀 开始穿越' }}
          </button>
        </div>

        <!-- 右侧：角色预览 -->
        <div class="glass-card">
          <h2>角色预览</h2>
          <div v-if="previewCharacter" class="character-preview">
            <div class="preview-item">
              <span class="label">姓名</span>
              <span class="value">{{ previewCharacter.name }}</span>
            </div>
            <div class="preview-item">
              <span class="label">性别</span>
              <span class="value">{{ previewCharacter.gender }}</span>
            </div>
            <div class="preview-item">
              <span class="label">年龄</span>
              <span class="value">{{ previewCharacter.age }}岁</span>
            </div>
            <div class="preview-item">
              <span class="label">身份</span>
              <span class="value">{{ previewCharacter.rank }}</span>
            </div>
            <div class="preview-item">
              <span class="label">世界</span>
              <span class="value">{{ form.novel }}</span>
            </div>
            <div class="preview-item">
              <span class="label">时间</span>
              <span class="value">{{ form.timeline }}</span>
            </div>
            <div class="preview-item">
              <span class="label">初始积分</span>
              <span class="value preview-points">{{ previewCharacter.starting_points }}</span>
            </div>
            <div v-if="previewCharacter.background" class="preview-item preview-bg">
              <span class="label">背景</span>
              <p class="value">{{ previewCharacter.background }}</p>
            </div>
            <div class="preview-badge">
              <span v-if="characterType === 'preset'" class="badge badge-success">🎭 经典角色</span>
              <span v-else class="badge">✨ 自定义角色</span>
            </div>
          </div>
          <div v-else class="preview-empty">
            <span class="empty-icon">📋</span>
            <span>请选择或创建角色</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import { gameAPI } from '@/api'
import AuthModal from '@/components/AuthModal.vue'
import sanguoImage from '../../../images/sanguo.png'
import shuihuImage from '../../../images/shuihu.png'
import mingdaiImage from '../../../images/mingdai.png'
import hongloumengImage from '../../../images/hongloumeng.png'
import xiyouImage from '../../../images/xiyou.png'

const router = useRouter()
const gameStore = useGameStore()
const authStore = useAuthStore()

const showAuthModal = ref(false)
const authModalTab = ref('login')

const characterType = ref('preset')
const selectedPresetCharacter = ref('')
const loading = ref(false)
const error = ref('')
const availableCharacters = ref({}) // 从API获取的角色-时间节点映射

const form = ref({
  novel: '三国演义',
  timeline: '赤壁之战',
  name: '',
  gender: '男性',
  age: 25,
  rank: '未知',
  background: '',
  starting_points: 0
})

// 动态小说/时间节点数据（从 API 加载）
const novelsData = ref([])

// 硬编码兜底（API 不可用时使用）
const FALLBACK_NOVELS = {
  '三国演义': ['黄巾起义', '董卓乱政', '官渡之战', '赤壁之战', '三国鼎立', '北伐中原'],
  '水浒传': ['洪太尉访道', '梁山聚义', '攻打祝家庄', '招安之路', '征讨方腊', '卸甲还乡'],
  '明代': ['洪武之治', '靖难之役', '永乐盛世', '土木堡之变', '万历乱局', '女真崛起', '闯王进京'],
  '清代': ['八旗入关', '康熙继位', '九子夺嫡', '马戛尔尼访华', '虎门销烟', '金田起义', '第二次中英战争', '洋务运动', '甲午战争', '八国联军进京', '预备立宪'],
  '西游记': ['大闹天宫', '五行山下', '西天取经', '三打白骨精', '女儿国', '真假美猴王', '火焰山', '取得真经']
}

// 从API加载的角色详情缓存
const presetCharacterCache = ref({})

const worldImageMap = {
  '三国演义': {
    src: sanguoImage,
    caption: '赤壁风起，天下三分'
  },
  '水浒传': {
    src: shuihuImage,
    caption: '梁山泊上，聚义听潮'
  },
  '明代': {
    src: mingdaiImage,
    caption: '宫阙深处，风云暗涌'
  },
  '清代': {
    src: hongloumengImage,
    caption: '盛世帘影，旧梦将醒'
  },
  '西游记': {
    src: xiyouImage,
    caption: '西行路上，妖雾重重'
  }
}

const timelines = computed(() => {
  const n = novelsData.value.find(n => n.novel_name === form.value.novel)
  if (n && n.timelines.length > 0) return n.timelines
  return FALLBACK_NOVELS[form.value.novel] || []
})

// 根据当前小说和时间节点筛选可用角色
const presetCharacters = computed(() => {
  const novelData = availableCharacters.value[form.value.novel]
  if (!novelData) return []
  // 返回当前时间节点可用的角色
  return novelData[form.value.timeline] || []
})

const currentWorldImage = computed(() => worldImageMap[form.value.novel] || worldImageMap['三国演义'])
const selectedPresetInfo = computed(() => {
  const cacheKey = `${form.value.novel}/${selectedPresetCharacter.value}`
  const presetInfo = presetCharacterCache.value[cacheKey]
  if (!presetInfo) return null
  return { ...presetInfo, novel: form.value.novel, timeline: form.value.timeline, character_type: 'preset' }
})

const previewCharacter = computed(() => {
  if (characterType.value === 'custom') {
    return form.value.name ? form.value : null
  } else if (selectedPresetInfo.value) {
    return selectedPresetInfo.value
  }
  return null
})

const onNovelChange = () => {
  form.value.timeline = timelines.value[0] || ''
  selectedPresetCharacter.value = ''
  if (characterType.value === 'preset') {
    form.value.name = ''
    form.value.starting_points = 0
  }
  loadCharacters()
}

// 从API加载角色-时间节点映射
const loadCharacters = async () => {
  try {
    const data = await gameAPI.getCharacters({ novel: form.value.novel })
    availableCharacters.value = data
  } catch (err) {
    console.error('加载角色列表失败:', err)
  }
}

onMounted(async () => {
  // 加载动态小说/时间节点数据
  try {
    const data = await gameAPI.getNovels()
    if (data && data.length > 0) {
      novelsData.value = data
      form.value.novel = data[0].novel_name
    }
  } catch (err) {
    console.warn('加载小说列表失败，使用硬编码兜底:', err)
  }
  await loadCharacters()
})

const onPresetCharacterChange = async () => {
  if (!selectedPresetCharacter.value) return
  const cacheKey = `${form.value.novel}/${selectedPresetCharacter.value}`
  if (presetCharacterCache.value[cacheKey]) {
    applyPresetToForm(presetCharacterCache.value[cacheKey])
    return
  }
  try {
    const detail = await gameAPI.getCharacterDetail(form.value.novel, selectedPresetCharacter.value, form.value.timeline)
    presetCharacterCache.value[cacheKey] = detail
    applyPresetToForm(detail)
  } catch (err) {
    console.error('获取角色详情失败:', err)
  }
}

const applyPresetToForm = (detail) => {
  form.value.name = detail.name
  form.value.gender = detail.gender
  form.value.age = detail.age
  form.value.rank = detail.rank
  form.value.background = detail.background || ''
  form.value.starting_points = detail.starting_points
}

watch(characterType, () => {
  if (characterType.value === 'custom') {
    form.value.name = ''
    form.value.age = 20
    form.value.rank = '未知'
    form.value.background = ''
    form.value.starting_points = 0
  } else {
    onPresetCharacterChange()
  }
})

const formatApiError = (err) => {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) {
    const ageError = detail.find(item => item.loc?.includes('age'))
    if (ageError) return '年龄请输入 18 岁以上的数字'
    return detail.map(item => item.msg).join('；')
  }
  return typeof detail === 'string' ? detail : detail?.message || '创建游戏会话失败'
}

const startGame = async () => {
  error.value = ''

  if (!form.value.name) {
    error.value = '请输入角色姓名或选择预设角色'
    return
  }

  const age = characterType.value === 'preset' && selectedPresetInfo.value
    ? Number(selectedPresetInfo.value.age)
    : Number(form.value.age)
  if (!Number.isFinite(age) || age < 18) {
    error.value = '年龄请输入 18 岁以上的数字'
    return
  }

  loading.value = true

  try {
    const characterSource = characterType.value === 'preset' && selectedPresetInfo.value
      ? selectedPresetInfo.value
      : form.value
    const characterData = {
      name: characterSource.name,
      gender: characterSource.gender,
      age,
      rank: characterSource.rank,
      background: characterSource.background || '',
      novel: form.value.novel,
      timeline: form.value.timeline,
      character_type: characterType.value,
      starting_points: characterSource.starting_points
    }

    await gameStore.createGameSession(characterData)
    router.push('/game')
  } catch (err) {
    error.value = formatApiError(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ===== 全屏沉浸布局 ===== */
.create-immersive {
  position: fixed;
  inset: 0;
  overflow: hidden;
  color: #f0e6d3;
}

/* 背景图 */
.create-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  z-index: 0;
}

.create-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

/* ===== 顶部栏 ===== */
.top-bar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 16px 28px;
  background: linear-gradient(180deg, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0) 100%);
}

.top-title {
  font-size: 1.3rem;
  margin: 0;
  color: #f0e6d3;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6);
  white-space: nowrap;
}

.top-subtitle {
  font-size: 0.9rem;
  color: rgba(255,215,150,0.8);
  text-shadow: 0 1px 4px rgba(0,0,0,0.5);
}

.top-auth {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-left: auto;
}

.auth-hint {
  font-size: 0.82rem;
  color: rgba(255,255,255,0.6);
}

/* ===== 中央内容区 ===== */
.create-content {
  position: relative;
  z-index: 5;
  height: calc(100vh - 76px);
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.card-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  width: 100%;
  max-width: 1000px;
}

/* ===== 玻璃卡片 ===== */
.glass-card {
  background: rgba(10, 10, 25, 0.2);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 215, 150, 0.12);
  border-radius: 14px;
  padding: 24px 28px;
  color: #f0e6d3;
  text-shadow: 0 1px 4px rgba(0,0,0,0.6);
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

.glass-card h2 {
  margin: 0 0 16px;
  font-size: 1.15rem;
  color: rgba(255,215,150,0.9);
  border-bottom: 1px solid rgba(255,215,150,0.15);
  padding-bottom: 10px;
}

/* ===== 表单元素 ===== */
.input-group {
  margin-bottom: 14px;
}

.input-group label {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 5px;
  color: rgba(255,255,255,0.75);
}

.input, select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255,215,150,0.2);
  background: rgba(0,0,0,0.35);
  color: #f0e6d3;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.input:focus, select:focus {
  border-color: rgba(255,215,150,0.5);
}

select option {
  background: #1a1a2e;
  color: #f0e6d3;
}

.input::placeholder {
  color: rgba(255,255,255,0.35);
}

textarea.input {
  resize: vertical;
  font-family: inherit;
}

.radio-group {
  display: flex;
  gap: 1.5rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.9rem;
}

/* ===== 按钮 ===== */
.btn-start {
  margin-top: 8px;
  padding: 12px;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* ===== 角色预览 ===== */
.character-preview {
  padding: 0;
}

.preview-item {
  display: flex;
  padding: 0.7rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.preview-item:last-child {
  border-bottom: none;
}

.preview-item .label {
  font-weight: 600;
  min-width: 80px;
  color: rgba(255,215,150,0.8);
  font-size: 0.88rem;
}

.preview-item .value {
  flex: 1;
  color: #f0e6d3;
  font-size: 0.92rem;
}

.preview-points {
  color: #f0c040 !important;
  font-weight: 700;
}

.preview-bg {
  flex-direction: column;
}

.preview-bg .label {
  margin-bottom: 4px;
}

.preview-badge {
  margin-top: 1rem;
  text-align: center;
}

.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: rgba(255,255,255,0.4);
  gap: 0.5rem;
}

.empty-icon {
  font-size: 2rem;
}

/* ===== 错误信息 ===== */
.error-message {
  padding: 0.7rem 1rem;
  background: rgba(248, 113, 113, 0.2);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: #fca5a5;
  border-radius: 8px;
  margin-bottom: 1rem;
  text-align: center;
  font-size: 0.88rem;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .top-bar {
    padding: 12px 16px;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .top-title {
    font-size: 1.1rem;
  }

  .top-subtitle {
    font-size: 0.78rem;
    width: 100%;
    order: 3;
  }

  .top-auth {
    margin-left: 0;
  }

  .create-content {
    height: calc(100vh - 100px);
    align-items: flex-start;
    padding: 12px;
  }

  .card-grid {
    grid-template-columns: 1fr;
    gap: 16px;
    max-width: 100%;
  }

  .glass-card {
    padding: 18px 16px;
  }
}

@media (min-width: 1400px) {
  .card-grid {
    max-width: 1200px;
  }
}
</style>
