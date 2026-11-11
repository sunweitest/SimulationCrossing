<template>
  <div class="create-immersive">
    <!-- 全屏背景 -->
    <div
      class="create-bg"
      :class="{ 'bg-thumb': step === 'world' }"
      :style="{ backgroundImage: `url(${displayWorldImage.src})` }"
    ></div>

    <!-- 登录/注册弹窗 -->
    <AuthModal v-model:visible="showAuthModal" :initial-tab="authModalTab" />

    <!-- 顶部栏 -->
    <div class="top-bar">
      <h1 class="top-title">🎭 角色创建</h1>
      <span class="top-subtitle">{{ form.novel }} · {{ currentWorldImage.caption }}</span>
      <div v-if="authStore.isAuthenticated" class="top-auth">
        <router-link to="/ladder" class="top-link">🏆 天梯</router-link>
        <router-link to="/my-games" class="top-link">📋 我的游戏</router-link>
        <span class="top-user">{{ authStore.user?.email || authStore.user?.phone || '已登录' }}</span>
        <button class="btn btn-sm" @click="handleLogout">退出</button>
      </div>
      <div v-else class="top-auth">
        <span class="auth-hint">登录后可保存存档</span>
        <button class="btn btn-primary btn-sm" @click="showAuthModal = true; authModalTab = 'login'">登录</button>
        <button class="btn btn-sm" @click="showAuthModal = true; authModalTab = 'register'">注册</button>
      </div>
    </div>

    <!-- 中央内容区 -->
    <div class="create-content" :class="{ 'is-world-step': step === 'world' }">
      <!-- ===== 第一步：选择世界（卡片网格） ===== -->
      <div v-if="step === 'world'" class="world-step">
        <div class="world-step-head">
          <h2>选择你的穿越世界</h2>
          <p>共 {{ worldCards.length }} 个世界 · 点击「开始穿越」进入角色选择</p>
        </div>

        <div class="world-grid">
          <div
            v-for="w in worldCards"
            :key="w.novel"
            class="world-card"
            :class="{ active: hoverNovel === w.novel }"
            role="button"
            tabindex="0"
            @mouseenter="hoverNovel = w.novel"
            @mouseleave="hoverNovel = ''"
            @focus="hoverNovel = w.novel"
            @blur="hoverNovel = ''"
            @keydown.enter.prevent="selectWorld(w.novel)"
            @keydown.space.prevent="selectWorld(w.novel)"
          >
            <div class="world-cover" :style="{ backgroundImage: `url(${w.cover})` }">
              <span v-if="w.badge" class="world-badge">{{ w.badge }}</span>
            </div>
            <div class="world-info">
              <h3>{{ w.novel }}</h3>
              <p class="world-caption">{{ w.caption }}</p>
              <button class="world-start" @click.stop="selectWorld(w.novel)">开始穿越 →</button>
            </div>
          </div>
        </div>

        <!-- 想看哪个世界：投票 -->
        <div class="vote-panel">
          <div class="vote-head">
            <h3>🗳 下一个世界做什么？</h3>
            <span>共 {{ voteTotal }} 票 · 点一下投票，再点取消</span>
          </div>
          <div class="vote-chips">
            <button
              v-for="c in voteCandidates"
              :key="c.name"
              class="vote-chip"
              :class="{ voted: c.voted }"
              @click="toggleVote(c)"
            >
              <strong>{{ c.name }}</strong>
              <span class="vote-count">{{ c.votes }}</span>
              <span class="vote-hint">{{ c.hint }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- ===== 第二步：先选角色，再选时间节点 ===== -->
      <div v-else class="card-grid">
        <!-- 左侧：角色 → 时间 -->
        <div class="glass-card">
          <div class="selected-world">
            <div class="selected-world-cover" :style="{ backgroundImage: `url(${currentWorldImage.thumb})` }"></div>
            <div class="selected-world-meta">
              <span class="selected-world-name">{{ form.novel }}</span>
              <span class="selected-world-caption">{{ currentWorldImage.caption }}</span>
            </div>
            <button class="change-world" @click="backToWorlds">↺ 换世界</button>
          </div>

          <!-- 2A：选角色 -->
          <template v-if="!selectedChar">
            <h2>选择你要成为的人</h2>
            <p class="step-hint">
              共 {{ worldCharacters.length }} 个角色 · 带「小人物」标记的往往更难，也更像我们自己的日子
            </p>

            <div v-if="authStore.isAuthenticated && myCharacters.length" class="my-chars">
              <p class="my-chars-title">我的角色 · 只有你能看见</p>
              <div class="my-chars-row">
                <div v-for="mc in myCharacters" :key="mc.id" class="my-char">
                  <button class="my-char-main" @click="selectMyCharacter(mc)">
                    <strong>{{ mc.name }}</strong>
                    <span>{{ mc.rank || '未知' }} · {{ mc.age }}岁</span>
                  </button>
                  <button class="my-char-act" title="修改" @click.stop="editMyCharacter(mc)">✎</button>
                  <button class="my-char-act danger" title="删除" @click.stop="deleteMyCharacter(mc)">✕</button>
                </div>
              </div>
            </div>

            <div v-if="charLoading" class="char-loading">
              <div class="spinner"></div>
              <span>正在唤醒这个世界的人…</span>
            </div>

            <div v-else class="char-grid">
              <button
                v-for="c in worldCharacters"
                :key="c.name"
                class="char-card"
                :class="{ 'is-minor': c.is_minor }"
                @click="chooseCharacter(c)"
              >
                <div
                  class="char-portrait"
                  :style="c.image ? { backgroundImage: `url(${c.image})` } : {}"
                >
                  <span v-if="!c.image" class="char-initial">{{ c.name.slice(0, 1) }}</span>
                  <span v-if="c.is_minor" class="char-flag">小人物</span>
                </div>
                <div class="char-meta">
                  <strong>{{ c.name }}</strong>
                  <span class="char-rank">{{ c.rank }}</span>
                  <span class="char-sub">{{ c.gender }} · {{ c.age }}岁 · {{ c.timelines.length }} 个时间点</span>
                </div>
              </button>

              <button class="char-card char-card-custom" @click="chooseCustom">
                <div class="char-portrait char-portrait-custom"><span class="char-plus">＋</span></div>
                <div class="char-meta">
                  <strong>自定义角色</strong>
                  <span class="char-rank">自己定姓名与身份</span>
                </div>
              </button>
            </div>
          </template>

          <!-- 2B：选时间节点 -->
          <template v-else>
            <button class="char-back" @click="backToCharacters">← 重选角色</button>
            <h2>
              {{ characterType === 'custom' ? '自定义角色' : charDisplay?.name + ' · 选择时间节点' }}
            </h2>

            <!-- 自定义角色表单 -->
            <template v-if="characterType === 'custom'">
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
                  <option v-if="form.rank && !standardRanks.includes(form.rank)" :value="form.rank">{{ form.rank }}</option>
                  <optgroup label="皇族贵胄">
                    <option>皇帝</option><option>皇后</option><option>太子</option>
                    <option>皇子</option><option>公主</option><option>王爷</option>
                    <option>王妃</option><option>贵妃</option>
                  </optgroup>
                  <optgroup label="将相官吏">
                    <option>将军</option><option>军师</option><option>士兵</option>
                    <option>文官</option><option>小吏</option><option>太监</option>
                  </optgroup>
                  <optgroup label="江湖民间">
                    <option>侠客</option><option>读书人</option><option>商人</option>
                    <option>大小姐</option><option>平民</option><option>宫女</option>
                    <option>道士</option><option>僧人</option><option>郎中</option>
                  </optgroup>
                  <optgroup label="其他"><option>未知</option></optgroup>
                </select>
              </div>

              <div class="input-group">
                <label>角色背景（可选）</label>
                <textarea v-model="form.background" class="input" rows="3" placeholder="描述角色的背景故事..."></textarea>
              </div>
            </template>

            <!-- 时间节点（预设角色只列这个人真正在场的节点） -->
            <div class="input-group">
              <label>从哪个时刻开始</label>
              <div class="tl-list">
                <button
                  v-for="t in charTimelines"
                  :key="t.name"
                  class="tl-card"
                  :class="{ active: form.timeline === t.name }"
                  @click="form.timeline = t.name"
                >
                  <strong>{{ t.name }}</strong>
                  <span>{{ t.background }}</span>
                </button>
              </div>
            </div>
          </template>

          <div v-if="error" class="error-message">{{ error }}</div>

          <button
            @click="startGame"
            class="btn btn-primary btn-block btn-start"
            :disabled="loading || (!selectedChar && characterType !== 'custom')"
          >
            {{ loading ? '⏳ 穿越中...' : '🚀 开始穿越' }}
          </button>
        </div>

        <!-- 右侧：预览 -->
        <div class="glass-card">
          <h2>角色预览</h2>
          <div v-if="previewCharacter" class="character-preview">
            <div
              v-if="previewCharacter.image"
              class="preview-portrait"
              :style="{ backgroundImage: `url(${previewCharacter.image})` }"
            ></div>
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
              <span v-if="previewCharacter.is_minor" class="badge badge-minor">小人物</span>
            </div>
          </div>
          <div v-else class="preview-empty">
            <span class="empty-icon">📋</span>
            <span>先在上方选一个人</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部链接 -->
    <div class="create-footer">
      <a href="tencent://message/?uin=1306344250" class="footer-btn footer-btn-feedback">
        💬 联系作者反馈
        <span class="footer-qq">QQ: 1306344250</span>
      </a>
      <a href="https://github.com/sunweitest/SimulationCrossing" target="_blank" class="footer-btn footer-btn-github">
        ⭐ Git仓库欢迎贡献代码
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import { gameAPI, communityAPI, customCharacterAPI } from '@/api'
import AuthModal from '@/components/AuthModal.vue'
import sanguoImage from '../../../images/sanguo.png'
import shuihuImage from '../../../images/shuihu.png'
import mingdaiImage from '../../../images/mingdai.png'
import hongloumengImage from '../../../images/hongloumeng.png'
import qingdaiImage from '../../../images/qingdai.png'
import xiyouImage from '../../../images/xiyou.png'
import jinpingmeiImage from '../../../images/jinpingmei.png'
import wastelandImage from '../../../images/wasteland.png'
import fengshenImage from '../../../images/fengshen.png'
import wuxiaImage from '../../../images/wuxia.png'
import xianxiaImage from '../../../images/xianxia.png'
import datangImage from '../../../images/datang.png'
import bianjingImage from '../../../images/bianjing.png'
import urbanImage from '../../../images/urban.png'
import dailyImage from '../../../images/daily.png'

const router = useRouter()
const route = useRoute()
const gameStore = useGameStore()
const authStore = useAuthStore()

const showAuthModal = ref(false)
const authModalTab = ref('login')

const step = ref('world') // 'world' 选世界 | 'character' 选角色/剧情
const hoverNovel = ref('')
const characterType = ref('preset')
const selectedPresetCharacter = ref('')
const loading = ref(false)
const error = ref('')
const worldCharacters = ref([])   // 当前世界的全部角色（含小人物）
const charLoading = ref(false)
const selectedChar = ref(null)    // 选中的角色对象；自定义时为 { custom: true }
const voteCandidates = ref([])
const voteTotal = ref(0)
const availableCharacters = ref({}) // 从API获取的角色-时间节点映射
const standardRanks = ['皇帝','皇后','太子','皇子','公主','王爷','王妃','贵妃','将军','军师','士兵','文官','小吏','太监','侠客','读书人','商人','大小姐','平民','宫女','道士','僧人','郎中','未知']
const myCharacters = ref([])        // 当前世界里我自己的自定义角色
const editingCustomId = ref(null)   // 正在修改的自定义角色 id（null = 新建）

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
  '西游记': ['大闹天宫', '五行山下', '西天取经', '三打白骨精', '女儿国', '真假美猴王', '火焰山', '取得真经'],
  '金瓶梅': ['结拜发迹', '王婆说风情', '毒杀武大', '娶李瓶儿', '生子鼎盛', '妻妾争宠', '暴毙家败', '妻妾散场'],
  '废土末世': ['灾变降临', '秩序崩坏', '废土求生', '势力割据', '文明余烬'],
  '红楼梦': ['元妃省亲', '大观园结社', '抄检大观园', '荣府抄家', '白茫茫大地'],
  '封神演义': ['女娲宫题诗', '妲己入宫', '黄飞虎反五关', '闻仲伐西岐', '牧野之战'],
  '武侠江湖': ['初入江湖', '武林大会', '魔教东来', '名剑之争', '江湖落幕', '青龙夜宴'],
  '仙侠修真': ['拜入山门', '筑基试炼', '宗门大比', '正魔之争', '飞升雷劫'],
  '大唐长安·天宝末年': ['天宝盛世', '谪仙入宫', '渔阳鼙鼓', '马嵬之变', '长安收复'],
  '北宋汴京之变': ['宣和盛世', '花石纲', '金兵南下', '靖康之变', '南渡'],
  '都市修真': ['灵气初醒', '写字楼修行', '城隍庙拆迁', '地脉之争', '天劫将至'],
  '日常生活': ['周一早高峰', '项目上线前夜', '开店第一年', '年底考核', '春节回家']
}

