import { useEffect, useRef, useState } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { useJobStore, useAssetStore, useNotificationStore } from '@/store/useStore'
import toast from 'react-hot-toast'

// WebSocket hook for real-time updates
export const useStreamOpsWebSocket = () => {
  const [isReconnecting, setIsReconnecting] = useState(false)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 10
  
  // Store actions
  const { updateJob, addJob, setActiveJobs } = useJobStore()
  const { updateAsset, addAsset } = useAssetStore()
  const { addNotification } = useNotificationStore()
  
  // WebSocket URL - adjust protocol based on current location
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
  
  const {
    sendMessage,
    sendJsonMessage,
    lastMessage,
    lastJsonMessage,
    readyState,
    getWebSocket,
  } = useWebSocket(wsUrl, {
    onOpen: () => {
      console.log('WebSocket connected')
      reconnectAttempts.current = 0
      setIsReconnecting(false)
      
      // Send initial subscription message
      sendJsonMessage({
        type: 'subscribe',
        topics: ['jobs', 'assets', 'system']
      })
    },
    onClose: (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
      
      if (event.code !== 1000) { // Not a normal closure
        setIsReconnecting(true)
        reconnectAttempts.current += 1
        
        if (reconnectAttempts.current <= maxReconnectAttempts) {
          toast.error(`Connection lost. Attempting to reconnect... (${reconnectAttempts.current}/${maxReconnectAttempts})`)
        } else {
          toast.error('Connection lost. Please refresh the page.')
          setIsReconnecting(false)
        }
      }
    },
    onError: (event) => {
      console.error('WebSocket error:', event)
      toast.error('WebSocket connection error')
    },
    shouldReconnect: (closeEvent) => {
      // Reconnect unless it was a normal closure or we've exceeded max attempts
      return closeEvent.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts
    },
    reconnectAttempts: maxReconnectAttempts,
    reconnectInterval: (attemptNumber) => Math.min(1000 * Math.pow(1.5, attemptNumber), 30000),
  })

  // Handle incoming messages
  useEffect(() => {
    if (lastJsonMessage) {
      handleWebSocketMessage(lastJsonMessage)
    }
  }, [lastJsonMessage])

  const handleWebSocketMessage = (message) => {
    try {
      const { type } = message

      // Handle messages based on their type
      switch (type) {
        case 'subscription_confirmed':
          console.log('Subscription confirmed for topics:', message.topics)
          break
          
        case 'system_subscription_confirmed':
          console.log('System subscription confirmed')
          break
          
        case 'jobs_update':
          if (message.jobs) {
            message.jobs.forEach(job => {
              updateJob(job)
            })
          }
          break
          
        case 'system_stats':
          if (message.stats) {
            // Update system stats in store if needed
            console.log('System stats:', message.stats)
          }
          break
          
        case 'job_created':
        case 'job_updated':
        case 'job_completed':
        case 'job_failed':
          handleJobUpdate(type, message)
          break
          
        case 'asset_created':
        case 'asset_updated':
        case 'asset_deleted':
          handleAssetUpdate(type, message)
          break
          
        case 'notification':
          if (message.notification) {
            addNotification(message.notification)
          }
          break
          
        default:
          console.log('Unhandled WebSocket message:', message)
      }
    } catch (error) {
      console.error('Error handling WebSocket message:', error, message)
    }
  }

  const handleJobUpdate = (type, data) => {
    switch (type) {
      case 'job_created':
        addJob(data)
        addNotification({
          type: 'info',
          title: 'New Job Created',
          message: `${data.type} job started for ${data.asset_path || 'unknown asset'}`,
        })
        break
        
      case 'job_updated':
        updateJob(data.id, data)
        
        // Show notifications for important status changes
        if (data.status === 'completed') {
          addNotification({
            type: 'success',
            title: 'Job Completed',
            message: `${data.type} job completed successfully`,
          })
        } else if (data.status === 'failed') {
          addNotification({
            type: 'error',
            title: 'Job Failed',
            message: `${data.type} job failed: ${data.error || 'Unknown error'}`,
          })
        }
        break
        
      case 'job_progress':
        updateJob(data.id, { 
          progress: data.progress,
          status: 'running',
          updated_at: new Date().toISOString()
        })
        break
        
      case 'active_jobs':
        setActiveJobs(data)
        break
        
      default:
        console.log('Unhandled job update:', type, data)
    }
  }

  const handleAssetUpdate = (type, data) => {
    switch (type) {
      case 'asset_created':
        addAsset(data)
        addNotification({
          type: 'info',
          title: 'New Asset Indexed',
          message: `${data.filename} has been added to your library`,
        })
        break
        
      case 'asset_updated':
        updateAsset(data.id, data)
        break
        
      case 'asset_thumbnails_ready':
        updateAsset(data.asset_id, { 
          has_thumbnails: true,
          thumbnail_path: data.thumbnail_path,
          updated_at: new Date().toISOString()
        })
        break
        
      default:
        console.log('Unhandled asset update:', type, data)
    }
  }

  const handleSystemUpdate = (type, data) => {
    switch (type) {
      case 'system_stats':
        // Update system stats in store if needed
        break
        
      case 'drive_status':
        addNotification({
          type: data.status === 'online' ? 'success' : 'warning',
          title: 'Drive Status Change',
          message: `Drive ${data.path} is now ${data.status}`,
        })
        break
        
      case 'system_alert':
        addNotification({
          type: data.level || 'warning',
          title: 'System Alert',
          message: data.message,
        })
        break
        
      default:
        console.log('Unhandled system update:', type, data)
    }
  }

  const handleNotificationUpdate = (type, data) => {
    addNotification(data)
  }

  // Connection status helpers
  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState]

  const isConnected = readyState === ReadyState.OPEN
  const isConnecting = readyState === ReadyState.CONNECTING || isReconnecting

  return {
    sendMessage,
    sendJsonMessage,
    lastMessage,
    lastJsonMessage,
    readyState,
    connectionStatus,
    isConnected,
    isConnecting,
    isReconnecting,
    getWebSocket,
  }
}

// Hook for subscribing to specific job updates
// Hook for subscribing to specific job updates
export const useJobWebSocket = (jobId) => {
  const [job, setJob] = useState(null)
  // Use global store instead of creating another WebSocket connection
  return { job, isConnected: true }
}

// Hook for real-time system monitoring  
export const useSystemWebSocket = () => {
  const [systemStats, setSystemStats] = useState(null)
  // Use global store instead of creating another WebSocket connection
  return { systemStats, isConnected: true }
}

export default useStreamOpsWebSocket