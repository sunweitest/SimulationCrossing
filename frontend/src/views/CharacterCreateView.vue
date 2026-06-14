<template>
  <div class="container">
    <!-- 认证栏 -->
    <div v-if="!authStore.isAuthenticated" class="auth-bar">
      <span class="auth-hint">登录后可查看和管理游戏存档</span>
      <div class="auth-buttons">
        <button class="btn btn-primary btn-sm" @click="showAuthModal = true; authModalTab = 'login'">登录</button>
        <button class="btn btn-sm" @click="showAuthModal = true; authModalTab = 'register'">注册</button>
      </div>
    </div>

    <h1>🎭 角色创建</h1>

    <!-- 登录/注册弹窗 -->
    <AuthModal v-model:visible="showAuthModal" :initial-tab="authModalTab" />

    <section class="world-visual" :style="{ backgroundImage: `url(${currentWorldImage.src})` }">
      <div class="world-visual-overlay">
        <span>{{ form.novel }}</span>
        <strong>{{ currentWorldImage.caption }}</strong>
      </div>
    </section>

    <div class="grid grid-2">
      <!-- 左侧：角色创建表单 -->
      <div class="card">
        <h2>选择穿越设定</h2>

        <div class="input-group">
          <label>选择小说/历史背景</label>
          <select v-model="form.novel" class="input" @change="onNovelChange">
            <option value="三国演义">三国演义</option>
            <option value="水浒传">水浒传</option>
            <option value="明代">明代</option>
            <option value="清代">清代</option>
            <option value="西游记">西游记</option>
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

        <button @click="startGame" class="btn btn-primary btn-block" :disabled="loading">
          {{ loading ? '穿越中...' : '开始穿越' }}
        </button>
      </div>

      <!-- 右侧：角色预览 -->
      <div class="card">
        <h2>角色预览</h2>
        <div v-if="previewCharacter" class="character-preview">
          <div class="preview-item">
            <span class="label">姓名:</span>
            <span class="value">{{ previewCharacter.name }}</span>
          </div>
          <div class="preview-item">
            <span class="label">性别:</span>
            <span class="value">{{ previewCharacter.gender }}</span>
          </div>
          <div class="preview-item">
            <span class="label">年龄:</span>
            <span class="value">{{ previewCharacter.age }}岁</span>
          </div>
          <div class="preview-item">
            <span class="label">身份:</span>
            <span class="value">{{ previewCharacter.rank }}</span>
          </div>
          <div class="preview-item">
            <span class="label">世界:</span>
            <span class="value">{{ form.novel }}</span>
          </div>
          <div class="preview-item">
            <span class="label">时间:</span>
            <span class="value">{{ form.timeline }}</span>
          </div>
          <div class="preview-item">
            <span class="label">初始积分:</span>
            <span class="value badge badge-warning">{{ previewCharacter.starting_points }}</span>
          </div>
          <div v-if="previewCharacter.background" class="preview-item">
            <span class="label">背景:</span>
            <p class="value">{{ previewCharacter.background }}</p>
          </div>
          <div class="preview-badge">
            <span v-if="characterType === 'preset'" class="badge badge-success">🎭 经典角色</span>
            <span v-else class="badge">✨ 自定义角色</span>
          </div>
        </div>
        <div v-else class="text-center text-muted">
          请选择或创建角色
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

// 时间节点映射
const timelineMap = {
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

const timelines = computed(() => timelineMap[form.value.novel] || [])

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

onMounted(() => {
  loadCharacters()
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
/* 认证栏 */
.auth-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 0.75rem 1.25rem;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 0.9rem;
}

.auth-hint {
  color: var(--text-light);
}

.auth-buttons {
  display: flex;
  gap: 0.5rem;
}

.world-visual {
  min-height: 260px;
  margin-bottom: 2rem;
  border-radius: 8px;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: flex-end;
}

.world-visual-overlay {
  width: 100%;
  padding: 2rem;
  color: white;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0), rgba(18, 18, 18, 0.78));
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
}

.world-visual-overlay span {
  display: block;
  font-size: 1rem;
  margin-bottom: 0.35rem;
}

.world-visual-overlay strong {
  display: block;
  font-size: 1.75rem;
  line-height: 1.25;
}

.radio-group {
  display: flex;
  gap: 1.5rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.character-preview {
  padding: 1rem;
}

.preview-item {
  display: flex;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-color);
}

.preview-item:last-child {
  border-bottom: none;
}

.preview-item .label {
  font-weight: 600;
  min-width: 100px;
  color: var(--text-color);
}

.preview-item .value {
  flex: 1;
  color: var(--text-light);
}

.preview-badge {
  margin-top: 1rem;
  text-align: center;
}

.error-message {
  padding: 0.75rem;
  background: var(--error-color);
  color: white;
  border-radius: 8px;
  margin-bottom: 1rem;
  text-align: center;
}

textarea.input {
  resize: vertical;
  font-family: inherit;
}

@media (max-width: 768px) {
  .world-visual {
    min-height: 190px;
  }

  .world-visual-overlay {
    padding: 1.25rem;
  }

  .world-visual-overlay strong {
    font-size: 1.3rem;
  }
}
</style>