// 从API加载的角色详情缓存
const presetCharacterCache = ref({})

const worldImageMap = {
  '三国演义': {
    src: sanguoImage,
    thumb: '/images/covers/sanguo.webp',
    caption: '赤壁风起，天下三分'
  },
  '水浒传': {
    src: shuihuImage,
    thumb: '/images/covers/shuihu.webp',
    caption: '梁山泊上，聚义听潮'
  },
  '明代': {
    src: mingdaiImage,
    thumb: '/images/covers/mingdai.webp',
    caption: '宫阙深处，风云暗涌'
  },
  '清代': {
    src: qingdaiImage,
    thumb: '/images/covers/qingdai.webp',
    caption: '盛世帘影，旧梦将醒'
  },
  '西游记': {
    src: xiyouImage,
    thumb: '/images/covers/xiyou.webp',
    caption: '西行路上，妖雾重重'
  },
  '金瓶梅': {
    src: jinpingmeiImage,
    thumb: '/images/covers/jinpingmei.webp',
    caption: '清河县里，浮世众生'
  },
  '废土末世': {
    src: wastelandImage,
    thumb: '/images/covers/wasteland.webp',
    caption: '废土荒原，文明余烬'
  },
  '红楼梦': {
    src: hongloumengImage,
    thumb: '/images/covers/hongloumeng.webp',
    caption: '大观园里，一梦浮生'
  },
  '封神演义': {
    src: fengshenImage,
    thumb: '/images/covers/fengshen.webp',
    caption: '三界押注，商亡周兴'
  },
  '武侠江湖': {
    src: wuxiaImage,
    thumb: '/images/covers/wuxia.webp',
    caption: '一柄刀，一个理由'
  },
  '仙侠修真': {
    src: xianxiaImage,
    thumb: '/images/covers/xianxia.webp',
    caption: '从杂役到雷劫之下'
  },
  '大唐长安·天宝末年': {
    src: datangImage,
    thumb: '/images/covers/datang.webp',
    caption: '开元全盛日，一夜转衰'
  },
  '北宋汴京之变': {
    src: bianjingImage,
    thumb: '/images/covers/bianjing.webp',
    caption: '汴河千帆，终成旧梦'
  },
  '都市修真': {
    src: urbanImage,
    thumb: '/images/covers/urban.webp',
    caption: '写字楼里，灵气初醒'
  },
  '日常生活': {
    src: dailyImage,
    thumb: '/images/covers/daily.webp',
    caption: '周一早高峰，日子照旧'
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

const charTimelines = computed(() => {
  if (characterType.value === 'custom') {
    return timelines.value.map(name => ({ name, background: '' }))
  }
  return selectedChar.value?.timelines || []
})

const charDisplay = computed(() => (selectedChar.value?.custom ? null : selectedChar.value))

const currentWorldImage = computed(() => worldImageMap[form.value.novel] || worldImageMap['三国演义'])
// 选世界阶段：背景用 400×225 缩略图（首屏只需 ~160KB，不拉 5MB 原图）；选完世界后再用大图
const displayWorldImage = computed(() => {
  if (step.value === 'world') {
    const meta = worldImageMap[hoverNovel.value] || currentWorldImage.value
    return { src: meta.thumb }
  }
  return currentWorldImage.value
})

// 世界卡片数据（优先用接口返回的小说列表，接口挂了用硬编码兜底）
const worldCards = computed(() => {
  const names = novelsData.value.length > 0
    ? novelsData.value.map(n => n.novel_name)
    : Object.keys(FALLBACK_NOVELS)
  return names.map((novel, idx) => {
    const meta = worldImageMap[novel]
    return {
      novel,
      cover: meta?.thumb || worldImageMap['三国演义'].thumb,
      caption: meta?.caption || '未知世界，静待探索',
      badge: idx === 0 ? '推荐' : ''
    }
  })
})
const selectedPresetInfo = computed(() => {
  const cacheKey = `${form.value.novel}/${selectedPresetCharacter.value}`
  const presetInfo = presetCharacterCache.value[cacheKey]
  if (!presetInfo) return null
  return { ...presetInfo, novel: form.value.novel, timeline: form.value.timeline, character_type: 'preset' }
})

const previewCharacter = computed(() => {
  if (characterType.value === 'custom') {
    return form.value.name ? { ...form.value, is_minor: false } : null
  }
  return selectedChar.value || null
})

const resetForNovel = () => {
  form.value.timeline = timelines.value[0] || ''
  selectedPresetCharacter.value = ''
  form.value.name = ''
  form.value.starting_points = 0
  availableCharacters.value = {}
}

// 点击卡片「开始穿越」→ 锁定世界并进入角色选择
const selectWorld = (novel) => {
  if (form.value.novel !== novel) {
    form.value.novel = novel
    resetForNovel()
    selectedChar.value = null
    worldCharacters.value = []
  }
  hoverNovel.value = ''
  step.value = 'character'
  if (!selectedChar.value) {
    loadWorldCharacters()
    loadMyCharacters()
  }
  // 埋点失败不影响进入游戏
  communityAPI.trackWorldClick(novel).catch(() => {})
}

// 先选角色：拉这个世界的人（含小人物、头像、可玩节点）
const loadWorldCharacters = async () => {
  charLoading.value = true
  try {
    const data = await communityAPI.getWorldCharacters(form.value.novel)
    worldCharacters.value = data.characters || []
  } catch (err) {
    console.warn('加载世界角色失败，回退到旧接口:', err)
    worldCharacters.value = []
  } finally {
    charLoading.value = false
  }
}

const chooseCharacter = (c) => {
  selectedChar.value = c
  characterType.value = 'preset'
  form.value.name = c.name
  form.value.gender = c.gender || '男性'
  form.value.age = c.age || 20
  form.value.rank = c.rank || '未知'
  form.value.background = c.background || ''
  form.value.starting_points = c.starting_points || 0
  form.value.timeline = c.timelines?.[0]?.name || timelines.value[0] || ''
}

const loadMyCharacters = async () => {
  if (!authStore.isAuthenticated) {
    myCharacters.value = []
    return
  }
  try {
    const rows = await customCharacterAPI.list(form.value.novel)
    myCharacters.value = Array.isArray(rows) ? rows : []
  } catch (e) {
    myCharacters.value = []
  }
}

const fillCustomForm = (mc) => {
  form.value.name = mc.name || ''
  form.value.gender = mc.gender || '女性'
  form.value.age = mc.age || 20
  form.value.rank = mc.rank || '未知'
  form.value.background = mc.background || ''
}

const selectMyCharacter = (mc) => {
  editingCustomId.value = mc.id
  characterType.value = 'custom'
  selectedChar.value = { custom: true, name: mc.name, timelines: [] }
  fillCustomForm(mc)
  if (!form.value.timeline) form.value.timeline = timelines.value[0] || ''
  step.value = 'character'
}

const editMyCharacter = (mc) => {
  selectMyCharacter(mc)
}

const deleteMyCharacter = async (mc) => {
  if (!confirm(`删除自定义角色「${mc.name}」？这个操作不会影响已开始的存档。`)) return
  try {
    await customCharacterAPI.remove(mc.id)
    myCharacters.value = myCharacters.value.filter((x) => x.id !== mc.id)
    if (editingCustomId.value === mc.id) editingCustomId.value = null
  } catch (e) {
    error.value = '删除失败，请稍后再试'
  }
}

const chooseCustom = () => {
  editingCustomId.value = null
  selectedChar.value = { custom: true, name: '', timelines: [] }
  characterType.value = 'custom'
  form.value.name = ''
  form.value.age = 20
  form.value.rank = '未知'
  form.value.background = ''
  form.value.starting_points = 0
  form.value.timeline = timelines.value[0] || ''
  step.value = 'character'
}

const loadVotes = async () => {
  try {
    const data = await communityAPI.getWorldVotes()
    voteCandidates.value = data.candidates || []
    voteTotal.value = data.total_votes || 0
  } catch (err) {
    console.warn('投票列表加载失败:', err)
  }
}

const toggleVote = async (c) => {
  // 先乐观更新，失败再回滚
  const before = c.voted
  c.voted = !before
  c.votes += before ? -1 : 1
  voteTotal.value += before ? -1 : 1
  try {
    const res = await communityAPI.voteWorld(c.name)
    c.voted = res.voted
  } catch (err) {
    c.voted = before
    c.votes += before ? 1 : -1
    voteTotal.value += before ? 1 : -1
    error.value = '投票失败，请稍后再试'
    setTimeout(() => { error.value = '' }, 3000)
  }
}

const backToCharacters = () => {
  selectedChar.value = null
  error.value = ''
}

const backToWorlds = () => {
  step.value = 'world'
  hoverNovel.value = ''
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
  // 支持 /character-create?novel=废土末世 直达角色页（分享/回跳场景）
  const queryNovel = typeof route.query.novel === 'string' ? route.query.novel : ''
  if (queryNovel) {
    const known = novelsData.value.length > 0
      ? novelsData.value.some(n => n.novel_name === queryNovel)
      : Boolean(FALLBACK_NOVELS[queryNovel])
    if (known) {
      if (form.value.novel !== queryNovel) {
        form.value.novel = queryNovel
        resetForNovel()
      }
      step.value = 'character'
    }
  }

  loadVotes()

  // 选世界阶段暂不预加载角色，进入角色页时再拉
  if (step.value === 'character') {
    await loadWorldCharacters()
    await loadMyCharacters()
  }
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
  // 从「我的角色」点进来时不要清空表单（editingCustomId 已设）
  if (characterType.value === 'custom' && !editingCustomId.value) {
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

const handleLogout = () => {
  authStore.logout()
  router.push('/character-create')
}

const startGame = async () => {
  error.value = ''

  if (!form.value.name) {
    error.value = '请先选一个角色，或填写自定义角色的姓名'
    return
  }

  const age = Number(form.value.age)
  if (characterType.value === 'custom' && (!Number.isFinite(age) || age < 18)) {
    error.value = '自定义角色年龄请输入 18 岁以上的数字'
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

    // 自定义角色：登录用户自动存进「我的角色」，别人看不见
    if (characterType.value === 'custom' && authStore.isAuthenticated) {
      const payload = {
        novel: form.value.novel,
        name: characterData.name,
        gender: characterData.gender,
        age: characterData.age,
        rank: characterData.rank,
        background: characterData.background,
      }
      try {
        if (editingCustomId.value) {
          await customCharacterAPI.update(editingCustomId.value, payload)
        } else {
          const saved = await customCharacterAPI.create(payload)
          editingCustomId.value = saved?.id || null
        }
      } catch (e) {
        // 存角色失败不该挡住开局
        console.warn('保存自定义角色失败', e)
      }
    }

    const session = await gameStore.createGameSession(characterData)
    // 必须把 id 带进 URL：否则刷新页面 / 登录回跳都会丢掉会话，被守卫打回主界面
    router.replace(`/game/${session.id}`)
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

/* 选世界阶段背景用 400×225 缩略图：轻微放大 + 模糊，避免糊得明显 */
.create-bg.bg-thumb {
  background-size: cover;
  transform: scale(1.06);
  filter: blur(3px) saturate(1.05);
  transition: background-image 0.35s ease;
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

.top-link {
  color: rgba(255,215,150,0.9);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.top-link:hover {
  color: #f0c040;
}

.top-user {
  font-size: 0.82rem;
  color: rgba(255,255,255,0.65);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 中央内容区 ===== */
.create-content {
  position: relative;
  z-index: 5;
  height: calc(100vh - 76px - 74px);
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.create-content.is-world-step {
  align-items: flex-start;
  padding: 8px 20px 24px;
}

/* ===== 第一步：世界卡片网格 ===== */
.world-step {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
}

.world-step-head {
  text-align: center;
  margin: 0.5rem 0 1.25rem;
}

.world-step-head h2 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
  color: #f0e6d3;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.75);
}

.world-step-head p {
  margin: 0;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.65);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
}

/* 自动适配列数：宽度够就多列，窄屏自动降为 1 列 */
.world-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
}

.world-card {
  display: flex;
  flex-direction: column;
  background: rgba(10, 10, 25, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 215, 150, 0.16);
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  outline: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
  transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
}

.world-card:hover,
.world-card.active,
.world-card:focus-visible {
  transform: translateY(-4px);
  border-color: rgba(255, 215, 150, 0.55);
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 215, 150, 0.25) inset;
}

.world-cover {
  position: relative;
  aspect-ratio: 16 / 9;
  background-size: cover;
  background-position: center;
  background-color: #1a1a2e;
  transition: transform 0.35s ease;
}

.world-card:hover .world-cover,
.world-card.active .world-cover {
  transform: scale(1.04);
}

.world-cover::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.05) 40%, rgba(10, 10, 25, 0.85) 100%);
}

.world-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  padding: 3px 10px;
  font-size: 0.72rem;
  border-radius: 999px;
  color: #1a1a2e;
  background: #f0c040;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.world-info {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.85rem 1rem 1rem;
}

.world-info h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #f0e6d3;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.6);
}

.world-caption {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(255, 215, 150, 0.72);
  min-height: 1.2em;
}

.world-start {
  margin-top: 0.55rem;
  width: 100%;
  padding: 0.55rem;
  border-radius: 9px;
  border: 1px solid rgba(255, 215, 150, 0.45);
  background: rgba(240, 192, 64, 0.12);
  color: #f0c040;
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.world-card:hover .world-start,
.world-start:hover {
  background: #f0c040;
  border-color: #f0c040;
  color: #1a1a2e;
}

/* ===== 已选世界信息条 ===== */
.selected-world {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.75rem;
  margin-bottom: 0.9rem;
  border-radius: 10px;
  background: rgba(255, 215, 150, 0.08);
  border: 1px solid rgba(255, 215, 150, 0.18);
}

.selected-world-cover {
  width: 56px;
  height: 34px;
  flex: none;
  border-radius: 6px;
  background-size: cover;
  background-position: center;
}

.selected-world-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.selected-world-name {
  font-size: 0.92rem;
  font-weight: 700;
  color: #f0e6d3;
}

.selected-world-caption {
  font-size: 0.72rem;
  color: rgba(255, 215, 150, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.change-world {
  margin-left: auto;
  flex: none;
  padding: 0.3rem 0.7rem;
  font-size: 0.78rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 215, 150, 0.35);
  background: transparent;
  color: rgba(255, 215, 150, 0.9);
  cursor: pointer;
  transition: all 0.2s ease;
}

.change-world:hover {
  background: rgba(255, 215, 150, 0.18);
  color: #f0c040;
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

/* ===== 底部链接 ===== */
.create-footer {
  position: relative;
  z-index: 10;
  display: flex;
  justify-content: center;
  gap: 14px;
  padding: 12px 28px;
  flex-wrap: wrap;
}

.footer-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 10px 22px;
  border-radius: 24px;
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  letter-spacing: 0.3px;
}

.footer-btn-feedback {
  background: #1a1a2e;
  border: 2px solid #f0c040;
  color: #f0c040;
}

.footer-btn-feedback:hover {
  background: #f0c040;
  border-color: #f0c040;
  color: #1a1a2e;
  box-shadow: 0 4px 16px rgba(240,192,64,0.4);
  transform: translateY(-1px);
}

.footer-qq {
  font-size: 0.78rem;
  font-weight: 400;
  opacity: 0.8;
}

.footer-btn-github {
  background: #24292e;
  border: 2px solid #8b949e;
  color: #f0f6fc;
}

.footer-btn-github:hover {
  background: #333842;
  border-color: #c9d1d9;
  color: #fff;
  box-shadow: 0 4px 16px rgba(139,148,158,0.35);
  transform: translateY(-1px);
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
    height: calc(100vh - 100px - 74px);
    align-items: flex-start;
    padding: 12px;
  }

  .create-content.is-world-step {
    padding: 4px 12px 20px;
  }

  .world-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
  }

  .world-step-head h2 {
    font-size: 1.2rem;
  }

  .world-info {
    padding: 0.65rem 0.75rem 0.8rem;
  }

  .world-info h3 {
    font-size: 0.98rem;
  }

  .world-start {
    padding: 0.45rem;
    font-size: 0.82rem;
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

/* ===== 角色优先选择：角色卡片网格 ===== */
.step-hint {
  margin: -0.25rem 0 1rem;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.62);
  line-height: 1.6;
}

.char-loading {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 2rem 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.92rem;
}

.char-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 0.85rem;
  max-height: 52vh;
  overflow-y: auto;
  padding-right: 4px;
  margin-bottom: 0.5rem;
}

/* ===== 我的角色（私有） ===== */
.my-chars { margin: 0 0 18px; }
.my-chars-title {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.5px;
  color: rgba(214, 178, 108, 0.85);
}
.my-chars-row { display: flex; flex-wrap: wrap; gap: 8px; }
.my-char {
  display: flex;
  align-items: stretch;
  border: 1px solid rgba(214, 178, 108, 0.28);
  border-radius: 10px;
  background: rgba(214, 178, 108, 0.08);
  overflow: hidden;
}
.my-char-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.my-char-main strong { font-size: 13.5px; color: #efe2c6; }
.my-char-main span { font-size: 11px; color: rgba(240, 230, 211, 0.55); }
.my-char-act {
  width: 30px;
  border: none;
  border-left: 1px solid rgba(214, 178, 108, 0.18);
  background: transparent;
  color: rgba(240, 230, 211, 0.6);
  cursor: pointer;
  font-size: 12px;
}
.my-char-act:hover { background: rgba(255, 255, 255, 0.08); color: #f0e6d3; }
.my-char-act.danger:hover { background: rgba(200, 80, 80, 0.22); color: #ffd7d7; }

.char-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  background: rgba(18, 22, 30, 0.55);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  text-align: left;
  color: inherit;
  font: inherit;
}

.char-card:hover,
.char-card:focus-visible {
  transform: translateY(-3px);
  border-color: rgba(231, 178, 106, 0.75);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.38);
  outline: none;
}

.char-portrait {
  position: relative;
  aspect-ratio: 3 / 4;
  background: linear-gradient(155deg, #2b3a4a 0%, #1b2430 60%, #131a22 100%);
  background-size: cover;
  background-position: center top;
  display: flex;
  align-items: center;
  justify-content: center;
}

.char-initial {
  font-size: 2.4rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 2px;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

.char-flag {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 0.68rem;
  background: rgba(196, 122, 60, 0.9);
  color: #fff;
  letter-spacing: 0.5px;
}

.char-card.is-minor .char-portrait {
  background-image: linear-gradient(155deg, #3a2f28 0%, #241d18 100%);
}

.char-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0.55rem 0.65rem 0.7rem;
  background: rgba(10, 13, 18, 0.75);
}

.char-meta strong {
  font-size: 0.98rem;
  color: #fff;
  font-weight: 600;
}

.char-rank {
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.66);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-sub {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.42);
}

.char-portrait-custom {
  background: repeating-linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.04) 0 10px,
    rgba(255, 255, 255, 0.08) 10px 20px
  );
}

.char-plus {
  font-size: 1.8rem;
  color: rgba(255, 255, 255, 0.55);
}

.char-back {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
  padding: 0 0 0.6rem;
  cursor: pointer;
}

.char-back:hover { color: #e7b26a; }

/* 时间节点卡片 */
.tl-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 34vh;
  overflow-y: auto;
  padding-right: 4px;
}

.tl-card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 0.7rem 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(18, 22, 30, 0.55);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
  font: inherit;
}

