import { useEffect, useRef, useCallback } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:7767/ws'

export function useStreamOpsWebSocket() {
  const queryClient = useQueryClient()
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5
  
  // WebSocket connection
  const {
    sendMessage,
    lastMessage,
    readyState,
    getWebSocket
  } = useWebSocket(WS_URL, {
    onOpen: () => {
      console.log('WebSocket connected')
      reconnectAttempts.current = 0
      
      // Subscribe to relevant events
      sendMessage(JSON.stringify({
        type: 'subscribe',
        channels: ['system', 'jobs', 'assets', 'drives']
      }))
    },
    onClose: () => {
      console.log('WebSocket disconnected')
    },
    onError: (error) => {
      console.error('WebSocket error:', error)
      if (reconnectAttempts.current >= maxReconnectAttempts) {
        console.log('Max reconnection attempts reached, falling back to polling')
      }
      reconnectAttempts.current++
    },
    shouldReconnect: () => reconnectAttempts.current < maxReconnectAttempts,
    reconnectInterval: (attemptNumber) => Math.min(1000 * 2 ** attemptNumber, 10000),
    reconnectAttempts: maxReconnectAttempts
  })
  
  // Handle incoming messages
  useEffect(() => {
    if (!lastMessage) return
    
    try {
      const data = JSON.parse(lastMessage.data)
      
      switch (data.type) {
        // System updates
        case 'system.summary':
          queryClient.setQueryData(['system', 'summary'], data.payload)
          break
          
        case 'system.metrics':
          queryClient.setQueryData(['system', 'metrics'], (old) => ({
            ...old,
            ...data.payload
          }))
          break
          
        case 'system.health':
          queryClient.setQueryData(['system', 'summary'], (old) => ({
            ...old,
            health: data.payload
          }))
          if (data.payload.status === 'degraded' || data.payload.status === 'critical') {
            toast.error(`System health: ${data.payload.reason}`)
          }
          break
          
        // Job updates
        case 'job.created':
        case 'job.started':
        case 'job.progress':
        case 'job.completed':
        case 'job.failed':
          // Invalidate active jobs query
          queryClient.invalidateQueries({ queryKey: ['jobs', 'active'] })
          
          // Update specific job if viewing it
          if (data.payload.id) {
            queryClient.setQueryData(['jobs', data.payload.id], data.payload)
          }
          
          // Show notifications for important events
          if (data.type === 'job.failed') {
            toast.error(`Job failed: ${data.payload.type}`)
          }
          break
          
        // Asset updates
        case 'asset.created':
        case 'asset.updated':
          // Invalidate recent assets query
          queryClient.invalidateQueries({ queryKey: ['assets', 'recent'] })
          
          // Update specific asset if viewing it
          if (data.payload.id) {
            queryClient.setQueryData(['assets', data.payload.id], data.payload)
          }
          break
          
        // Drive updates
        case 'drive.status':
          queryClient.setQueryData(['drives', 'status'], data.payload)
          break
          
        case 'drive.watcher':
          // Update specific drive watcher status
          queryClient.setQueryData(['drives', 'status'], (old) => {
            if (!old) return old
            return old.map(drive => 
              drive.id === data.payload.drive_id 
                ? { ...drive, watcher_enabled: data.payload.enabled }
                : drive
            )
          })
          break
          
        // OBS updates
        case 'obs.connected':
        case 'obs.disconnected':
        case 'obs.recording.started':
        case 'obs.recording.stopped':
          queryClient.setQueryData(['system', 'summary'], (old) => ({
            ...old,
            obs: {
              connected: data.type === 'obs.connected' || data.type === 'obs.recording.started' || data.type === 'obs.recording.stopped',
              recording: data.type === 'obs.recording.started',
              version: data.payload?.version || old?.obs?.version
            }
          }))
          
          // Show OBS notifications
          if (data.type === 'obs.recording.started') {
            toast.success('OBS recording started')
          } else if (data.type === 'obs.recording.stopped') {
            toast.success('OBS recording stopped')
          }
          break
          
        // Guardrails updates
        case 'guardrails.activated':
          queryClient.setQueryData(['system', 'summary'], (old) => ({
            ...old,
            guardrails: {
              active: true,
              reason: data.payload.reason
            }
          }))
          toast.warning(`Guardrails activated: ${data.payload.reason}`)
          break
          
        case 'guardrails.deactivated':
          queryClient.setQueryData(['system', 'summary'], (old) => ({
            ...old,
            guardrails: {
              active: false,
              reason: null
            }
          }))
          toast.success('Guardrails deactivated - processing resumed')
          break
          
        // Notifications
        case 'notification':
          switch (data.payload.level) {
            case 'error':
              toast.error(data.payload.message)
              break
            case 'warning':
              toast(data.payload.message, { icon: '⚠️' })
              break
            case 'success':
              toast.success(data.payload.message)
              break
            default:
              toast(data.payload.message)
          }
          break
          
        default:
          console.log('Unknown WebSocket message type:', data.type)
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error)
    }
  }, [lastMessage, queryClient])
  
  // Connection status
  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Connected',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Disconnected',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState]
  
  // Send a message to the server
  const send = useCallback((type, payload = {}) => {
    if (readyState === ReadyState.OPEN) {
      sendMessage(JSON.stringify({ type, payload }))
    } else {
      console.warn('WebSocket not connected, cannot send message')
    }
  }, [readyState, sendMessage])
  
  // Subscribe to specific channels
  const subscribe = useCallback((channels) => {
    send('subscribe', { channels })
  }, [send])
  
  // Unsubscribe from channels
  const unsubscribe = useCallback((channels) => {
    send('unsubscribe', { channels })
  }, [send])
  
  return {
    connectionStatus,
    isConnected: readyState === ReadyState.OPEN,
    send,
    subscribe,
    unsubscribe,
    readyState
  }
}