<template>
  <div class="pricing-page">
    <div class="pricing-shell">
      <router-link to="/character-create" class="back">← 返回游戏</router-link>

      <header class="head">
        <h1>定价</h1>
        <p class="sub">
          这不是订阅制小说，是每一次 AI 生成都要付钱的服务。所以价格按真实成本定，而不是按章节卖。
        </p>
      </header>

      <section class="plans">
        <article
          v-for="plan in PLANS"
          :key="plan.id"
          :class="['plan', { featured: plan.highlight, free: plan.id === 'free' }]"
        >
          <div class="plan-head">
            <span class="plan-name">{{ plan.name }}</span>
            <span v-if="plan.highlight" class="plan-badge">最多人选</span>
          </div>
          <p class="plan-price">
            <span class="currency">¥</span>{{ plan.price }}<span class="unit">{{ plan.unit }}</span>
          </p>
          <p class="plan-tag">{{ plan.tag }}</p>
          <ul class="plan-quota">
            <li v-for="(q, i) in plan.quota" :key="i">{{ q }}</li>
          </ul>
          <p class="plan-note">{{ plan.note }}</p>
          <router-link v-if="plan.id === 'free'" to="/character-create" class="plan-cta ghost-cta">
            {{ plan.cta }}
          </router-link>
          <button v-else class="plan-cta" @click="openContact(plan)">
            {{ plan.cta }}
          </button>
        </article>
      </section>

      <section class="faq">
        <h2>常见问题</h2>
        <details v-for="(item, i) in PRICING_FAQ" :key="i" class="faq-item">
          <summary>{{ item.q }}</summary>
          <p>{{ item.a }}</p>
        </details>
      </section>

      <section class="contact">
        <h2>内测期怎么开通</h2>
        <p>在线支付还在接入（微信 / 支付宝）。现在购买请加作者 QQ，说明要哪一档，转账后手动开通，通常当天生效。</p>
        <div class="contact-row">
          <span class="qq">{{ AUTHOR_QQ }}</span>
          <button class="btn" @click="copyQQ">{{ copied ? '✅ 已复制' : '复制 QQ 号' }}</button>
          <router-link to="/character-create" class="btn ghost">先免费玩几天</router-link>
        </div>
        <p class="contact-tip">{{ copied ? '已复制，去 QQ 搜索添加即可' : CONTACT_TIP }}</p>
      </section>

      <nav class="legal-nav">
        <router-link to="/terms">服务条款</router-link>
        <span>·</span>
        <router-link to="/refund">退款政策</router-link>
        <span>·</span>
        <router-link to="/privacy">隐私政策</router-link>
      </nav>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { PLANS, PRICING_FAQ } from '@/content/pricing'
import { AUTHOR_QQ, CONTACT_TIP } from '@/content/contact'

const copied = ref(false)

async function copyQQ() {
  try {
    await navigator.clipboard.writeText(AUTHOR_QQ)
    copied.value = true
  } catch {
    copied.value = false
  }
}

function openContact() {
  copyQQ()
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}
</script>

