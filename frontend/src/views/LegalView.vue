<template>
  <div class="legal-page">
    <div class="legal-shell">
      <router-link to="/character-create" class="legal-back">← 返回游戏</router-link>

      <article class="legal-card">
        <header class="legal-head">
          <h1>{{ doc.title }}</h1>
          <p class="legal-sub">{{ LEGAL_META.site }} · 最后更新 {{ LEGAL_META.updated }}</p>
        </header>

        <p class="legal-intro">{{ doc.intro }}</p>

        <section v-for="(sec, i) in doc.sections" :key="i" class="legal-section">
          <h2>{{ sec.h }}</h2>
          <ul v-if="sec.list">
            <li v-for="(item, j) in sec.list" :key="j">{{ item }}</li>
          </ul>
          <p v-for="(para, k) in sec.p || []" :key="'p' + k">{{ para }}</p>
          <p v-if="sec.note" class="legal-note">{{ sec.note }}</p>
        </section>

        <footer class="legal-foot">
          <p>运营者：{{ LEGAL_META.operator }}</p>
          <p>联系方式：QQ {{ LEGAL_META.qq }}</p>
          <p>邮箱：<a :href="`mailto:${LEGAL_META.email}`">{{ LEGAL_META.email }}</a></p>
        </footer>
      </article>

      <nav class="legal-nav">
        <router-link to="/privacy" :class="{ active: kind === 'privacy' }">隐私政策</router-link>
        <span>·</span>
        <router-link to="/terms" :class="{ active: kind === 'terms' }">服务条款</router-link>
        <span>·</span>
        <router-link to="/refund" :class="{ active: kind === 'refund' }">退款政策</router-link>
      </nav>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DOCS, LEGAL_META } from '@/content/legal'

const route = useRoute()
const kind = computed(() => route.meta.doc || 'privacy')
const doc = computed(() => DOCS[kind.value] || DOCS.privacy)
</script>

<style scoped>
.legal-page {
  min-height: 100vh;
  padding: 32px 16px 64px;
  background: linear-gradient(135deg, #f5f5dc 0%, #fffef7 100%);
}

.legal-shell {
  max-width: 820px;
  margin: 0 auto;
}

.legal-back {
  display: inline-block;
  margin-bottom: 16px;
  color: var(--secondary-color);
  text-decoration: none;
  font-size: 0.92rem;
}

.legal-back:hover { color: var(--accent-color); }

.legal-card {
  background: var(--card-bg);
  border: 1px solid rgba(212, 175, 55, 0.35);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
  padding: 36px 40px 32px;
}

.legal-head h1 {
  font-size: 1.6rem;
  color: var(--primary-color);
  letter-spacing: 2px;
  margin-bottom: 6px;
}

.legal-sub {
  font-size: 0.82rem;
  color: var(--text-light);
}

.legal-intro {
  margin: 18px 0 26px;
  padding: 14px 16px;
  background: rgba(212, 175, 55, 0.08);
  border-left: 3px solid var(--accent-color);
  border-radius: 6px;
  color: #4a4a4a;
  font-size: 0.95rem;
  line-height: 1.8;
}

.legal-section { margin-bottom: 26px; }

.legal-section h2 {
  font-size: 1.05rem;
  color: var(--primary-color);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px dashed rgba(212, 175, 55, 0.4);
}

.legal-section ul {
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legal-section li,
.legal-section p {
  font-size: 0.93rem;
  line-height: 1.85;
  color: #4a4a4a;
}

.legal-section p + p { margin-top: 8px; }

.legal-note {
  margin-top: 10px;
  font-size: 0.86rem !important;
  color: #8a7a5c !important;
  background: rgba(212, 175, 55, 0.07);
  border-radius: 6px;
  padding: 8px 12px;
}

.legal-foot {
  margin-top: 30px;
  padding-top: 18px;
  border-top: 1px solid rgba(212, 175, 55, 0.28);
  font-size: 0.86rem;
  color: var(--text-light);
  line-height: 2;
}

.legal-foot a { color: var(--secondary-color); }

.legal-nav {
  margin-top: 20px;
  text-align: center;
  font-size: 0.88rem;
  color: var(--text-light);
}

.legal-nav a {
  color: var(--secondary-color);
  text-decoration: none;
  padding: 0 4px;
}

.legal-nav a.active {
  color: var(--accent-color);
  font-weight: 600;
}

@media (max-width: 640px) {
  .legal-card { padding: 24px 20px 22px; }
  .legal-head h1 { font-size: 1.35rem; }
  .legal-section li, .legal-section p { font-size: 0.9rem; }
}
</style>
