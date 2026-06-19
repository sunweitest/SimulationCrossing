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

export default router

import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