<style scoped>
.pricing-page {
  min-height: 100vh;
  padding: 28px 16px 48px;
  background: linear-gradient(180deg, #fffdf6 0%, #f7f1e3 100%);
  color: #2f2a22;
}

.pricing-shell {
  max-width: 980px;
  margin: 0 auto;
}

.back {
  display: inline-block;
  margin-bottom: 18px;
  font-size: 0.86rem;
  color: #8a6d2f;
  text-decoration: none;
}

.head {
  text-align: center;
  margin-bottom: 26px;
}

.head h1 {
  margin: 0 0 10px;
  font-size: 1.8rem;
  letter-spacing: 0.08em;
}

.sub {
  max-width: 620px;
  margin: 0 auto;
  line-height: 1.7;
  font-size: 0.92rem;
  color: #6b6153;
}

.plans {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.plan {
  display: flex;
  flex-direction: column;
  padding: 18px 16px;
  border: 1px solid rgba(212, 175, 55, 0.35);
  border-radius: 14px;
  background: #fffef9;
  box-shadow: 0 2px 10px rgba(120, 95, 40, 0.06);
}

.plan.featured {
  border-color: #c9a227;
  box-shadow: 0 6px 22px rgba(201, 162, 39, 0.18);
  transform: translateY(-4px);
}

.plan.free {
  background: #fbf8ef;
}

.plan-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.plan-name {
  font-weight: 600;
  letter-spacing: 0.06em;
}

.plan-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: #c9a227;
  color: #fff;
  font-size: 0.7rem;
}

.plan-price {
  margin: 0 0 6px;
  font-size: 2rem;
  font-weight: 700;
  color: #8a6d2f;
  line-height: 1.1;
}

.currency {
  font-size: 1rem;
  margin-right: 2px;
}

.unit {
  margin-left: 4px;
  font-size: 0.8rem;
  font-weight: 400;
  color: #8a8578;
}

.plan-tag {
  margin: 0 0 12px;
  font-size: 0.82rem;
  color: #6b6153;
  min-height: 1.6em;
}

.plan-quota {
  margin: 0 0 10px;
  padding: 0;
  list-style: none;
  font-size: 0.85rem;
  line-height: 1.9;
}

.plan-quota li::before {
  content: '·';
  margin-right: 6px;
  color: #c9a227;
}

.plan-note {
  margin: auto 0 14px;
  font-size: 0.76rem;
  line-height: 1.6;
  color: #8a8578;
}

.plan-cta {
  padding: 10px 0;
  border: none;
  border-radius: 999px;
  background: #8a6d2f;
  color: #fff;
  font-size: 0.88rem;
  cursor: pointer;
}

.plan-cta:hover {
  background: #6f5624;
}

.plan.featured .plan-cta {
  background: #c9a227;
  color: #2b2417;
  font-weight: 600;
}

.plan.featured .plan-cta:hover {
  background: #b8911f;
}

.plan-cta.ghost-cta {
  display: block;
  text-align: center;
  text-decoration: none;
  background: transparent;
  border: 1px solid rgba(138, 109, 47, 0.45);
  color: #8a6d2f;
}

.faq,
.contact {
  margin-top: 34px;
}

.faq h2,
.contact h2 {
  margin: 0 0 12px;
  font-size: 1.06rem;
  letter-spacing: 0.04em;
}

.contact p {
  margin: 0 0 10px;
  font-size: 0.9rem;
  line-height: 1.8;
  color: #4a4338;
}

.faq-item {
  padding: 12px 0;
  border-bottom: 1px solid rgba(212, 175, 55, 0.22);
}

.faq-item summary {
  cursor: pointer;
  font-size: 0.92rem;
  color: #2f2a22;
}

.faq-item p {
  margin: 10px 0 0;
  font-size: 0.86rem;
  line-height: 1.8;
  color: #6b6153;
}

.contact-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 12px 0 8px;
}

.qq {
  padding: 6px 12px;
  border-radius: 8px;
  background: #fff8e5;
  border: 1px dashed #c9a227;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 1rem;
  letter-spacing: 0.08em;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 999px;
  background: #8a6d2f;
  color: #fff;
  font-size: 0.85rem;
  cursor: pointer;
  text-decoration: none;
}

.btn.ghost {
  background: transparent;
  border: 1px solid rgba(138, 109, 47, 0.5);
  color: #8a6d2f;
}

.contact-tip {
  font-size: 0.8rem;
  color: #8a8578;
}

.legal-nav {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 30px;
  font-size: 0.82rem;
  color: #8a8578;
}

.legal-nav a {
  color: #8a6d2f;
  text-decoration: none;
}

@media (max-width: 860px) {
  .plans {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .plans {
    grid-template-columns: 1fr;
  }

  .plan.featured {
    transform: none;
  }
}
</style>
