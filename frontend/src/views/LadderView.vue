<template>
  <div class="ladder-page">
    <div class="ladder-bg"></div>

    <div class="page-nav">
      <router-link to="/character-create" class="back-link">← 返回主界面</router-link>
    </div>

    <header class="ladder-head">
      <h1>🏆 天梯排行榜</h1>
      <p>按存档积分排名 · 共 {{ totalSessions }} 个存档 / {{ totalPlayers }} 位玩家</p>
    </header>

    <!-- 世界筛选 -->
    <div class="world-tabs">
      <button
        class="world-tab"
        :class="{ active: activeWorld === 'all' }"
        @click="selectWorld('all')"
      >
        全部世界
      </button>
      <button
        v-for="w in worlds"
        :key="w.novel"
        class="world-tab"
        :class="{ active: activeWorld === w.novel }"
        @click="selectWorld(w.novel)"
      >
        {{ w.novel }}
        <span class="tab-count">{{ w.sessions }}</span>
      </button>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>加载中…</p>
    </div>

    <template v-else>
      <!-- 榜 -->
      <div class="board">
        <div v-if="top.length === 0" class="empty">还没有人上榜，去玩一局就是第一名。</div>
        <ol v-else class="top-list">
          <li v-for="row in top" :key="row.session_id" class="top-row" :class="'rank-' + row.rank">
            <span class="rank">{{ medal(row.rank) }}</span>
            <span class="who">
              <strong>{{ row.character_name }}</strong>
              <span class="who-sub">{{ row.character_rank }} · {{ row.novel }} · {{ row.timeline }}</span>
            </span>
            <span class="points">{{ row.points }}<small>分</small></span>
          </li>
        </ol>
      </div>

      <!-- 世界概览 -->
      <div class="world-board">
        <h2>各世界战况</h2>
        <div class="world-cards">
          <div v-for="w in worlds" :key="w.novel" class="world-stat">
            <div class="world-stat-cover" :style="{ backgroundImage: `url(${coverOf(w.novel)})` }"></div>
            <div class="world-stat-body">
              <h3>{{ w.novel }}</h3>
              <div class="stat-line"><span>最高分</span><b>{{ w.top_points }}</b></div>
              <div class="stat-line"><span>平均分</span><b>{{ w.avg_points }}</b></div>
              <div class="stat-line"><span>存档 / 玩家</span><b>{{ w.sessions }} / {{ w.players }}</b></div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { communityAPI } from '@/api'

const worlds = ref([])
const top = ref([])
const activeWorld = ref('all')
const loading = ref(true)

const totalSessions = computed(() => worlds.value.reduce((s, w) => s + w.sessions, 0))
const totalPlayers = computed(() => worlds.value.reduce((s, w) => s + w.players, 0))

const COVERS = {
  '三国演义': 'sanguo', '水浒传': 'shuihu', '明代': 'mingdai', '清代': 'qingdai',
  '西游记': 'xiyou', '金瓶梅': 'jinpingmei', '废土末世': 'wasteland',
  '红楼梦': 'hongloumeng', '封神演义': 'fengshen', '武侠江湖': 'wuxia',
  '仙侠修真': 'xianxia', '大唐长安·天宝末年': 'datang', '北宋汴京之变': 'bianjing'
}
const coverOf = (novel) => `/images/covers/${COVERS[novel] || 'sanguo'}.webp`

const medal = (rank) => (rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank)

const load = async () => {
  loading.value = true
  try {
    const data = await communityAPI.getLadder({ world: activeWorld.value, limit: 30 })
    worlds.value = data.worlds || []
    top.value = data.top || []
  } catch (err) {
    console.error('天梯加载失败:', err)
  } finally {
    loading.value = false
  }
}

const selectWorld = (w) => {
  activeWorld.value = w
  load()
}

onMounted(load)
</script>

<style scoped>
.ladder-page {
  position: relative;
  min-height: 100vh;
  padding: 1.2rem clamp(1rem, 4vw, 3rem) 3rem;
  color: #f2f4f7;
}

.ladder-bg {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(1200px 600px at 20% -10%, rgba(231, 178, 106, 0.16), transparent 60%),
    radial-gradient(900px 500px at 90% 10%, rgba(70, 120, 180, 0.16), transparent 60%),
    #0b0e13;
}

.page-nav { margin-bottom: 0.8rem; }

.back-link {
  color: rgba(255, 255, 255, 0.62);
  text-decoration: none;
  font-size: 0.9rem;
}

.back-link:hover { color: #e7b26a; }

.ladder-head h1 {
  margin: 0 0 0.3rem;
  font-size: clamp(1.5rem, 3vw, 2rem);
  letter-spacing: 1px;
}

.ladder-head p {
  margin: 0 0 1.2rem;
  color: rgba(255, 255, 255, 0.55);
  font-size: 0.88rem;
}

.world-tabs {
  display: flex;
  gap: 0.45rem;
  overflow-x: auto;
  padding-bottom: 0.6rem;
  margin-bottom: 1rem;
}

.world-tab {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.84rem;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.16s ease;
}

.world-tab:hover { border-color: rgba(231, 178, 106, 0.5); }

.world-tab.active {
  border-color: #e7b26a;
  background: rgba(231, 178, 106, 0.16);
  color: #ffe0b0;
}

.tab-count {
  font-size: 0.72rem;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
}

.board {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: rgba(14, 18, 24, 0.66);
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.empty {
  padding: 3rem 1rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
}

.top-list { list-style: none; margin: 0; padding: 0.4rem; }

.top-row {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.72rem 0.9rem;
  border-radius: 10px;
}

.top-row + .top-row { margin-top: 2px; }

.top-row.rank-1 { background: linear-gradient(90deg, rgba(231, 178, 106, 0.18), transparent); }
.top-row.rank-2 { background: linear-gradient(90deg, rgba(190, 200, 215, 0.14), transparent); }
.top-row.rank-3 { background: linear-gradient(90deg, rgba(190, 130, 90, 0.14), transparent); }

.rank {
  width: 2rem;
  text-align: center;
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.6);
  font-variant-numeric: tabular-nums;
}

.who { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.who strong { font-size: 0.98rem; }
.who-sub {
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.points {
  font-size: 1.15rem;
  font-weight: 700;
  color: #e7b26a;
  font-variant-numeric: tabular-nums;
}

.points small { font-size: 0.7rem; margin-left: 2px; color: rgba(255, 255, 255, 0.5); font-weight: 400; }

.world-board { margin-top: 1.6rem; }
.world-board h2 { font-size: 1.05rem; margin: 0 0 0.75rem; color: rgba(255, 255, 255, 0.85); }

.world-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.8rem;
}

.world-stat {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(14, 18, 24, 0.6);
}

.world-stat-cover {
  height: 84px;
  background-size: cover;
  background-position: center 30%;
  opacity: 0.85;
}

.world-stat-body { padding: 0.6rem 0.75rem 0.75rem; }
.world-stat-body h3 { margin: 0 0 0.4rem; font-size: 0.92rem; }

.stat-line {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.5);
  padding: 1px 0;
}

.stat-line b { color: rgba(255, 255, 255, 0.85); font-weight: 600; }
</style>
