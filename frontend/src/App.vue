<template>
  <div id="app">
    <header v-if="authStore.isAuthenticated" class="app-header">
      <div class="container">
        <div class="header-content">
          <h2>🎮 AI穿越模拟</h2>
          <div class="user-info">
            <router-link to="/my-games" class="header-link">我的游戏</router-link>
            <span>{{ authStore.user?.email || authStore.user?.phone }}</span>
            <button @click="handleLogout" class="btn btn-secondary">退出</button>
          </div>
        </div>
      </div>
    </header>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const gameStore = useGameStore()
const router = useRouter()

const handleLogout = () => {
  authStore.logout()
  gameStore.resetGame()
  router.push('/login')
}
</script>

<style scoped>
.app-header {
  background: var(--card-bg);
  border-bottom: 2px solid var(--border-color);
  padding: 1rem 0;
  box-shadow: var(--shadow-sm);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
  border: none;
  padding: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-link {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  transition: all 0.2s;
}

.header-link:hover {
  background: var(--accent-color);
  color: white;
}

.app-main {
  min-height: calc(100vh - 100px);
}
</style>
