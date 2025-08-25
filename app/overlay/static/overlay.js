/**
 * StreamOps Overlay Client-Side JavaScript
 * Handles WebSocket communication, animations, and overlay management
 */

(function(window, document) {
  'use strict';

  // ========== Constants ========== 
  const ANIMATION_DURATION = {
    fast: 150,
    normal: 300,
    slow: 500,
    slower: 750
  };

  const WEBSOCKET_CONFIG = {
    reconnectAttempts: 10,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    pingInterval: 30000,
    connectionTimeout: 5000
  };

  const LOG_LEVELS = {
    ERROR: 0,
    WARN: 1,
    INFO: 2,
    DEBUG: 3
  };

  // ========== Utility Functions ==========
  
  /**
   * Enhanced logging with levels
   */
  const Logger = {
    level: LOG_LEVELS.INFO,
    
    error: function(...args) {
      if (this.level >= LOG_LEVELS.ERROR) {
        console.error('[StreamOps Overlay]', ...args);
      }
    },
    
    warn: function(...args) {
      if (this.level >= LOG_LEVELS.WARN) {
        console.warn('[StreamOps Overlay]', ...args);
      }
    },
    
    info: function(...args) {
      if (this.level >= LOG_LEVELS.INFO) {
        console.info('[StreamOps Overlay]', ...args);
      }
    },
    
    debug: function(...args) {
      if (this.level >= LOG_LEVELS.DEBUG) {
        console.debug('[StreamOps Overlay]', ...args);
      }
    }
  };

  /**
   * Utility functions
   */
  const Utils = {
    // Generate UUID v4
    generateId: function() {
      return 'overlay-' + Math.random().toString(36).substr(2, 9);
    },

    // Debounce function
    debounce: function(func, wait) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    },

    // Throttle function
    throttle: function(func, limit) {
      let inThrottle;
      return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
          func.apply(context, args);
          inThrottle = true;
          setTimeout(() => inThrottle = false, limit);
        }
      };
    },

    // Deep merge objects
    deepMerge: function(target, ...sources) {
      if (!sources.length) return target;
      const source = sources.shift();

      if (this.isObject(target) && this.isObject(source)) {
        for (const key in source) {
          if (this.isObject(source[key])) {
            if (!target[key]) Object.assign(target, { [key]: {} });
            this.deepMerge(target[key], source[key]);
          } else {
            Object.assign(target, { [key]: source[key] });
          }
        }
      }

      return this.deepMerge(target, ...sources);
    },

    // Check if value is object
    isObject: function(item) {
      return item && typeof item === 'object' && !Array.isArray(item);
    },

    // Parse JSON safely
    safeJsonParse: function(str, fallback = null) {
      try {
        return JSON.parse(str);
      } catch (e) {
        Logger.warn('Failed to parse JSON:', str);
        return fallback;
      }
    },

    // Format time duration
    formatDuration: function(seconds) {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;
      
      if (hours > 0) {
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      }
      return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    },

    // Get element by selector with fallback
    getElement: function(selector, context = document) {
      const element = context.querySelector(selector);
      if (!element) {
        Logger.warn('Element not found:', selector);
      }
      return element;
    },

    // Get elements by selector
    getElements: function(selector, context = document) {
      return Array.from(context.querySelectorAll(selector));
    }
  };

  // ========== Animation Manager ==========
  
  const AnimationManager = {
    activeAnimations: new Map(),
    
    /**
     * Apply animation to element
     */
    animate: function(element, animationName, options = {}) {
      if (!element) {
        Logger.warn('Cannot animate null element');
        return Promise.resolve();
      }

      const {
        duration = ANIMATION_DURATION.normal,
        easing = 'ease-out',
        fillMode = 'forwards',
        onComplete = null,
        onStart = null
      } = options;

      return new Promise((resolve) => {
        // Remove any existing animation
        this.stopAnimation(element);

        // Generate unique animation ID
        const animationId = Utils.generateId();
        this.activeAnimations.set(element, animationId);

        // Add animation class
        element.classList.add(animationName);
        
        if (onStart) onStart(element);

        const cleanup = () => {
          element.classList.remove(animationName);
          if (this.activeAnimations.get(element) === animationId) {
            this.activeAnimations.delete(element);
          }
          element.removeEventListener('animationend', handleAnimationEnd);
          element.removeEventListener('animationcancel', handleAnimationEnd);
          if (onComplete) onComplete(element);
          resolve();
        };

        const handleAnimationEnd = (e) => {
          if (e.target === element) {
            cleanup();
          }
        };

        element.addEventListener('animationend', handleAnimationEnd);
        element.addEventListener('animationcancel', handleAnimationEnd);

        // Fallback timeout
        setTimeout(cleanup, duration + 100);
      });
    },

    /**
     * Stop animation on element
     */
    stopAnimation: function(element) {
      if (!element) return;
      
      const animationId = this.activeAnimations.get(element);
      if (animationId) {
        // Remove animation classes
        const animationClasses = [
          'animate-fade-in', 'animate-fade-out',
          'animate-slide-in-up', 'animate-slide-in-down',
          'animate-slide-in-left', 'animate-slide-in-right',
          'animate-slide-out-up', 'animate-slide-out-down',
          'animate-slide-out-left', 'animate-slide-out-right',
          'animate-zoom-in', 'animate-zoom-out',
          'animate-bounce-in', 'animate-bounce-out',
          'animate-shake', 'animate-pulse', 'animate-wobble'
        ];
        
        element.classList.remove(...animationClasses);
        this.activeAnimations.delete(element);
      }
    },

    /**
     * Chain multiple animations
     */
    chain: function(animations) {
      return animations.reduce((promise, { element, animation, options }) => {
        return promise.then(() => this.animate(element, animation, options));
      }, Promise.resolve());
    },

    /**
     * Run animations in parallel
     */
    parallel: function(animations) {
      const promises = animations.map(({ element, animation, options }) => 
        this.animate(element, animation, options)
      );
      return Promise.all(promises);
    }
  };

  // ========== WebSocket Manager ==========
  
  const WebSocketManager = {
    ws: null,
    connected: false,
    reconnectAttempts: 0,
    reconnectTimer: null,
    pingTimer: null,
    messageQueue: [],
    eventHandlers: new Map(),
    connectionPromise: null,

    /**
     * Initialize WebSocket connection
     */
    init: function(url, overlayId = null) {
      this.url = url;
      this.overlayId = overlayId;
      
      Logger.info('Initializing WebSocket connection to:', url);
      return this.connect();
    },

    /**
     * Connect to WebSocket server
     */
    connect: function() {
      if (this.connectionPromise) {
        return this.connectionPromise;
      }

      this.connectionPromise = new Promise((resolve, reject) => {
        try {
          this.ws = new WebSocket(this.url);
          
          const connectionTimeout = setTimeout(() => {
            Logger.error('WebSocket connection timeout');
            this.ws.close();
            reject(new Error('Connection timeout'));
          }, WEBSOCKET_CONFIG.connectionTimeout);

          this.ws.onopen = () => {
            clearTimeout(connectionTimeout);
            Logger.info('WebSocket connected successfully');
            
            this.connected = true;
            this.reconnectAttempts = 0;
            this.connectionPromise = null;
            
            this.updateConnectionStatus('connected');
            this.startPingInterval();
            this.processMessageQueue();
            
            // Send registration if overlay ID is available
            if (this.overlayId) {
              this.send({
                type: 'register',
                overlay_id: this.overlayId
              });
            }
            
            this.emit('connected');
            resolve();
          };

          this.ws.onmessage = (event) => {
            try {
              const data = Utils.safeJsonParse(event.data);
              if (data) {
                Logger.debug('Received message:', data);
                this.handleMessage(data);
              }
            } catch (error) {
              Logger.error('Error processing message:', error);
            }
          };

          this.ws.onclose = (event) => {
            clearTimeout(connectionTimeout);
            Logger.info('WebSocket disconnected, code:', event.code);
            
            this.connected = false;
            this.connectionPromise = null;
            this.stopPingInterval();
            this.updateConnectionStatus('disconnected');
            
            this.emit('disconnected', event);
            
            if (!event.wasClean) {
              this.scheduleReconnect();
            }
            
            reject(new Error(`Connection closed: ${event.code}`));
          };

          this.ws.onerror = (error) => {
            clearTimeout(connectionTimeout);
            Logger.error('WebSocket error:', error);
            this.updateConnectionStatus('error');
            this.emit('error', error);
            reject(error);
          };

        } catch (error) {
          Logger.error('Failed to create WebSocket connection:', error);
          this.connectionPromise = null;
          reject(error);
        }
      });

      return this.connectionPromise;
    },

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect: function() {
      if (this.reconnectAttempts >= WEBSOCKET_CONFIG.reconnectAttempts) {
        Logger.error('Max reconnection attempts reached');
        this.updateConnectionStatus('failed');
        return;
      }

      this.reconnectAttempts++;
      const delay = Math.min(
        WEBSOCKET_CONFIG.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
        WEBSOCKET_CONFIG.maxReconnectDelay
      );

      Logger.info(`Scheduling reconnect attempt ${this.reconnectAttempts}/${WEBSOCKET_CONFIG.reconnectAttempts} in ${delay}ms`);
      this.updateConnectionStatus('reconnecting');

      this.reconnectTimer = setTimeout(() => {
        Logger.info(`Reconnection attempt ${this.reconnectAttempts}`);
        this.connect().catch(() => {
          // Error handled in connect method
        });
      }, delay);
    },

    /**
     * Send message via WebSocket
     */
    send: function(data) {
      if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          const message = JSON.stringify(data);
          this.ws.send(message);
          Logger.debug('Sent message:', data);
          return true;
        } catch (error) {
          Logger.error('Failed to send message:', error);
          return false;
        }
      } else {
        Logger.debug('Queueing message (not connected):', data);
        this.messageQueue.push(data);
        return false;
      }
    },

    /**
     * Process queued messages
     */
    processMessageQueue: function() {
      while (this.messageQueue.length > 0 && this.connected) {
        const message = this.messageQueue.shift();
        this.send(message);
      }
    },

    /**
     * Handle incoming messages
     */
    handleMessage: function(data) {
      const { type } = data;
      
      switch (type) {
        case 'ping':
          this.send({ type: 'pong', overlay_id: this.overlayId });
          break;
          
        case 'show':
          this.emit('show', data);
          break;
          
        case 'hide':
          this.emit('hide', data);
          break;
          
        case 'update':
          this.emit('update', data);
          break;
          
        default:
          this.emit('message', data);
          break;
      }
    },

    /**
     * Start ping interval
     */
    startPingInterval: function() {
      this.stopPingInterval();
      this.pingTimer = setInterval(() => {
        if (this.connected) {
          this.send({ type: 'ping', overlay_id: this.overlayId });
        }
      }, WEBSOCKET_CONFIG.pingInterval);
    },

    /**
     * Stop ping interval
     */
    stopPingInterval: function() {
      if (this.pingTimer) {
        clearInterval(this.pingTimer);
        this.pingTimer = null;
      }
    },

    /**
     * Update connection status indicator
     */
    updateConnectionStatus: function(status) {
      const indicator = Utils.getElement('#connection-status');
      if (indicator) {
        indicator.className = `connection-status ${status}`;
        indicator.title = `WebSocket: ${status}`;
      }
    },

    /**
     * Event emitter functionality
     */
    on: function(event, handler) {
      if (!this.eventHandlers.has(event)) {
        this.eventHandlers.set(event, new Set());
      }
      this.eventHandlers.get(event).add(handler);
    },

    off: function(event, handler) {
      if (this.eventHandlers.has(event)) {
        this.eventHandlers.get(event).delete(handler);
      }
    },

    emit: function(event, data = null) {
      if (this.eventHandlers.has(event)) {
        this.eventHandlers.get(event).forEach(handler => {
          try {
            handler(data);
          } catch (error) {
            Logger.error('Error in event handler:', error);
          }
        });
      }
    },

    /**
     * Close connection
     */
    close: function() {
      Logger.info('Closing WebSocket connection');
      
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      
      this.stopPingInterval();
      
      if (this.ws) {
        this.ws.close(1000, 'Client disconnecting');
      }
      
      this.connected = false;
      this.connectionPromise = null;
    }
  };

  // ========== Overlay Manager ==========
  
  const OverlayManager = {
    overlays: new Map(),
    defaultOptions: {
      animation: {
        show: 'animate-fade-in',
        hide: 'animate-fade-out',
        update: 'animate-pulse'
      },
      autoHide: false,
      duration: null,
      trackImpressions: true
    },

    /**
     * Register overlay
     */
    register: function(overlayId, element, options = {}) {
      if (!element) {
        Logger.error('Cannot register overlay without element');
        return false;
      }

      const config = Utils.deepMerge({}, this.defaultOptions, options);
      
      this.overlays.set(overlayId, {
        id: overlayId,
        element: element,
        config: config,
        visible: false,
        lastShown: null,
        impressions: 0,
        autoHideTimer: null
      });

      Logger.info('Registered overlay:', overlayId);
      return true;
    },

    /**
     * Unregister overlay
     */
    unregister: function(overlayId) {
      const overlay = this.overlays.get(overlayId);
      if (overlay) {
        if (overlay.autoHideTimer) {
          clearTimeout(overlay.autoHideTimer);
        }
        AnimationManager.stopAnimation(overlay.element);
        this.overlays.delete(overlayId);
        Logger.info('Unregistered overlay:', overlayId);
        return true;
      }
      return false;
    },

    /**
     * Show overlay
     */
    show: function(overlayId, content = null, options = {}) {
      const overlay = this.overlays.get(overlayId);
      if (!overlay) {
        Logger.warn('Overlay not found:', overlayId);
        return Promise.resolve();
      }

      const {
        animation = overlay.config.animation.show,
        duration = overlay.config.duration,
        onComplete = null
      } = options;

      // Update content if provided
      if (content) {
        this.updateContent(overlayId, content);
      }

      // Clear any existing auto-hide timer
      if (overlay.autoHideTimer) {
        clearTimeout(overlay.autoHideTimer);
        overlay.autoHideTimer = null;
      }

      // Show element
      overlay.element.style.display = 'block';
      overlay.element.classList.remove('overlay-hidden', 'overlay-invisible');
      overlay.visible = true;
      overlay.lastShown = new Date();

      // Track impression
      if (overlay.config.trackImpressions) {
        overlay.impressions++;
        this.trackImpression(overlayId);
      }

      // Apply animation
      return AnimationManager.animate(overlay.element, animation, {
        onComplete: (element) => {
          element.classList.add('overlay-visible');
          
          // Schedule auto-hide if duration specified
          if (duration && duration > 0) {
            overlay.autoHideTimer = setTimeout(() => {
              this.hide(overlayId);
            }, duration * 1000);
          }
          
          if (onComplete) onComplete(element);
        }
      });
    },

    /**
     * Hide overlay
     */
    hide: function(overlayId, options = {}) {
      const overlay = this.overlays.get(overlayId);
      if (!overlay || !overlay.visible) {
        return Promise.resolve();
      }

      const {
        animation = overlay.config.animation.hide,
        onComplete = null
      } = options;

      // Clear auto-hide timer
      if (overlay.autoHideTimer) {
        clearTimeout(overlay.autoHideTimer);
        overlay.autoHideTimer = null;
      }

      overlay.visible = false;

      return AnimationManager.animate(overlay.element, animation, {
        onComplete: (element) => {
          element.style.display = 'none';
          element.classList.remove('overlay-visible');
          element.classList.add('overlay-hidden');
          
          if (onComplete) onComplete(element);
        }
      });
    },

    /**
     * Update overlay content
     */
    updateContent: function(overlayId, content, animated = false) {
      const overlay = this.overlays.get(overlayId);
      if (!overlay) {
        Logger.warn('Overlay not found:', overlayId);
        return;
      }

      const element = overlay.element;

      if (animated) {
        AnimationManager.animate(element, overlay.config.animation.update, {
          onComplete: () => {
            this.applyContentChanges(element, content);
          }
        });
      } else {
        this.applyContentChanges(element, content);
      }
    },

    /**
     * Apply content changes to element
     */
    applyContentChanges: function(element, content) {
      // Update text content
      if (content.text) {
        const textElements = Utils.getElements('.overlay-text, [data-content="text"]', element);
        textElements.forEach(el => el.textContent = content.text);
      }

      // Update HTML content
      if (content.html) {
        const htmlElements = Utils.getElements('.overlay-content, [data-content="html"]', element);
        htmlElements.forEach(el => el.innerHTML = content.html);
      }

      // Update image sources
      if (content.image_url) {
        const imgElements = Utils.getElements('.overlay-image, [data-content="image"]', element);
        imgElements.forEach(el => {
          el.src = content.image_url;
          el.onerror = () => Logger.warn('Failed to load image:', content.image_url);
        });
      }

      // Update template variables
      if (content.template_variables) {
        Object.entries(content.template_variables).forEach(([key, value]) => {
          const elements = Utils.getElements(`[data-variable="${key}"]`, element);
          elements.forEach(el => {
            if (el.tagName === 'IMG') {
              el.src = value;
            } else if (el.tagName === 'INPUT') {
              el.value = value;
            } else {
              el.textContent = value;
            }
          });
        });
      }

      Logger.debug('Updated content for overlay:', element.id);
    },

    /**
     * Track impression
     */
    trackImpression: function(overlayId) {
      WebSocketManager.send({
        type: 'impression',
        overlay_id: overlayId,
        timestamp: new Date().toISOString()
      });
    },

    /**
     * Get overlay statistics
     */
    getStats: function(overlayId) {
      const overlay = this.overlays.get(overlayId);
      if (!overlay) {
        return null;
      }

      return {
        id: overlayId,
        visible: overlay.visible,
        impressions: overlay.impressions,
        lastShown: overlay.lastShown,
        element: overlay.element
      };
    },

    /**
     * Get all overlay statistics
     */
    getAllStats: function() {
      const stats = {};
      for (const [id, overlay] of this.overlays.entries()) {
        stats[id] = this.getStats(id);
      }
      return stats;
    }
  };

  // ========== Event Handlers ==========
  
  const EventHandlers = {
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboard: function(event) {
      // Only process shortcuts with Ctrl+Alt
      if (!event.ctrlKey || !event.altKey) return;

      switch (event.key.toLowerCase()) {
        case 'd':
          event.preventDefault();
          window.StreamOpsOverlay.toggleDebugMode();
          break;

        case 'g':
          event.preventDefault();
          window.StreamOpsOverlay.toggleDebugGrid();
          break;

        case 'r':
          event.preventDefault();
          location.reload();
          break;

        case 'c':
          event.preventDefault();
          console.log('Overlay Stats:', OverlayManager.getAllStats());
          break;
      }
    },

    /**
     * Handle window resize
     */
    handleResize: Utils.debounce(function() {
      Logger.debug('Window resized');
      // Refresh overlay positions if needed
    }, 250),

    /**
     * Handle visibility change
     */
    handleVisibilityChange: function() {
      if (document.hidden) {
        Logger.debug('Page hidden, pausing operations');
      } else {
        Logger.debug('Page visible, resuming operations');
      }
    }
  };

  // ========== Main StreamOps Overlay Object ==========
  
  window.StreamOpsOverlay = {
    version: '1.0.0',
    initialized: false,
    debugMode: false,
    overlayId: null,

    // Expose managers
    WebSocket: WebSocketManager,
    Animation: AnimationManager,
    Overlay: OverlayManager,
    Utils: Utils,
    Logger: Logger,

    /**
     * Initialize overlay system
     */
    init: function(options = {}) {
      if (this.initialized) {
        Logger.warn('StreamOps Overlay already initialized');
        return Promise.resolve();
      }

      const {
        websocketUrl = 'ws://localhost:7769/overlay/ws',
        overlayId = null,
        debugMode = false,
        logLevel = 'INFO'
      } = options;

      Logger.level = LOG_LEVELS[logLevel] || LOG_LEVELS.INFO;
      this.debugMode = debugMode;
      this.overlayId = overlayId;

      if (debugMode) {
        Logger.level = LOG_LEVELS.DEBUG;
        Logger.debug('Debug mode enabled');
      }

      // Register event listeners
      document.addEventListener('keydown', EventHandlers.handleKeyboard);
      window.addEventListener('resize', EventHandlers.handleResize);
      document.addEventListener('visibilitychange', EventHandlers.handleVisibilityChange);

      // Auto-register overlays found on page
      this.autoRegisterOverlays();

      // Setup WebSocket event handlers
      WebSocketManager.on('show', (data) => {
        OverlayManager.show(data.overlay_id, data.content, {
          animation: data.animation,
          duration: data.duration
        });
      });

      WebSocketManager.on('hide', (data) => {
        OverlayManager.hide(data.overlay_id, {
          animation: data.animation
        });
      });

      WebSocketManager.on('update', (data) => {
        OverlayManager.updateContent(data.overlay_id, data.content, true);
      });

      // Initialize WebSocket connection
      const initPromise = WebSocketManager.init(websocketUrl, overlayId)
        .then(() => {
          this.initialized = true;
          Logger.info('StreamOps Overlay system initialized successfully');
        })
        .catch((error) => {
          Logger.error('Failed to initialize overlay system:', error);
          throw error;
        });

      Logger.info('Initializing StreamOps Overlay System v' + this.version);
      return initPromise;
    },

    /**
     * Auto-register overlays found on the page
     */
    autoRegisterOverlays: function() {
      const overlayElements = Utils.getElements('[id*="overlay"], .overlay-container');
      
      overlayElements.forEach(element => {
        if (element.id) {
          OverlayManager.register(element.id, element);
        }
      });

      Logger.info(`Auto-registered ${overlayElements.length} overlays`);
    },

    /**
     * Register overlay manually
     */
    registerOverlay: function(overlayId, element, options = {}) {
      return OverlayManager.register(overlayId, element, options);
    },

    /**
     * Show overlay
     */
    showOverlay: function(overlayId, content = null, options = {}) {
      return OverlayManager.show(overlayId, content, options);
    },

    /**
     * Hide overlay
     */
    hideOverlay: function(overlayId, options = {}) {
      return OverlayManager.hide(overlayId, options);
    },

    /**
     * Update overlay content
     */
    updateOverlay: function(overlayId, content, animated = true) {
      return OverlayManager.updateContent(overlayId, content, animated);
    },

    /**
     * Send message via WebSocket
     */
    sendMessage: function(data) {
      return WebSocketManager.send(data);
    },

    /**
     * Toggle debug mode
     */
    toggleDebugMode: function() {
      this.debugMode = !this.debugMode;
      Logger.level = this.debugMode ? LOG_LEVELS.DEBUG : LOG_LEVELS.INFO;
      
      Logger.info('Debug mode:', this.debugMode ? 'ON' : 'OFF');
      
      if (this.debugMode) {
        document.body.style.border = '2px solid red';
        console.log('Overlay Stats:', OverlayManager.getAllStats());
      } else {
        document.body.style.border = 'none';
      }
    },

    /**
     * Toggle debug grid
     */
    toggleDebugGrid: function() {
      const grid = Utils.getElement('#debug-grid');
      if (grid) {
        const isVisible = grid.style.display === 'block';
        grid.style.display = isVisible ? 'none' : 'block';
        Logger.info('Debug grid:', isVisible ? 'OFF' : 'ON');
      }
    },

    /**
     * Get overlay statistics
     */
    getOverlayStats: function(overlayId = null) {
      if (overlayId) {
        return OverlayManager.getStats(overlayId);
      }
      return OverlayManager.getAllStats();
    },

    /**
     * Cleanup and shutdown
     */
    destroy: function() {
      Logger.info('Shutting down StreamOps Overlay system');
      
      // Close WebSocket connection
      WebSocketManager.close();
      
      // Clear all overlays
      for (const [overlayId] of OverlayManager.overlays.entries()) {
        OverlayManager.unregister(overlayId);
      }
      
      // Remove event listeners
      document.removeEventListener('keydown', EventHandlers.handleKeyboard);
      window.removeEventListener('resize', EventHandlers.handleResize);
      document.removeEventListener('visibilitychange', EventHandlers.handleVisibilityChange);
      
      this.initialized = false;
    }
  };

  // ========== Auto-Initialize ==========
  
  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      const overlayId = window.overlayId || null;
      const websocketUrl = window.websocketUrl || 'ws://localhost:7769/overlay/ws';
      
      window.StreamOpsOverlay.init({
        overlayId: overlayId,
        websocketUrl: websocketUrl,
        debugMode: false
      }).catch((error) => {
        Logger.error('Auto-initialization failed:', error);
      });
    });
  } else {
    // DOM already ready
    setTimeout(() => {
      const overlayId = window.overlayId || null;
      const websocketUrl = window.websocketUrl || 'ws://localhost:7769/overlay/ws';
      
      window.StreamOpsOverlay.init({
        overlayId: overlayId,
        websocketUrl: websocketUrl,
        debugMode: false
      }).catch((error) => {
        Logger.error('Auto-initialization failed:', error);
      });
    }, 100);
  }

  // ========== Global Utilities ==========
  
  // Backward compatibility aliases
  window.showOverlay = function(overlayId, content, options) {
    return window.StreamOpsOverlay.showOverlay(overlayId, content, options);
  };

  window.hideOverlay = function(overlayId, options) {
    return window.StreamOpsOverlay.hideOverlay(overlayId, options);
  };

  window.updateOverlay = function(overlayId, content, animated) {
    return window.StreamOpsOverlay.updateOverlay(overlayId, content, animated);
  };

  Logger.info('StreamOps Overlay Client loaded successfully');

})(window, document);