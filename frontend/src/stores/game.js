import { defineStore } from 'pinia'
import { ref } from 'vue'
import { gameAPI } from '@/api'

export const useGameStore = defineStore('game', () => {
  const currentSession = ref(null)
  const gameState = ref(null)
  const isGenerating = ref(false)

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

  const resetGame = () => {
    currentSession.value = null
    gameState.value = null
    isGenerating.value = false
  }

  return {
    currentSession,
    gameState,
    isGenerating,
    createGameSession,
    performAction,
    loadGameState,
    resetGame
  }
})
