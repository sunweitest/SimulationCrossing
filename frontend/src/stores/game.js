import { defineStore } from 'pinia'
import { ref } from 'vue'
import { gameAPI } from '@/api'

export const useGameStore = defineStore('game', () => {
  const currentSession = ref(null)
  const gameState = ref(null)
  const isGenerating = ref(false)
  const mySessions = ref([])
  const isSessionsLoading = ref(false)

  const createGameSession = async (characterData) => {
    const response = await gameAPI.createSession({ character: characterData })
    currentSession.value = response
    return response
  }

  const performAction = async (action) => {
    if (!currentSession.value) return

    isGenerating.value = true
    try {
      const response = await gameAPI.performAction({
        action,
        game_session_id: currentSession.value.id
      })
      isGenerating.value = false
      return response
    } catch (error) {
      isGenerating.value = false
      throw error
    }
  }

  const loadGameState = async (sessionId) => {
    const state = await gameAPI.getGameState(sessionId)
    gameState.value = state
    return state
  }

  const loadExistingSession = async (sessionId) => {
    const session = await gameAPI.getSession(sessionId)
    currentSession.value = session
    return session
  }

  const listSessions = async () => {
    isSessionsLoading.value = true
    try {
      const data = await gameAPI.getSessions()
      mySessions.value = data
      return data
    } finally {
      isSessionsLoading.value = false
    }
  }

  const deleteSession = async (sessionId) => {
    await gameAPI.deleteSession(sessionId)
    mySessions.value = mySessions.value.filter(s => s.id !== sessionId)
    // 如果删除的是当前正在玩的会话，一并清除
    if (currentSession.value?.id === sessionId) {
      currentSession.value = null
      gameState.value = null
    }
  }

  const resetGame = () => {
    currentSession.value = null
    gameState.value = null
    isGenerating.value = false
    mySessions.value = []
  }

  return {
    currentSession,
    gameState,
    isGenerating,
    mySessions,
    isSessionsLoading,
    createGameSession,
    performAction,
    loadGameState,
    loadExistingSession,
    listSessions,
    deleteSession,
    resetGame
  }
})
