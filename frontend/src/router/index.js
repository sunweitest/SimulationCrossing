import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/character-create'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue')
  },
  {
    path: '/character-create',
    name: 'CharacterCreate',
    component: () => import('@/views/CharacterCreateView.vue')
  },
  {
    path: '/game/:id?',
    name: 'Game',
    component: () => import('@/views/GameView.vue'),
    meta: { requiresGame: true }
  },
  {
    path: '/ladder',
    name: 'Ladder',
    component: () => import('@/views/LadderView.vue')
  },
  {
    path: '/my-games',
    name: 'MyGames',
    component: () => import('@/views/MyGamesView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/character-relations',
    name: 'CharacterRelations',
    component: () => import('@/views/CharacterRelationsView.vue'),
    meta: { requiresGame: true }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/AdminView.vue')
  },
  {
    path: '/privacy',
    name: 'Privacy',
    component: () => import('@/views/LegalView.vue'),
    meta: { doc: 'privacy' }
  },
  {
    path: '/terms',
    name: 'Terms',
    component: () => import('@/views/LegalView.vue'),
    meta: { doc: 'terms' }
  },
  {
    path: '/refund',
    name: 'Refund',
    component: () => import('@/views/LegalView.vue'),
    meta: { doc: 'refund' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const gameStore = useGameStore()

  // 需要登录的页面
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  // 需要游戏会话：无 id 参数时必须已有 currentSession；有 id 参数时放行
  if (to.meta.requiresGame && !to.params.id && !gameStore.currentSession) {
    next('/character-create')
    return
  }

  next()
})

// 懒加载 chunk 拉取失败：发布后旧页面里的 chunk 名已不存在，强制刷新一次拿新版本
// 否则用户只会看到空白页 + 控制台 "Failed to fetch dynamically imported module"
router.onError((error, to) => {
  const msg = String((error && error.message) || error)
  const isChunkError = /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk [\w-]+ failed/i.test(msg)
  if (!isChunkError) return
  const KEY = 'chunk_reload_at'
  const last = Number(sessionStorage.getItem(KEY) || 0)
  if (Date.now() - last < 60000) return // 一分钟内只自动重载一次，避免死循环
  sessionStorage.setItem(KEY, String(Date.now()))
  const target = (to && to.fullPath) || location.pathname + location.search
  location.replace(target)
})

export default router

import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
