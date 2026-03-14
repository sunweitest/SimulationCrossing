<template>
  <div class="container">
    <h1>🎭 角色创建</h1>

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
              <input v-model.number="form.age" type="number" class="input" min="18" max="60" />
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
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/game'

const router = useRouter()
const gameStore = useGameStore()

const characterType = ref('preset')
const selectedPresetCharacter = ref('')
const loading = ref(false)
const error = ref('')

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
  '清代': ['八旗入关', '康熙继位', '九子夺嫡', '马戛尔尼访华', '虎门销烟', '金田起义', '第二次中英战争', '洋务运动', '甲午战争', '八国联军进京', '预备立宪']
}

// 预设角色映射（简化版）
const presetCharactersMap = {
  '三国演义': ['诸葛亮', '赵云', '曹操'],
  '水浒传': ['宋江'],
  '明代': ['朱元璋'],
  '清代': ['康熙']
}

const timelines = computed(() => timelineMap[form.value.novel] || [])
const presetCharacters = computed(() => presetCharactersMap[form.value.novel] || [])

const previewCharacter = computed(() => {
  if (characterType.value === 'custom') {
    return form.value.name ? form.value : null
  } else if (selectedPresetCharacter.value) {
    return {
      name: selectedPresetCharacter.value,
      ...form.value,
      starting_points: 60 // 预设角色默认积分
    }
  }
  return null
})

const onNovelChange = () => {
  form.value.timeline = timelines.value[0] || ''
  selectedPresetCharacter.value = ''
}

const onPresetCharacterChange = () => {
  if (selectedPresetCharacter.value) {
    form.value.name = selectedPresetCharacter.value
    form.value.starting_points = 60
  }
}

watch(characterType, () => {
  if (characterType.value === 'custom') {
    form.value.name = ''
    form.value.starting_points = 0
  }
})

const startGame = async () => {
  error.value = ''

  if (!form.value.name) {
    error.value = '请输入角色姓名或选择预设角色'
    return
  }

  loading.value = true

  try {
    const characterData = {
      name: form.value.name,
      gender: form.value.gender,
      age: form.value.age,
      rank: form.value.rank,
      background: form.value.background || '',
      novel: form.value.novel,
      timeline: form.value.timeline,
      character_type: characterType.value,
      starting_points: form.value.starting_points
    }

    await gameStore.createGameSession(characterData)
    router.push('/game')
  } catch (err) {
    error.value = err.response?.data?.detail || '创建游戏会话失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
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
</style>