.tl-card strong { font-size: 0.94rem; color: #fff; }
.tl-card span { font-size: 0.8rem; color: rgba(255, 255, 255, 0.58); line-height: 1.5; }

.tl-card:hover { border-color: rgba(231, 178, 106, 0.5); }

.tl-card.active {
  border-color: #e7b26a;
  background: rgba(231, 178, 106, 0.12);
}

/* 预览头像 */
.preview-portrait {
  width: 100%;
  aspect-ratio: 3 / 2;
  border-radius: 10px;
  margin-bottom: 0.8rem;
  background-size: cover;
  background-position: center 22%;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.badge-minor {
  background: rgba(196, 122, 60, 0.85);
  color: #fff;
  margin-left: 0.4rem;
}

@media (max-width: 768px) {
  .char-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); max-height: 46vh; }
  .char-initial { font-size: 1.9rem; }
  .tl-list { max-height: 30vh; }
}


/* ===== 想看哪个世界：投票 ===== */
.vote-panel {
  margin-top: 1.2rem;
  padding: 1rem 1.1rem 1.15rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  background: rgba(10, 13, 18, 0.55);
  backdrop-filter: blur(6px);
}

.vote-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.vote-head h3 { margin: 0; font-size: 1rem; color: #fff; }
.vote-head span { font-size: 0.78rem; color: rgba(255, 255, 255, 0.5); }

.vote-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.vote-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.42rem 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.86);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.16s ease;
}

.vote-chip:hover { border-color: rgba(231, 178, 106, 0.6); }

.vote-chip.voted {
  border-color: #e7b26a;
  background: rgba(231, 178, 106, 0.16);
  color: #ffe0b0;
}

.vote-count {
  font-variant-numeric: tabular-nums;
  font-size: 0.76rem;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
}

.vote-hint {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.42);
  max-width: 0;
  overflow: hidden;
  white-space: nowrap;
  transition: max-width 0.2s ease, opacity 0.2s ease;
  opacity: 0;
}

.vote-chip:hover .vote-hint { max-width: 12rem; opacity: 1; }

</style>
