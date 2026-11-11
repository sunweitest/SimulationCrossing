<template>
  <footer class="site-footer">
    <div class="site-footer-inner">
      <nav class="footer-links">
        <router-link to="/pricing">定价</router-link>
        <span class="dot">·</span>
        <router-link to="/privacy">隐私政策</router-link>
        <span class="dot">·</span>
        <router-link to="/terms">服务条款</router-link>
        <span class="dot">·</span>
        <router-link to="/refund">退款政策</router-link>
      </nav>
      <p class="footer-meta">
        © {{ year }} {{ LEGAL_META.site }} · 联系：<a :href="`mailto:${LEGAL_META.email}`">{{ LEGAL_META.email }}</a>
      </p>
      <p class="footer-note">剧情由 AI 生成，仅供娱乐。</p>
    </div>
  </footer>
</template>

<script setup>
import { LEGAL_META } from '@/content/legal'
const year = new Date().getFullYear()
</script>

<style scoped>
.site-footer {
  padding: 22px 16px 26px;
  text-align: center;
  font-size: 0.82rem;
  color: #8a8578;
  border-top: 1px solid rgba(212, 175, 55, 0.25);
  background: rgba(255, 254, 247, 0.6);
}

.footer-links {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.footer-links a {
  color: var(--secondary-color, #8b7355);
  text-decoration: none;
}

.footer-links a:hover { color: var(--accent-color, #d4af37); }

.dot { color: rgba(139, 115, 85, 0.5); }

.footer-meta { line-height: 1.9; }
.footer-meta a { color: var(--secondary-color, #8b7355); }
.footer-note { color: #a8a294; font-size: 0.78rem; }
</style>
