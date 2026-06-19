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

  const performActionStream = async (action, callbacks = {}) => {
    if (!currentSession.value) return

    isGenerating.value = true
    let finalScene = null

    try {
      const headers = { 'Content-Type': 'application/json' }
      const token = localStorage.getItem('token')
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch('/api/game/action/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          action,
          game_session_id: currentSession.value.id
        })
      })

      if (!response.ok) {
        let detail = '执行行动失败'
        try {
          const errorBody = await response.json()
          detail = errorBody.detail || detail
        } catch {
          detail = await response.text()
        }
        const error = new Error(typeof detail === 'string' ? detail : detail.message || '执行行动失败')
        error.response = { status: response.status, data: { detail } }
        throw error
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      const handleEvent = (rawEvent) => {
        const lines = rawEvent.split('\n')
        let eventName = 'message'
        const dataLines = []

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trimStart())
          }
        }

        if (!dataLines.length) return

        const dataText = dataLines.join('\n')
        const payload = JSON.parse(dataText)

        if (eventName === 'status') callbacks.onStatus?.(payload)
        if (eventName === 'story_chunk') callbacks.onStoryChunk?.(payload.delta || '')
        if (eventName === 'scene') {
          finalScene = payload
          currentSession.value.current_scene = payload
          currentSession.value.points += payload.game_update.points_awarded
          callbacks.onScene?.(payload)
        }
        if (eventName === 'done') callbacks.onDone?.(payload)
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''
        for (const event of events) {
          if (event.trim()) handleEvent(event)
        }
      }

      buffer += decoder.decode()
      if (buffer.trim()) handleEvent(buffer)

      return finalScene
    } finally {
      isGenerating.value = false
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
    performActionStream,
    loadGameState,
    loadExistingSession,
    listSessions,
    deleteSession,
    resetGame
  }
})
