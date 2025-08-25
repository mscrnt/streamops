// Singleton WebSocket manager to maintain a single persistent connection
class WebSocketManager {
  constructor() {
    this.ws = null
    this.listeners = new Set()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
    this.isConnecting = false
    this.subscriptions = new Set()
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return
    }

    this.isConnecting = true
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    
    console.log('Connecting to WebSocket:', wsUrl)
    
    try {
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        
        // Send initial subscriptions
        this.sendMessage({
          type: 'subscribe',
          topics: ['jobs', 'assets', 'system']
        })
        
        // Notify all listeners
        this.notifyListeners({ type: 'connected' })
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.notifyListeners(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.isConnecting = false
      }
      
      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        this.isConnecting = false
        this.ws = null
        
        // Notify listeners of disconnection
        this.notifyListeners({ type: 'disconnected' })
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 30000)
          console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          setTimeout(() => this.connect(), delay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      this.isConnecting = false
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
  }

  sendMessage(message) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected, cannot send message:', message)
    }
  }

  addListener(callback) {
    this.listeners.add(callback)
    
    // If already connected, notify the new listener
    if (this.ws?.readyState === WebSocket.OPEN) {
      callback({ type: 'connected' })
    }
    
    // Return unsubscribe function
    return () => {
      this.listeners.delete(callback)
    }
  }

  notifyListeners(message) {
    this.listeners.forEach(callback => {
      try {
        callback(message)
      } catch (error) {
        console.error('Error in WebSocket listener:', error)
      }
    })
  }

  // Subscribe to system stats
  subscribeToSystemStats(interval = 5000) {
    if (!this.subscriptions.has('system_stats')) {
      this.subscriptions.add('system_stats')
      this.sendMessage({
        type: 'subscribe_system',
        interval
      })
    }
  }
}

// Create singleton instance
const wsManager = new WebSocketManager()

export default wsManager