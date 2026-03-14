import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
    path: '/game',
    name: 'Game',
    component: () => import('@/views/GameView.vue'),
    meta: { requiresGame: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const gameStore = useGameStore()

  if (to.meta.requiresGame && !gameStore.currentSession) {
    next('/character-create')
  } else {
    next()
  }
})

export default router

// 需要导入store
import { useGameStore } from '@/stores/game'
